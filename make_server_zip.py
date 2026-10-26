"""Build the server zip from the Prism instance, as set in packsync.json.

  mods/      every enabled mod that isn't client-only, plus server_extra_mods (e.g. Chunky)
  config/    the pack's configs (minus "exclude"; client-only configs are harmless on a server)
  README.txt, user_jvm_args.txt   from server/

Usage: python make_server_zip.py      (writes server_zip, normally the Desktop)
"""
import fnmatch, hashlib, json, os, tomllib, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "packsync.json"), encoding="utf-8"))
GAME = os.path.join(CFG["instance"], "minecraft")
MODS = os.path.join(GAME, "mods")
CLIENT_ONLY = set(CFG["client_only_mods"])
DOWNLOADS = os.path.join(os.environ.get("TEMP", HERE), "bop3-server-extras")


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


def extra_jar(mod):
    """Path to a server_extra_mods jar, downloaded once and checked against its sha512."""
    os.makedirs(DOWNLOADS, exist_ok=True)
    path = os.path.join(DOWNLOADS, mod["file"])
    if not os.path.exists(path) or hashlib.sha512(open(path, "rb").read()).hexdigest() != mod["sha512"]:
        req = urllib.request.Request(mod["url"], headers={"User-Agent": "best-of-pack-3 server zip"})
        data = urllib.request.urlopen(req).read()
        if hashlib.sha512(data).hexdigest() != mod["sha512"]:
            raise SystemExit(f"{mod['file']}: download doesn't match its sha512 in packsync.json")
        open(path, "wb").write(data)
    return path


jars = sorted((f for f in os.listdir(MODS) if f.endswith(".jar")), key=str.lower)
server = [f for f in jars if not (mod_ids(os.path.join(MODS, f)) and mod_ids(os.path.join(MODS, f)) <= CLIENT_ONLY)]
extras = [(m["file"], extra_jar(m)) for m in CFG["server_extra_mods"]]
count = len(server) + len(extras)

out = CFG["server_zip"]
tmp = out + ".tmp"
root = "best-of-pack-3-server/"
with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in server:
        z.write(os.path.join(MODS, f), root + "mods/" + f)
    for name, path in extras:
        z.write(path, root + "mods/" + name)
    for top in ("config", "defaultconfigs"):
        for dirpath, _, files in os.walk(os.path.join(GAME, top)):
            for f in files:
                full = os.path.join(dirpath, f)
                rel = os.path.relpath(full, GAME).replace(os.sep, "/")
                if not any(fnmatch.fnmatch(rel, p) for p in CFG["exclude"]):
                    z.write(full, root + rel)
    readme = open(os.path.join(HERE, "server", "server-README.txt"), encoding="utf-8").read()
    z.writestr(root + "README.txt", readme.replace("{mod_count}", str(count)))
    z.write(os.path.join(HERE, "server", "user_jvm_args.txt"), root + "user_jvm_args.txt")
with zipfile.ZipFile(tmp) as z:
    bad = z.testzip()
if bad:
    raise SystemExit(f"{tmp}: corrupt entry {bad}")
os.replace(tmp, out)
print(f"wrote {out}: {count} mods ({', '.join(n for n, _ in extras)} server-only), "
      f"{os.path.getsize(out) / 1e6:.0f} MB")
