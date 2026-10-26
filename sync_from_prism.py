"""Turn the Prism instance into the two packwiz packs in this repo, as set in packsync.json.

  full/     every enabled mod, configs, resource packs, shaders
  public/   mods that run on the server plus public_pack_keeps (sodium); no shaders

Mods come from Prism's own metadata (mods/.index/*.pw.toml) where it has some. Jars without it are looked
up on Modrinth by hash (cached in modrinth-matches.json); jars Modrinth doesn't know are copied in and
hosted in this repo. Files matching "preserve" are installed once and never overwritten for players.

Usage: python sync_from_prism.py      then: git add -A, git commit, git push
"""
import fnmatch, hashlib, io, json, os, shutil, subprocess, tomllib, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "packsync.json"), encoding="utf-8"))
GAME = os.path.join(CFG["instance"], "minecraft")
MODS = os.path.join(GAME, "mods")
CACHE = os.path.join(HERE, "modrinth-matches.json")
CLIENT_ONLY = set(CFG["client_only_mods"])


def matches(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def mod_ids(path):
    """The jar's own mod ids, from its NeoForge or Fabric metadata."""
    ids = set()
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "META-INF/neoforge.mods.toml" in names:
            try:
                toml = tomllib.loads(z.read("META-INF/neoforge.mods.toml").decode("utf-8", "replace"))
                ids |= {m.get("modId") for m in toml.get("mods", [])}
            except Exception:
                pass
        if "fabric.mod.json" in names:
            try:
                ids.add(json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False).get("id"))
            except Exception:
                pass
    ids.discard(None)
    return ids


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    # TOML basic strings share JSON's escapes, but not its \u surrogate pairs for emoji: keep those as-is
    return json.dumps(v, ensure_ascii=False)


def write_metafile(path, meta):
    """Write a .pw.toml: top-level keys, then [download] and [update.<source>]."""
    lines = [f"{k} = {toml_value(v)}" for k, v in meta.items() if not isinstance(v, dict)]
    lines += ["", "[download]"] + [f"{k} = {toml_value(v)}" for k, v in meta["download"].items()]
    for source, fields in meta.get("update", {}).items():
        lines += ["", f"[update.{source}]"] + [f"{k} = {toml_value(v)}" for k, v in fields.items()]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


# ---- what's in the instance ---------------------------------------------------------------

prism = {}
for f in os.listdir(os.path.join(MODS, ".index")):
    t = tomllib.load(open(os.path.join(MODS, ".index", f), "rb"))
    prism[t.get("filename")] = t

jars = sorted((f for f in os.listdir(MODS) if f.endswith(".jar")), key=str.lower)
ids = {f: mod_ids(os.path.join(MODS, f)) for f in jars}
client = {f for f in jars if ids[f] and ids[f] <= CLIENT_ONLY}
public = {f for f in jars if f not in client or ids[f] & set(CFG["public_pack_keeps"])}

# Jars Prism has no metadata for (or only CurseForge metadata): try Modrinth by sha512.
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
sha = {f: hashlib.sha512(open(os.path.join(MODS, f), "rb").read()).hexdigest()
       for f in jars if f not in prism or prism[f]["download"].get("mode") == "metadata:curseforge"}
unknown = [h for h in sha.values() if h not in cache]
if unknown:
    req = urllib.request.Request("https://api.modrinth.com/v2/version_files",
                                 data=json.dumps({"hashes": unknown, "algorithm": "sha512"}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "best-of-pack-3 sync"})
    found = json.load(urllib.request.urlopen(req))
    for h in unknown:
        v = found.get(h)
        cache[h] = None if not v else {
            "name": v.get("name"), "project": v["project_id"], "version": v["id"],
            "url": next(x["url"] for x in v["files"] if x["hashes"]["sha512"] == h)}
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, sort_keys=True)


