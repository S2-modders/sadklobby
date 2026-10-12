# The mods a player of this lobby server needs, each built into build/<name>/ as the folder to copy to
# <game>\mods\<name>\. The rules are sadkmod's (mods.mk); SADKMOD is the path to a sadkmod checkout (the submodule).
#   make          every mod (builds sadkmod first)
#   make verify   checks every mod's patches against a DRM-free SADK.exe under Wine (SADK_EXE=<path>)
#   make test     assetshare's archive format under Wine
SADKMOD ?= ../sadkmod
include $(SADKMOD)/mods.mk

build/test_archive.exe: tests/test_archive.cpp assetshare/archive.cpp assetshare/archive.hpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) -static -o $@ tests/test_archive.cpp assetshare/archive.cpp

test: build/test_archive.exe
	WINEDEBUG=-all wine build/test_archive.exe

.PHONY: test
