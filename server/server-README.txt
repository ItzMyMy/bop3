best of pack 3 - server files
=============================

versions
  minecraft   1.21.1
  neoforge    21.1.264   (the server must be on this exact neoforge build or newer 21.1.x)
  java        21

what's in here
  mods/      {mod_count} mods - everything from the pack that runs on a server
  config/    the pack's config files (client-only config files are harmless on a server)
  user_jvm_args.txt   suggested memory settings

setting up a fresh server
  1. download the neoforge 21.1.264 installer from https://neoforged.net
     and run:   java -jar neoforge-21.1.264-installer.jar --installServer
  2. copy the mods/ and config/ folders from this zip into the server folder
     (next to run.bat / run.sh).
  3. replace the server's user_jvm_args.txt with the one in this zip, or add
     the -Xmx line to it.
  4. bro you know how to run a server

memory
  this is a big pack (create + aeronautics/sable physics + several worldgen mods).
  give the server at least 8 gb. 10-12 gb is better with several players or
  lots of moving contraptions. change -Xmx in user_jvm_args.txt.
sorry brah thats what the boss (big tech) sayz

players
  players must use best of pack 3, not this zip: import
    https://github.com/ItzMyMy/bop3/raw/main/best-of-pack-3-autoupdate.zip
  into prism. it updates itself every launch.
  gameplay choices (/gameplay) needs to be on both the server and the clients;
  it is included here and in the client pack.

notes for the korbs
  - spark is included. if the server lags, run:
      /spark profiler start --timeout 300
    and send the link it gives you after 5 minutes.
  - distant horizons is client-side only now; the server doesn't generate lods.
  - no pollution mods (pollution of the realms, create: smog and airborne are all out).
  - start a fresh world when mods are removed, or their blocks vanish from old chunks.
  - chunky is included (server only) to pregenerate the world, so players load chunks
    instead of generating them. run it once on a new world, from the console or as op:
      chunky radius 5000
      chunky start
    it keeps going after restarts; check with "chunky progress", pause with "chunky pause".
    5000 blocks takes a while (hours with this many worldgen mods); start smaller if needed.
