# Dai-2 Alpha English Patch & Spreadsheet Editor

Translate **Dai-2-Ji Super Robot Taisen Alpha** (`第2次スーパーロボット大戦α`)
for PlayStation 2 from a local spreadsheet, then build a playable ISO or a
shareable xdelta patch. The target is the Japanese **SLPS-25228** release.

Compare the Japanese with the existing machine translation, write your own
English in up to three dialogue pages, and test the result in the game. Your
hand translations replace the machine translation. The game keeps its original
scene order, speakers, portraits, and branching; extra pages finish before the
next original entry advances.

**[Download the editable ZIP](https://github.com/MiLO83/dai2-alpha-english-patch/raw/refs/heads/main/release/dai2-alpha-english-editable-patch.zip)**
· **[ZIP checksum](release/dai2-alpha-english-editable-patch.zip.sha256)**
· **[Tutorial](#tutorial-from-one-edit-to-a-playable-iso)**
· **[Technical project map](docs/PROJECT-MAP.md)**

The package supplies the editor, translation tables, build tools, font, and
binary-difference patches. Supply your own clean disc image. No game ISO,
PS2 BIOS, emulator, memory card, or savestate is included.

## What you can edit

The recommended table is [`translation/all-known-game-text.tsv`](translation/all-known-game-text.tsv).
It contains **43,420 known text rows**: 39,911 dialogue strings, 3,508 UI strings,
and one tracked title/prologue entry. These are extracted strings, not a claim
that every line has been professionally translated or that every screen is
editable. Machine-translated text remains a draft for human review.

The browser shows five text columns, with a small **Scope** field beside them:

| Text column | Browser label | Saved TSV header | Purpose |
| --- | --- | --- | --- |
| 1 | Original Japanese | `Original Japanese` | Source lookup key and reference. Keep it unchanged. |
| 2 | Machine Translation (Eng) | `Automatic Translation` | Fallback when all hand-translated cells are empty. |
| 3 | Hand Translated 1 | `English` | First optional human-written page. |
| 4 | Hand Translated 2 | `English Page 2` | Second optional human-written page. |
| 5 | Hand Translated 3 | `English Page 3` | Third optional human-written page. |

**The first nonempty hand-translated cell replaces the original entry.** Any
remaining nonempty hand-translated cells follow in column order. Empty cells,
including whitespace-only cells, do not produce a box. If all three are empty,
the builder selects column 2; if that is empty too, it keeps the Japanese.

| Hand Translated 1 | Hand Translated 2 | Hand Translated 3 | Pages played for this original entry |
| --- | --- | --- | --- |
| A | B | C | A → B → C |
| A | empty | C | A → C |
| empty | B | C | B → C |
| empty | empty | C | C |
| empty | empty | empty | Machine translation, or Japanese if unavailable |

This selection runs at the entry's existing place in the scenario. Spreadsheet
sorting and filtering do **not** change game order. A shared Japanese dialogue
string can occur in several scenes; editing its row affects its mapped
occurrences, rather than just one scene.

Three-page insertion is for **dialogue**. UI names, menus, statistics, and
other fixed fields use Hand Translated 1 and retain their individual byte
limits. Extra-page cells are disabled for non-dialogue rows. The `title` scope
is a translation reference; the editor does not currently insert those rows.

## Dual-tile encoding: is it really 6× the text?

**Up to 6× the character-position capacity of one full-width page is the
right theoretical comparison. It is not a sixfold allowance for every string.**

The font uses 18×18-pixel tiles. The project's whole-page DTE encoding puts two
English characters into one tile, each in a 9×18-pixel half. For example,
`Launch` is encoded as the pairs `La`, `un`, and `ch`: three tiles instead of
six full-width Latin tiles. Each pair is represented by one two-byte glyph code.
The matching pair images are rebuilt into the game's font atlas.

| Layout | Calculation | Nominal character positions |
| --- | --- | ---: |
| One full-width reference page | 22 tiles × 3 lines × 1 character | 66 |
| One English DTE page | 22 tiles × 3 lines × 2 characters | 132 |
| Three English DTE pages | 132 × 3 pages | 396 |

Thus **2 characters per tile × 3 pages = 6×** the nominal capacity of one
full-width page. The editor's working limit is **44 English characters per
line, three lines per page, up to three pages per original entry**. It is
396 characters across three boxes, not 396 characters in one box.

Actual space also depends on speaker text, full-width dialogue delimiters,
line wrapping, control codes, and the source entry's available allocation.
Odd-length visible segments receive a padding space during pairing. Not every
Japanese entry originally fills 66 cells, and character count is not a measure
of translation completeness. The first page must fit a safe text slot in its
scenario member. Extra pages share a finite resident payload area, so the
builder can also reject a spreadsheet with too many inserts overall. The
available DTE glyph bank is finite too.

Use ordinary printable ASCII English and punctuation inside the preserved
dialogue structure. Smart quotes, emoji, and accented letters are not supported
by the whole-page pair encoder. You type readable English; the builder assigns
the pairs and regenerates the matching font automatically. Do not mix font,
scenario, or executable files from different builds.

## Requirements and quick start

The supplied launchers target **Linux x86-64 or Ubuntu under Windows WSL**.
They use Bash, Python **3.10 or newer**, Python venv/pip support, and standard
Linux utilities. The bundled xdelta3 executable is Linux x86-64; this is not a
native Windows batch-file or macOS build workflow.

A current Chromium-based browser provides direct **Save** and **Save As**.
Other browsers can use the editor and download the saved TSV. The first ISO
build creates `work/editor-venv/` and installs Pillow for font rendering, so it
needs internet access for that dependency. Viewing and editing use only the
local Python server and your browser; no account or translation service is
required. Keep roughly **20 GB free** for the source, output, and intermediate
ISO copies; retained checkpoints need additional space.

From an extracted package or repository checkout:

```sh
# Ubuntu/WSL prerequisites, if not already installed:
sudo apt install python3 python3-venv python3-pip

mkdir -p original
# Copy your clean SLPS-25228.iso into original/ before building.
./tools/run-tsv-editor.sh
```

Open **[http://127.0.0.1:8765/](http://127.0.0.1:8765/)** if a browser does not
open automatically. In WSL, open that address in your Windows browser. Keep
the launcher terminal running. Click **Open TSV** and select
`translation/all-known-game-text.tsv` from this same package or checkout.

If an archive extractor drops execute permissions, restore them with:

```sh
chmod +x tools/*.sh tools/xdelta3
```

## The stock ISO and its SHA-256

The builder requires this exact clean source image:

| Property | Required value |
| --- | --- |
| Game serial | `SLPS-25228` |
| Volume label | `SLPS_25228` |
| Size | **2,501,378,048 bytes** |
| Default path | `original/SLPS-25228.iso` |
| SHA-256 | `1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd` |

SHA-256 is a fingerprint of the **entire file's bytes**. Matching the filename,
serial, or file size alone is not enough. Renaming another disc image cannot
make it compatible. A different pressing, a modified ISO, or a damaged dump
can have a different hash; support for a reissue is not implied by the title.

Check your dump on Linux/WSL:

```sh
sha256sum original/SLPS-25228.iso
```

Or in Windows PowerShell, from a directory containing your `original` folder:

```powershell
Get-FileHash .\original\SLPS-25228.iso -Algorithm SHA256
```

Uppercase and lowercase hexadecimal represent the same digest. If it differs,
use a matching clean dump before continuing. The builder checks the full-image
hash and verifies the extracted executable, scenario, and font extents. It
writes a separate output ISO and leaves the clean source intact. Keep custom
output paths different from the source path.

Do not compare an English output ISO with the stock hash: edits necessarily
change it. Build logs print the output checksum. The separately bundled v25
patch has its own fixed patch/output hashes in [`patches/README.md`](patches/README.md).

## Tutorial: from one edit to a playable ISO

### 1. Find a dialogue entry

Launch the editor, open the combined TSV, choose the `dialogue` scope, and
filter by Japanese or English text. Read both reference cells before editing.
The first two text panes each take approximately one quarter of the text area;
the three green hand-translation panes share the other half.

The Japanese cell is the lookup key, even though the browser allows editing
it. Keep it intact, and keep the saved TSV headers unchanged. An entry may
appear more than once in the game.

### 2. Write the replacement

Enter your English into **Hand Translated 1**. For a hypothetical source entry
with `「…」` delimiters and no `$` codes, a three-page edit could be:

| Hand Translated 1 | Hand Translated 2 | Hand Translated 3 |
| --- | --- | --- |
| `「All units, prepare to launch!」` | `「Protect the transport until it leaves.」` | `「Then regroup at the rendezvous point.」` |

These are illustrative lines, not a replacement for an arbitrary source row.
Keep that row's required speaker structure, `「` and `」` delimiters, and `$`
control-code sequence in **each** nonempty page. Follow the source rather than
adding delimiters to a row that has none. Do not copy this example over a row
with different control codes.

### 3. Fit up to three pages

Each green cell is one box. Keep to three lines and 44 English characters per
line, allowing room for the surrounding dialogue structure. As you type past
the limit, the editor wraps whole words and carries overflow into the next
hand-translation cell. If the third cell overflows, excess text is preserved
and flagged so you can shorten it. Review all three cells after a long paste.

Empty cells are skipped. For a two-page replacement, use two cells and leave
the other blank. To return to the machine translation, clear **all three**.
A blank Hand Translated 1 alone does not restore the machine translation if
Hand Translated 2 or 3 still contains text.

### 4. Save your work

Click **Save** to update the opened TSV, or **Save As** for a checkpoint.
If the browser downloads a file instead, put that saved copy somewhere you can
find and reopen it. **Recovery autosave** is an optional browser-local draft;
it does not replace saving your spreadsheet to disk.

**Generate ISO** uses the current in-memory table, including unsaved edits
if you accept its prompt. Building does not save those edits into the TSV you
opened. The helper keeps its latest submitted build input separately at
`work/web-editor/current-translation.tsv`.

### 5. Generate the ISO

Click **Generate ISO** and read the build log. The builder validates your
source image and text, allocates DTE pairs, builds the font and text data, and
installs the extra-page hook when needed. The result is:

```text
build/SLPS-25228-English-web-edited.iso
```

The editor's build also preserves the bundled release's native English title
logo and five English intro cards. A later editor build replaces the same
output file. Copy a successful checkpoint elsewhere if you want to retain it.
Run one build at a time, including builds launched from a terminal, because
they share intermediate files.

### 6. Check it in the game

Boot the newly generated ISO in PCSX2 or on your PS2 setup. Use a fresh boot
and, if needed, an ordinary in-game save. An emulator savestate from an older
build can restore the old executable, font, and resident page data.

At the edited entry, verify the sequence:

```text
Previous original entry
    → Hand Translated 1
    → Hand Translated 2, if nonempty
    → Hand Translated 3, if nonempty
    → Next original entry
```

Check the speaker, portrait, wrapping, punctuation, and scene transitions.
Each completed inserted box should take **one normal advance press**, just
like an original box. The hook does not add a separate confirmation box.
Normal text-reveal behavior still belongs to the game. The ordering fix has
been reported working in this project's user testing; that is not exhaustive
coverage of all routes or hardware.

The repository's `run-pcsx2.sh` is a convenience launcher for an optional local
development installation under `work/pcsx2/`. PCSX2 and its BIOS are not bundled
with the editable package; use your own configured emulator installation.

### 7. Make a patch to share

Click **Generate Patch**. This rebuilds from the current table, then encodes
the difference against the verified stock ISO:

```text
build/SLPS-25228-English-web-edited.xdelta
```

Share the xdelta, its printed SHA-256, the expected stock ISO hash, and any
translation notes. To apply a custom editor-generated patch with the bundled
tool, from the package directory:

```sh
mkdir -p build
./tools/xdelta3 -d -s original/SLPS-25228.iso \
  build/SLPS-25228-English-web-edited.xdelta build/my-custom-english.iso
```

Use a new output filename, and verify the stock hash yourself before this raw
xdelta command. `apply-full-game-patch.sh` is specifically for the bundled v25
baseline and its fixed expected output hash; it is not the custom-patch installer.

### 8. Keep iterating

Save the TSV, rebuild, fresh-boot, and review the actual scene. Keep notes for
awkward line breaks, inconsistent names, repeated strings, and mistranslations.
A successful build proves structural checks passed; it does not prove the
English meaning is right or that every scene was exercised.

## Command-line equivalents

Run these from the project/package directory:

```sh
# Same visual baseline and editable workflow as Generate ISO:
./tools/build-web-edited-iso.sh

# Same workflow as Generate Patch:
./tools/build-web-edited-patch.sh

# Custom spreadsheet, source, and output:
./tools/build-web-edited-iso.sh translation/all-known-game-text.tsv \
  original/SLPS-25228.iso build/my-translation.iso

# Apply only the bundled v25 patch, without spreadsheet edits:
mkdir -p build
./tools/apply-full-game-patch.sh original/SLPS-25228.iso build/english-v25.iso
```

`build-edited-iso.sh` is the lower-level spreadsheet-only builder. It creates
`build/SLPS-25228-English-edited.iso` and does not add the web wrapper's visual
baseline. It refuses an existing output unless `--force` is passed as argument
four. Prefer `build-web-edited-iso.sh` for the complete editor experience.

For an alternative server port:

```sh
./tools/run-tsv-editor.sh --port 8766 --no-browser
# Open http://127.0.0.1:8766/
```

## Troubleshooting and current limits

| Symptom | What to check |
| --- | --- |
| Browser does not open | Open the printed localhost URL yourself; keep the server terminal running. |
| Generate buttons fail from a local HTML file | Launch `run-tsv-editor.sh` and use its HTTP URL. File-only viewing has no build helper. |
| Source ISO missing or wrong hash | Put the matching clean image at the expected path; compare SHA-256, not just the name. |
| Control codes or dialogue delimiters differ | Restore the source's required sequence in every nonempty manual page. |
| A box exceeds three lines or 44 characters | Shorten it or split it across the remaining green cells. |
| Manual occurrence could not be inserted | Check `work/editor-build/editable-build-report.tsv`; the first page still needs a safe scenario text slot. |
| UI translation cannot fit | Shorten Hand Translated 1; UI fields do not gain extra dialogue boxes. See `editable-ui-build-report.tsv`. |
| No unique dialogue command | That occurrence cannot be safely extended by the current inserter; use one page or investigate its record. |
| Resident payload or glyph-bank capacity exceeded | Reduce inserts or revise text; three pages per row is not unlimited total storage. |
| Old text, wrong font, or old page order after a rebuild | Boot the correct new ISO from a fresh emulator session, without restoring an old savestate. |
| Title-scope edits have no effect | These rows are not inserted by the current editor pipeline; native title/intro art comes from the baseline patch. |

Automatic text that is invalid or cannot fit may fall back to Japanese. Failed
manual insertion stops the build instead of silently claiming success. The UI
fit counter is a guide; the encoder and build reports are authoritative.

## How the build works

1. Select nonempty hand translations in order, otherwise machine English,
   otherwise Japanese; keep dialogue and UI editing scopes distinct.
2. Verify the source ISO and extract clean executable, font, and scenario data.
3. Assign whole-page DTE pairs while protecting glyphs still used by Japanese,
   numeric fields, lookup tables, punctuation, and name entry.
4. Fit first-page scenario text into existing overlay-local slots and update
   its pointers. Build the matching font and fixed-field UI translations.
5. Resolve each extended entry's original dialogue command and store extra
   command copies/text in a resident executable segment. The completion hook
   follows the active queued or sequential command, holds it through its extra
   pages, then restores and advances the original sequence. A member-name check
   distinguishes scenarios that reuse RAM addresses.
6. Overlay those same-sized files onto the bundled visual baseline and write
   the output ISO. Generate Patch additionally creates an xdelta difference.

The active workflow does **not** grow STAGE.BIN or use the older experimental
continuation/overlay-expansion scripts. See
[`docs/DIALOGUE-PAGES.md`](docs/DIALOGUE-PAGES.md) for the ordering fix and
[`docs/PROJECT-MAP.md`](docs/PROJECT-MAP.md) for file roles and historical tools.

## Validation and redistribution

Run the dialogue selection, box-limit, and MIPS ordering tests:

```sh
python3 -m unittest discover -s tools -p 'test_dialogue_pages.py' -v
```

Rebuild the editable ZIP with:

```sh
python3 tools/package_editable_patch.py
sha256sum -c release/dai2-alpha-english-editable-patch.zip.sha256
```

The package contains a `SHA256SUMS` inventory for its files and a separate ZIP
checksum beside the download. Its manifest excludes the private `original/`,
`work/`, and `build/` directories, game images/extracted binaries, and emulator
state. The supplied TSVs and original patch differences are the editable
project materials; no full disc image is distributed.

Ubuntu Sans Mono's notices are under [`assets/`](assets/). The bundled xdelta3
binary's notices and corresponding Debian source archives are under
[`third_party/xdelta3/`](third_party/xdelta3/). Retain these with redistributions.
The game and its associated properties belong to their respective owners;
this is an independent fan translation project.
