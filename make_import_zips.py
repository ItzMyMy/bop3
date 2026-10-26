"""Make the Prism import zip: instance settings + packwiz-installer-bootstrap.jar + a pre-launch command
that installs and updates the pack from GitHub on every launch. No mods inside; the first launch downloads them.

Usage: python make_import_zips.py   (needs "raw_base" in packsync.json)
Writes best-of-pack-3-autoupdate.zip next to this script, so once pushed it downloads from
github.com/<user>/<repo>/raw/main/<zip> (also usable in Prism's Import from URL).
"""
import json, os, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "packsync.json"), encoding="utf-8"))
INSTANCE = CFG["instance"]
BOOTSTRAP = os.path.join(os.path.dirname(CFG["packwiz"]), "packwiz-installer-bootstrap.jar")
OUT = HERE
KEEP = {"ConfigVersion", "iconKey", "InstanceType", "OverrideMemory", "MaxMemAlloc", "MinMemAlloc", "PermGen"}


def instance_cfg(name, pack_url):
    """Name/icon/memory from the real instance, plus the installer as the pre-launch command."""
    out, section = ["[General]"], None
    for line in open(os.path.join(INSTANCE, "instance.cfg"), encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("["):
            section = line
        elif section == "[General]" and "=" in line and line.split("=", 1)[0] in KEEP:
            out.append(line)
    command = f'"$INST_JAVA" -jar packwiz-installer-bootstrap.jar {pack_url}'
    out += [f"name={name}", "AutomaticJava=true", "OverrideJavaLocation=false",
            "OverrideCommands=true", "PreLaunchCommand=" + json.dumps(command)]
    return "\n".join(out) + "\n"


for folder, name, zip_name in (("pack", "best of pack 3", "best-of-pack-3-autoupdate.zip"),):
    url = f"{CFG['raw_base'].rstrip('/')}/{folder}/pack.toml"
    path = os.path.join(OUT, zip_name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("instance.cfg", instance_cfg(name, url))
        z.write(os.path.join(INSTANCE, "mmc-pack.json"), "mmc-pack.json")
        for extra in ("icon.ico", "icon.png", "bestofpack2.jpg"):
            p = os.path.join(INSTANCE, extra)
            if os.path.exists(p):
                z.write(p, extra)
        z.write(BOOTSTRAP, "minecraft/packwiz-installer-bootstrap.jar")
    print(f"wrote {zip_name} ({os.path.getsize(path) / 1e3:.0f} KB) -> {url}")
