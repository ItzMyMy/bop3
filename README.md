# best of pack 3

An auto-updating Prism pack, built with [packwiz](https://packwiz.infra.link). The pack itself is in `pack/`.

## Playing

In Prism: *Add Instance → Import*, and paste this link (or download the zip and pick it):

`https://github.com/ItzMyMy/bop3/raw/main/best-of-pack-3-autoupdate.zip`

On the first launch a window lists the optional client mods (shaders support, Distant Horizons, sound and
animation mods, HUD tweaks…), all ticked. Untick any you don't want; the choice is remembered. To change it
later, click the options button in the installer window while it checks for updates at launch.
Later launches download only what changed.

## Updating the pack (for ItzMyMy)

1. Change the pack in Prism as usual: add, remove or update mods, edit configs. Close the game first.
2. Run `python sync_from_prism.py`. It rebuilds `pack/` from the instance.
3. Bump `version` in `pack/pack.toml` (optional, shown to players).
4. Commit and push (GitHub Desktop, or `git add -A`, `git commit -m "..."`, `git push`).

The import zip only needs remaking when the instance settings or Minecraft/NeoForge version change:
run `python make_import_zips.py` and push.

Settings are in `packsync.json`:

- `client_only_mods`: mod ids that only run on the client. Add new client-only mods here.
- Client-only mods become optional checkboxes, except mods another mod needs (they'd crash the game if
  unticked alone), jars hosted in this repo, and `keep_required` (Sodium and performance mods).
  `optional_off_by_default` lists ids that start unticked.
- `preserve`: files players keep their own copy of (video, keybinds, HUD, sound settings…).
  They are installed once and never overwritten. Every other file is replaced whenever it changes here.
- `exclude`: files that never go in the pack (backups, caches, downloaded programs).

Mods without Prism metadata are looked up on Modrinth by hash (`modrinth-matches.json`); mods that
aren't on Modrinth are hosted in this repo as jars. Checkbox titles and descriptions come from Modrinth
(`modrinth-projects.json`).
