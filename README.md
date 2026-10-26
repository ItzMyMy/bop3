# best of pack 3

Auto-updating Prism packs, built with [packwiz](https://packwiz.infra.link).

- `full/` – the full pack: every mod, shaders, all resource packs
- `public/` – the lighter pack: mods that run on the server, plus Sodium; no shaders

## Playing

In Prism: *Add Instance → Import*, and paste one of these links (or download the zip and pick it):

- full: `https://github.com/ItzMyMy/bop3/raw/main/best-of-pack-3-autoupdate.zip`
- public: `https://github.com/ItzMyMy/bop3/raw/main/best-of-pack-3-public-autoupdate.zip`

The first launch downloads the pack; later launches download only what changed.
The zips only change when the instance settings or Minecraft/NeoForge version do: then run
`python make_import_zips.py` and push.

## Updating the pack (for ItzMyMy)

1. Change the pack in Prism as usual: add, remove or update mods, edit configs.
2. Run `python sync_from_prism.py`. It rebuilds `full/` and `public/` from the instance.
3. Bump `version` in `full/pack.toml` and `public/pack.toml` (optional, shown to players).
4. `git add -A`, `git commit -m "..."`, `git push`.

Settings are in `packsync.json`:

- `client_only_mods`: mod ids that stay out of the public pack and are marked client-side.
  Add new client-only mods here.
- `preserve`: files players keep their own copy of (video, keybinds, HUD, sound settings…).
  They are installed once and never overwritten. Every other config is replaced whenever it changes here.
- `exclude`: files that never go in the pack (backups, caches, downloaded programs).

Mods without Prism metadata are looked up on Modrinth by hash (`modrinth-matches.json`); mods that
aren't on Modrinth are hosted in this repo as jars.
