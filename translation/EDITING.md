# Editing the game script

The recommended spreadsheet is `all-known-game-text.tsv`, which combines all
known scenario, UI, database, and title-card strings. `glyph-byte-table.tsv`
is the accompanying Japanese CP932 and English DTE byte/index reference.
Its `Scope` column must remain `dialogue`, `ui`, or `title`. The other columns
are the Japanese source, automatic English, and three user-reviewed English
page fields.

For a local graphical editor, run `./tools/run-tsv-editor.sh`. It provides
equal-width translation columns, direct open/save, recovery autosave, unsaved
exit warnings, filtering and paging, plus buttons to build an ISO and generate
an xdelta. See `TSV-EDITOR-README.md` for the complete workflow.

Open `all-known-game-text.tsv` (recommended), or the older domain-specific
`game-script.tsv` (scenario dialogue) and `ui-script.tsv` (menus,
databases, names, descriptions, and executable messages) as UTF-8
tab-separated files in LibreOffice Calc, Excel, or a text editor. Both contain
five translation columns (plus `Scope` in the combined table):

1. `Original Japanese` identifies the game string and should not be edited.
2. `Automatic Translation` contains the current machine-translated text.
3. `English` is for reviewed or rewritten text.
4. `English Page 2` is an optional inserted dialogue page.
5. `English Page 3` is an optional final inserted dialogue page.

For each table, the ISO builder chooses `English` when it is non-empty, otherwise
`Automatic Translation`, otherwise it leaves the original Japanese string in
the game. Spaces alone count as an empty cell.

Keep `$` control codes, line breaks, and the `「」` dialogue delimiters in the
same order as the Japanese cell. Dialogue supports at most three lines and 44
ASCII characters per line in all-DTE mode. The builder validates manual rows
and points to a detailed report if a manual edit cannot be inserted.

Pages 2 and 3 are dialogue-only. They clone the original record so the same
speaker, portrait, and event metadata is retained, and the game continues to
the original next record after the final inserted page. The builder expands
the affected overlay and relocates STAGE.BIN in the ISO; it does not impose the
original file-size ceiling. A record that cannot be identified safely causes
the build to stop.

From the repository root, build with the defaults:

```sh
./tools/build-edited-iso.sh
```

This reads both translation tables and the verified clean
`original/SLPS-25228.iso`, then creates
`build/SLPS-25228-English-edited.iso`.

Custom paths may be supplied in table, source ISO, output ISO order:

```sh
./tools/build-edited-iso.sh translation/game-script.tsv original/SLPS-25228.iso build/my-edit.iso
```

An existing output is never overwritten unless `--force` is added as the
fourth argument. Intermediate DTE, font, stage, executable, and validation files are kept
under `work/editor-build/`.

The UI occurrence locations and fixed field capacities are stored separately
in `data/ui-occurrences.tsv`. Do not edit offsets there. UI strings which do
not fit their field after all-DTE encoding are left Japanese and listed as
`overflow` in `work/editor-build/editable-ui-build-report.tsv`.

`title-script.tsv` tracks title/prologue cards discovered during testing. Some
of these are compressed, indexed, or graphical rather than plain executable
strings. Rows whose metadata status is `runtime-address-required` are retained
for translation but are not patched until their runtime representation has
been mapped safely.

To deliberately regenerate the table from the current automatic translation
(this erases column-three edits), run:

```sh
work/editor-venv/bin/python tools/editable_translation.py export --force
```