def mod_entry(f):
    """('meta', metafile dict) for a downloadable mod, or ('file', None) for a jar hosted in the repo."""
    side = "client" if f in client else "both"
    m = cache.get(sha.get(f, ""))
    if m:
        return "meta", {"name": os.path.splitext(f)[0], "filename": f, "side": side,
                        "download": {"url": m["url"], "hash-format": "sha512", "hash": sha[f]},
                        "update": {"modrinth": {"mod-id": m["project"], "version": m["version"]}}}
    if f in prism:
        t = prism[f]
        meta = {"name": t.get("name", f), "filename": f, "side": side,
                # Prism writes url = "" for CurseForge files resolved through the API; the installer wants it absent
                "download": {k: v for k, v in t["download"].items() if v != "" and not (k == "mode" and v == "url")},
                "update": t.get("update", {})}
        return "meta", meta
    return "file", None


# ---- writing a pack -----------------------------------------------------------------------

def build(name, selection, with_shaders):
    root = os.path.join(HERE, name)
    for sub in ["mods"] + CFG["pack_dirs"] + ["options.txt"]:
        p = os.path.join(root, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    os.makedirs(os.path.join(root, "mods"), exist_ok=True)
    if not os.path.exists(os.path.join(root, "pack.toml")):
        p = CFG["pack"]
        subprocess.run([CFG["packwiz"], "init", "--name", p["name"] + ("" if name == "full" else " (public)"),
                        "--author", p["author"], "--version", "1.0.0", "--mc-version", p["minecraft"],
                        "--modloader", "neoforge", "--neoforge-version", p["neoforge"], "-y"],
                       cwd=root, check=True, capture_output=True)

    hosted = []
    for f in sorted(selection, key=str.lower):
        kind, meta = mod_entry(f)
        if kind == "meta":
            write_metafile(os.path.join(root, "mods", os.path.splitext(f)[0] + ".pw.toml"), meta)
        else:
            shutil.copy2(os.path.join(MODS, f), os.path.join(root, "mods", f))
            hosted.append(f)

    for top in CFG["pack_dirs"]:
        if top == "shaderpacks" and not with_shaders:
            continue
        for dirpath, _, files in os.walk(os.path.join(GAME, top)):
            for f in files:
                src = os.path.join(dirpath, f)
                rel = os.path.relpath(src, GAME).replace(os.sep, "/")
                if not matches(rel, CFG["exclude"]):
                    os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
                    shutil.copy2(src, os.path.join(root, rel))
    opts = os.path.join(GAME, "options.txt")
    if os.path.exists(opts):
        text = "\n".join(l for l in open(opts, encoding="utf-8").read().splitlines() if not l.startswith("lastServer:"))
        open(os.path.join(root, "options.txt"), "w", encoding="utf-8", newline="\n").write(text + "\n")

    index_path = os.path.join(root, "index.toml")
    if not os.path.exists(index_path):
        open(index_path, "w", encoding="utf-8", newline="\n").write('hash-format = "sha256"\n')
    subprocess.run([CFG["packwiz"], "refresh"], cwd=root, check=True, capture_output=True)
    mark_preserved(root)
    print(f"{name}: {len(selection)} mods ({len(hosted)} hosted here: {', '.join(hosted) or 'none'})")


def mark_preserved(root):
    """Add preserve = true to matching index entries, then point pack.toml at the new index hash."""
    index_path = os.path.join(root, "index.toml")
    out, rel, count = [], None, 0
    for line in open(index_path, encoding="utf-8").read().splitlines():
        if line.startswith("preserve = "):
            continue  # refresh keeps old flags; rebuild them from the current rules
        if line.startswith("file = "):
            rel = json.loads(line[len("file = "):]) if line[7] == '"' else line[8:-1]
        out.append(line)
        if line.startswith("hash = ") and rel and matches(rel, CFG["preserve"]) and not rel.endswith(".pw.toml"):
            out.append("preserve = true")
            count += 1
    data = ("\n".join(out) + "\n").encode()
    open(index_path, "wb").write(data)
    pack_path = os.path.join(root, "pack.toml")
    pack = open(pack_path, encoding="utf-8").read()
    start = pack.index("[index]")
    head, tail = pack[:start], pack[start:]
    lines = tail.splitlines()
    lines = [f'hash = "{hashlib.sha256(data).hexdigest()}"' if l.startswith("hash = ") else l for l in lines]
    open(pack_path, "w", encoding="utf-8", newline="\n").write(head + "\n".join(lines) + "\n")
    print(f"  {count} files players keep their own copy of")


build("full", set(jars), True)
build("public", public, False)
