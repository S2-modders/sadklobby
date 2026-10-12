# sadklobby — the true SAdK lobby server

A lobby server for the 2008 game **Die Siedler: Aufbruch der Kulturen** (*The Settlers: Rise of Cultures*,
**SAdK**), whose official servers went offline around 2014. Unmodified game clients log in, meet in the 3D lobby
village and host, join and finish matches. It comes with the mods its players need, among them `gamebridge`:
hosting from behind a router, through the server.

The protocol was reverse-engineered from the game client in
[SAdK-Resurrected](https://github.com/J4n1X/SAdK-Resurrected), which holds the protocol documentation and the
evidence behind it. Statements tagged `[PROVEN]` there have a binary address and live evidence; `[TODO]` marks
what is implemented but not confirmed in the game.

## What is in here

| Folder | What |
|---|---|
| `sadk_lobby/` | the server (Python): login, chat, server list, the lobby village, accounts and characters, tavern minigames, mail, buddies, the match referee, the host bridge |
| `mods/` | the players' side, built on [sadkmod](https://github.com/S2-modders/sadkmod): `gamebridge` (the host bridge's client, `docs/bridge-protocol.md`), `assetshare` (shares a match's map and the host's server mods; every player needs it), `billboards` (plain screens on the village's advertising boards) |
| `setup/` | SAdK-ServerConfig, the players' setup tool: points a game install at a server and installs the mod loader and the three mods |
| `sadkmod/` | submodule: the modding library and the mod loader (`shim/`, a proxy `wsock32.dll`) |
| `packaging/` | `make_release.sh` assembles a release: the setup tool, the mods, the server |
| `tests/` | the server's tests |

## Running the server

The server reads the game's own message schema, which is not distributed with it: copy `bin\msgdefs.ini` from
your game installation to `sadk_lobby/data/msgdefs.ini`.

```bash
pip install -r requirements.txt
export SADK_ADVERTISE_IP=203.0.113.10     # the IP address players reach the server at
python -m sadk_lobby
```

Ports: `7070` lobby, `7071` chat, `5477` village, `5481` referee, `7072` / `7073` host bridge. `packaging/server-README.md` is
the full guide for server operators.

Players run SAdK-ServerConfig, enter the server's address and press Save. The mod loader and the mods need
the DRM-free `SADK.exe` (MD5 `d4832bc5103c14f5445471af29b8d778`); the game's patch level is 9212.

## Building the players' side

Linux, mingw-w64 (`i686-w64-mingw32-g++`, GCC 13 or later), Python 3, Wine for the tests:

```bash
git submodule update --init
make -C mods            # mods/build/<name>/ for each mod (builds sadkmod first)
make -C mods verify     # the mods' patches against a DRM-free SADK.exe (SADK_EXE=<path>)
make -C mods test       # assetshare's archive format
make -C setup           # SAdK-ServerConfig.exe
packaging/make_release.sh
```

`SADKMOD=<path>` builds against another sadkmod checkout than the submodule.

## Tests

```bash
pytest tests/
```

They need `sadk_lobby/data/msgdefs.ini`.

## License

MIT (`LICENSE`). The game's `msgdefs.ini` is not part of this repository and must never be committed.
