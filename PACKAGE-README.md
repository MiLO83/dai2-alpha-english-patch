# Dai-2 Alpha English editable patch package

This package contains no game ISO or extracted game binaries. You must supply
your own unmodified Japanese `SLPS-25228` disc image.

## Quick start

1. Put the clean disc image at `original/SLPS-25228.iso`.
2. Edit `translation/all-known-game-text.tsv` as a UTF-8 tab-separated
   spreadsheet. It combines every known dialogue, UI, database, and title-card
   string.
3. Put reviewed English in the `English` user-override column. `Scope` keeps
   identical Japanese strings in dialogue, UI, and title-card domains separate.
4. Run `./tools/build-edited-iso.sh` from this directory.
5. Open `build/SLPS-25228-English-edited.iso` in PCSX2.

The first run creates an isolated Python environment under `work/` and installs
Pillow for bitmap-font generation. Internet access is therefore needed once.
The builder verifies the source ISO before doing anything, extracts its own
clean working data, rebuilds the all-DTE font, scenario text, and executable
menu/database text, and never modifies the
original image.

Selection priority is reviewed `English`, then `Automatic Translation`, then
unchanged `Original Japanese`. See `translation/EDITING.md` for control-code,
line-width, custom-path, and validation details.

`translation/glyph-byte-table.tsv` documents retail Japanese CP932 glyph
bytes, English DTE pairs, encoded bytes, and known FTALL atlas indices.

`translation/title-script.tsv` also records prologue/title cards. Entries
marked `runtime-address-required` in `data/title-occurrences.tsv` are not yet
inserted by the builder; they require a PCSX2 memory capture while displayed.

`patches/SLPS-25228-English-current.xdelta` directly recreates the current
tested build without spreadsheet edits.
The spreadsheet builder uses the gameplay-tested overlay-local pointer-swap
method. It fits additional scenario translations by reassigning confirmed
pointers among differently sized slots inside the same overlay. Executable UI
fields are patched in place and retain their original fixed allocations.
