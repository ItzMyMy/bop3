"""Turn the Prism instance into the packwiz pack in pack/, as set in packsync.json.

Every enabled mod goes in. Client-only mods that no other mod needs become optional: players get a
checkbox for each on first install (ticked unless listed in optional_off_by_default). Libraries, mods
other mods depend on, keep_required and jars hosted here stay required, so unticking can't crash the game.

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
PROJECTS = os.path.join(HERE, "modrinth-projects.json")
CLIENT_ONLY = set(CFG["client_only_mods"])
KEEP_REQUIRED = set(CFG["keep_required"])
OFF_BY_DEFAULT = set(CFG["optional_off_by_default"])
BUILTIN = {"minecraft", "neoforge", "java", "forge", "fml", "javafml", "mixinextras"}


def matches(rel, patterns):
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def describe(data, depth=0):
    """(own mod ids, ids provided incl. jar-in-jar, required mod ids) from a jar's NeoForge/Fabric metadata."""
    own, requires = set(), set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        if "META-INF/neoforge.mods.toml" in names:
            try:
                toml = tomllib.loads(z.read("META-INF/neoforge.mods.toml").decode("utf-8", "replace"))
                own |= {m.get("modId") for m in toml.get("mods", [])}
                for deps in (toml.get("dependencies") or {}).values():
                    for d in deps:
                        if str(d.get("type", "required" if d.get("mandatory") else "optional")).lower() == "required":
                            requires.add(d.get("modId"))
            except Exception:
                pass
        if "fabric.mod.json" in names:
            try:
                own.add(json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"), strict=False).get("id"))
            except Exception:
                pass
        provides = set(own)
        if depth < 2:
            for n in names:
                if n.startswith("META-INF/") and n.endswith(".jar"):
                    provides |= describe(z.read(n), depth + 1)[1]
    own.discard(None)
    provides.discard(None)
    return own, provides, requires - BUILTIN - {None}


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    # TOML basic strings share JSON's escapes, but not its \u surrogate pairs for emoji: keep those as-is
    return json.dumps(v, ensure_ascii=False)


def write_metafile(path, meta):
    """Write a .pw.toml: top-level keys, then [download], [option] and [update.<source>]."""
    lines = [f"{k} = {toml_value(v)}" for k, v in meta.items() if not isinstance(v, dict)]
    lines += ["", "[download]"] + [f"{k} = {toml_value(v)}" for k, v in meta["download"].items()]
    if "option" in meta:
        lines += ["", "[option]"] + [f"{k} = {toml_value(v)}" for k, v in meta["option"].items()]
    for source, fields in meta.get("update", {}).items():
        lines += ["", f"[update.{source}]"] + [f"{k} = {toml_value(v)}" for k, v in fields.items()]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


def modrinth(path, body=None):
    req = urllib.request.Request("https://api.modrinth.com/v2/" + path, data=body and json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "best-of-pack-3 sync"})
    return json.load(urllib.request.urlopen(req))


# ---- what's in the instance ---------------------------------------------------------------

prism = {}
for f in os.listdir(os.path.join(MODS, ".index")):
    t = tomllib.load(open(os.path.join(MODS, ".index", f), "rb"))
    prism[t.get("filename")] = t

jars = sorted((f for f in os.listdir(MODS) if f.endswith(".jar")), key=str.lower)
info = {f: dict(zip(("ids", "provides", "requires"), describe(open(os.path.join(MODS, f), "rb").read())))
        for f in jars}
client = {f for f in jars if info[f]["ids"] and info[f]["ids"] <= CLIENT_ONLY}
# a jar is needed when another enabled jar requires one of the mod ids it provides
needed = {g for f in jars for g in jars
          if g != f and info[f]["requires"] & info[g]["provides"]}

# Jars Prism has no metadata for (or only CurseForge metadata): try Modrinth by sha512.
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
sha = {f: hashlib.sha512(open(os.path.join(MODS, f), "rb").read()).hexdigest()
       for f in jars if f not in prism or prism[f]["download"].get("mode") == "metadata:curseforge"}
unknown = [h for h in sha.values() if h not in cache]
if unknown:
    found = modrinth("version_files", {"hashes": unknown, "algorithm": "sha512"})
    for h in unknown:
        v = found.get(h)
        cache[h] = None if not v else {
            "name": v.get("name"), "project": v["project_id"], "version": v["id"],
            "url": next(x["url"] for x in v["files"] if x["hashes"]["sha512"] == h)}
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), indent=1, sort_keys=True)


def mod_entry(f):
    """Metafile dict for a downloadable mod, or None for a jar hosted in the repo."""
    side = "client" if f in client else "both"
    m = cache.get(sha.get(f, ""))
    if m:
        return {"name": os.path.splitext(f)[0], "filename": f, "side": side,
                "download": {"url": m["url"], "hash-format": "sha512", "hash": sha[f]},
                "update": {"modrinth": {"mod-id": m["project"], "version": m["version"]}}}
    if f in prism:
        t = prism[f]
        return {"name": t.get("name", f), "filename": f, "side": side,
                # Prism writes url = "" for CurseForge files resolved through the API; the installer wants it absent
                "download": {k: v for k, v in t["download"].items() if v != "" and not (k == "mode" and v == "url")},
                "update": t.get("update", {})}
    return None


entries = {f: mod_entry(f) for f in jars}
optional = {f for f in client
            if f not in needed and entries[f] and not info[f]["ids"] & KEEP_REQUIRED}

# Titles and one-line descriptions for the checkboxes, from Modrinth (cached in modrinth-projects.json).
projects = json.load(open(PROJECTS, encoding="utf-8")) if os.path.exists(PROJECTS) else {}
wanted = sorted({entries[f]["update"]["modrinth"]["mod-id"] for f in optional
                 if "modrinth" in entries[f]["update"]} - set(projects))
if wanted:
    for p in modrinth("projects?ids=" + urllib.request.quote(json.dumps(wanted))):
        projects[p["id"]] = {"title": p["title"], "description": p["description"]}
    json.dump(projects, open(PROJECTS, "w", encoding="utf-8"), indent=1, sort_keys=True, ensure_ascii=False)

for f in optional:
    meta = entries[f]
    p = projects.get(meta["update"].get("modrinth", {}).get("mod-id"))
    if p:
        meta["name"] = p["title"]
    meta["option"] = {"optional": True, "default": not info[f]["ids"] & OFF_BY_DEFAULT,
                      "description": p["description"] if p else meta["name"]}


# ---- writing the pack ---------------------------------------------------------------------

def build(name):
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
        subprocess.run([CFG["packwiz"], "init", "--name", p["name"], "--author", p["author"], "--version", "1.0.0",
                        "--mc-version", p["minecraft"], "--modloader", "neoforge", "--neoforge-version", p["neoforge"],
                        "-y"], cwd=root, check=True, capture_output=True)

    hosted = []
    for f in jars:
        if entries[f]:
            write_metafile(os.path.join(root, "mods", os.path.splitext(f)[0] + ".pw.toml"), entries[f])
        else:
            shutil.copy2(os.path.join(MODS, f), os.path.join(root, "mods", f))
            hosted.append(f)

    for top in CFG["pack_dirs"]:
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
    print(f"{name}: {len(jars)} mods, {len(optional)} optional "
          f"({len([f for f in optional if f in OFF_BY_DEFAULT or info[f]['ids'] & OFF_BY_DEFAULT])} off by default), "
          f"{len(hosted)} hosted here: {', '.join(hosted) or 'none'}")


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


build("pack")
