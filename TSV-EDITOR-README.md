# Dai-2 Alpha local TSV editor

This is a local browser interface for editing the complete translation table,
building a test ISO, and generating an xdelta patch. Nothing is uploaded.

## Start the editor

From the project directory in Linux or WSL:

```sh
./tools/run-tsv-editor.sh
```

Open `http://127.0.0.1:8765/` if the browser does not open automatically.
Keep the terminal open while using **Apply Patch** or **Generate Patch**.

## Edit and save

1. Click **Open TSV** and select `translation/all-known-game-text.tsv`.
2. Edit the three green **Your English** page columns. Japanese and automatic
   English each receive 25% of the row; pages 1, 2, and 3 divide the remaining
   50% equally. All five text cells stay visible side-by-side.
3. Keep ordinary dialogue in Page 1 when it fits. If typing crosses the
   three-line, 44-character-per-line display limit, the editor moves the final
   whole word into Page 2, then Page 3. Extra pages are disabled for UI rows.
4. Use filtering, scope selection, paging, and vertically resizable cells to
   navigate the large table without loading 43,000 HTML rows simultaneously.
5. Click **Save** to update the opened file or **Save As** for a new copy.

Chromium-based browsers support direct Save/Save As. Other browsers fall back
to downloading a TSV. Recovery autosave uses private browser storage and asks
before enabling or restoring it. Browsers control the wording of the final
unsaved-exit warning; use Save before closing whenever possible.

## Apply Patch

Place your verified clean disc image here first:

```text
original/SLPS-25228.iso
```

Click **Apply Patch**. The editor sends the current in-memory spreadsheet only
to the localhost helper, which validates it and runs the existing DTE builder.
Progress appears in the build-log window. The result is:

```text
build/SLPS-25228-English-web-edited.iso
```

The builder recreates the current tested release as its visual baseline, then
overlays the spreadsheet-generated scenario data, executable UI, and matching
DTE font. The custom native English title logo and five line-aligned English
intro cards are therefore retained in every editor-built ISO.

The source ISO is verified and never modified. The output ISO is replaced on a
subsequent build, so move a checkpoint elsewhere if you want to retain it.

When Page 2 or Page 3 is populated, the builder clones only positively
identified 24-byte dialogue records, retaining their speaker/portrait/control
metadata. It expands the affected overlay allocation and relocates STAGE.BIN
through its ISO9660 directory record. After the final inserted page, playback
continues at the same original next dialogue record. Identical inserted page
bytes are stored once per overlay. Unsafe or non-dialogue page requests stop
the build with an error instead of producing a risky ISO.

## Generate Patch

After a successful ISO build, click **Generate Patch**. It produces:

```text
build/SLPS-25228-English-web-edited.xdelta
```

The log reports the complete path and SHA-256 checksum. This xdelta contains
only differences and does not contain the original disc image.

## Stop the editor

Save your spreadsheet, close the browser tab, then press `Ctrl+C` in the
launcher terminal.
