#!/usr/bin/env bash
# Assembles release/ for a GitHub release (zip its contents):
#   release/SAdK-ServerConfig.exe   the players' setup tool (embeds the shim and the mods below)
#   release/mods/<name>/            gamebridge, assetshare and billboards, to copy into <game>\mods by hand
#   release/LICENSE
#   release/server/                 the Python server, WITHOUT the game's msgdefs.ini, + a quick guide
# SADKMOD names the sadkmod checkout to build against (default: the submodule).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$REPO/release"
export SADKMOD="${SADKMOD:-$REPO/sadkmod}"
RELEASE_MODS="gamebridge assetshare billboards"

# Plain make: the Makefiles track their dependencies. (make -B rebuilds sadkmod's precompiled header from several
# sub-makes at once, which corrupts it.)
make -C "$SADKMOD/shim"
make -C "$REPO/mods"
make -C "$REPO/setup"

rm -rf "$OUT"
mkdir -p "$OUT/server"
cp "$REPO/setup/SAdK-ServerConfig.exe" "$OUT/"
cp "$REPO/LICENSE" "$OUT/"
mkdir -p "$OUT/mods"
for m in $RELEASE_MODS; do cp -r "$REPO/mods/build/$m" "$OUT/mods/"; done
cat > "$OUT/mods/INSTALL.txt" <<'TXT'
The mods a player of this lobby server needs. SAdK-ServerConfig.exe installs them by itself, together with the
mod loader (bin\wsock32.dll); these folders are for installing by hand. They need the DRM-free SADK.exe.

By hand: copy the folders in here into the game's "mods" folder (create it next to "bin" and "data"), so that
you get e.g. ...\Die Siedler - Aufbruch der Kulturen\mods\gamebridge\mod.dll

  gamebridge      hosting from behind a router, through the lobby server (gamebridge.ini)
  assetshare      shares a match's map and the host's server mods with the joiners; every player needs it
  billboards      plain screens on the lobby's advertising billboards (billboards.ini)

To switch a mod off, remove its folder or rename it so that it starts with "_".
More mods and how to write one: https://github.com/S2-modders/sadkmod
TXT

# The package's tracked .py files (working-tree contents), minus the game's msgdefs.ini: players
# supply their own copy.
(cd "$REPO" && git ls-files sadk_lobby | grep '\.py$') | while read -r f; do
    mkdir -p "$OUT/server/$(dirname "$f")"
    cp "$REPO/$f" "$OUT/server/$f"
done
mkdir -p "$OUT/server/sadk_lobby/data"
cat > "$OUT/server/sadk_lobby/data/PUT_MSGDEFS_INI_HERE.txt" <<'TXT'
Copy msgdefs.ini from the bin folder of your game installation into this folder.
The server reads the game's own message definitions from it and will not start without it.
TXT
cp "$REPO/requirements.txt" "$OUT/server/"
cp "$REPO/packaging/server-README.md" "$OUT/server/README.md"
cp "$REPO/LICENSE" "$OUT/server/"

if find "$OUT" -iname 'msgdefs.ini' | grep -q .; then
    echo "msgdefs.ini ended up in the release — aborting" >&2
    exit 1
fi
echo "release/ assembled:"
(cd "$OUT" && find . -type f | sort | sed 's/^/  /')
