# SAdK-ServerConfig.exe: the players' setup tool. It embeds the shim (sadkmod's shim/wsock32.dll) and this
# repository's mods. SADKMOD is the path to a sadkmod checkout (the submodule).
CC = i686-w64-mingw32-gcc
WINDRES = i686-w64-mingw32-windres
SADKMOD ?= ../sadkmod
SHIM = $(SADKMOD)/shim/wsock32.dll

SAdK-ServerConfig.exe: main.c res.o
	$(CC) -O2 -s -mwindows -static-libgcc -o $@ main.c res.o -lcomctl32 -lshlwapi -lshell32 -lole32 -ladvapi32

MODS = ../mods/build/billboards/mod.dll ../mods/build/gamebridge/mod.dll ../mods/build/assetshare/mod.dll
MOD_INIS = ../mods/billboards/billboards.ini ../mods/gamebridge/gamebridge.ini ../mods/assetshare/assetshare.ini

# serverconfig.rc names the shim as build/wsock32.dll, wherever SADKMOD is
build/wsock32.dll: $(SHIM)
	@mkdir -p build
	cp $< $@

res.o: serverconfig.rc resource.h serverconfig.manifest sadk.ico build/wsock32.dll $(MODS) $(MOD_INIS)
	$(WINDRES) -O coff -o $@ serverconfig.rc

$(SHIM): FORCE
	$(MAKE) -C $(SADKMOD)/shim

$(MODS): FORCE
	$(MAKE) -C ../mods

FORCE:
.PHONY: FORCE

clean:
	rm -rf SAdK-ServerConfig.exe res.o build
