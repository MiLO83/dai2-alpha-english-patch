# Dai-2 Alpha English editable patch package

This package contains no game ISO or extracted game binaries. You must supply
your own unmodified Japanese `SLPS-25228` disc image.

## Quick start

For the graphical workflow, run `./tools/run-tsv-editor.sh`, then open the TSV
and use **Apply Patch** or **Generate Patch**. See `TSV-EDITOR-README.md`.

For the command-line workflow:

1. Put the clean disc image at `original/SLPS-25228.iso`.
2. Edit `translation/all-known-game-text.tsv` as a UTF-8 tab-separated
   spreadsheet. It combines every known dialogue, UI, database, and title-card
   string.
3. Put reviewed English in `English`; optional `English Page 2` and
   `English Page 3` cells insert sequential dialogue pages. `Scope` keeps
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
structurally verified release candidate without spreadsheet edits. Gameplay
testing in PCSX2 is still encouraged before treating a checkpoint as final.
The current patch targets v25 and includes the native English title logo,
five English intro cards, Hero Setup layout corrections, translated operation
summary labels, and the latest Pilot Skills cleanup.
The spreadsheet builder uses the gameplay-tested overlay-local pointer-swap
method for Page 1. Optional Pages 2 and 3 clone validated dialogue records,
expand the affected PS2 overlay allocation, and relocate STAGE.BIN through its
ISO9660 directory entry. Executable UI fields remain fixed-width.
