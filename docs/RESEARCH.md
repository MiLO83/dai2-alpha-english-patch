# Research notes

## Known identity

The standard Japanese release uses serial `SLPS-25228`; inside an extracted
disc, the boot ELF will normally be named in the `SLPS_252.28` form.

Analyzed source image:

- Volume label: `SLPS_25228`
- Filesystem: hybrid ISO9660/UDF
- Size: `2,501,378,048` bytes
- SHA-256: `1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd`

Do not assume the standard release and `PlayStation 2 the Best` reissue are
binary-compatible. Each supported image must have its own verified digest and
patch.

## Patch format

Classic IPS is not suitable for a PS2 DVD image because its ordinary offset
field is limited to 24 bits. The initial target is `xdelta3`, applied to a
verified clean ISO.

## Unknowns to resolve from the disc

- Exact clean-image size and SHA-256
- ISO filesystem layout
- Container/archive formats and compression
- Scenario and interface text encoding
- Pointer and control-code representation
- Font format and available glyph metrics
- Whether rebuilt files may grow or must remain fixed-size

## Initial disc findings

- The boot ELF is `SLPS_252.28` and is a non-stripped, statically linked,
  little-endian MIPS-III ELF (`3,542,656` bytes).
- `DATA/NAME.BIN` is uncompressed Shift-JIS in 165 fixed-size `0x40`-byte
  records. Records are NUL-terminated and padded with `0xCC`.
- `DATA/FTALL.P04` is `806,400` bytes of packed 4-bpp pixel data. The font
  renderer at `0x00125978` proves that it is a `320x5040` atlas with 18x18
  glyph cells arranged as 16 columns by 280 rows (4,480 addressable slots).
- `DATA/FONTCOL.C16` contains 16 palettes of 16 little-endian 16-bit colors.
- The atlas is neither compressed nor conventionally PS2-swizzled. Each glyph
  occupies 9 packed bytes on each of 18 scanlines, and scanlines have a
  160-byte source stride. The earlier 24x24 and 32x32 interpretations were
  incorrect.

## Font code locations

- `host:data/ftall.p04` is stored at virtual address `0x0042E4E0`.
- `host:data/fontcol.c16` is stored at virtual address `0x0042E500`.
- The font initialization routine begins at `0x00125300`.
- It loads `FTALL.P04` through the file loader at `0x00124150`, stores the
  resulting pointer at `0x004748F0`, and calls the font parser at `0x001254D0`.
- The palette is subsequently loaded and configured with 16 entries.
- A full-width Latin Shift-JIS mapping sequence is embedded immediately before
  the font diagnostics and filenames. In particular, it includes the standard
  `0x8260` through `0x8279` uppercase/lowercase ranges. This confirms that the
  game already maps Latin characters, although their glyph appearance and
  advance widths still need verification.

## Runtime debugger findings

At runtime, the globals beginning at `0x004748D0` contain these pointers:

| Global | Runtime target | Allocation/use |
| --- | --- | --- |
| `0x004748D0` | `0x00FA69D0` | `0x1920`-byte work buffer |
| `0x004748D8` | `0x00FA8300` | `0x1400`-byte work buffer |
| `0x004748F0` | `0x00FE9040` | raw loaded `FTALL.P04` |
| `0x004748F8` | `0x00FA9710` | `0x10000`-byte cache/table |

Memory at `0x00FE9040` matches `FTALL.P04` byte-for-byte at its beginning.
Stepping out of `0x001254D0` returned to `0x0016D628`, following a call at
`0x0016D620`. The observed invocation had `a0 = 0`, and the displayed portion
of `0x00FA9710` did not change. Therefore `0x001254D0` should currently be
described as a recurring font-state/cache routine, not conclusively as the
one-time font decoder or per-glyph bitmap decoder.

The game's English name-entry page visibly renders `A-Z` and `a-z`, confirming
that a usable Latin glyph set and input mapping already exist in the retail
image.

## Stage text extraction

- `DATA/STAGE.BIN` contains 298 `MWo3` overlay records.
- Probable text strings are NUL-terminated CP932 and overwhelmingly begin on
  eight-byte boundaries. Enforcing that alignment removes binary false
  positives found by the initial broad scan.
- The current extraction finds 61,684 occurrences and 39,911 unique strings.
  Identical source strings may have different allocations, so a shared
  translation must fit the smallest occurrence unless occurrences are split.
- Each dump row records its original byte count and maximum in-place encoded
  byte count. These are byte budgets, not Unicode character limits.
- A 12-line `qwen3.5:latest` Ollama pilot showed that model output needs both
  deterministic control-token validation and human review. Isolated masked
  requests preserved token structure in 9 of 12 cases, but romanization and
  meaning were not consistent enough for unattended bulk insertion.
- A subsequent six-line glossary/DTE/byte-feedback pilot preserved the real
  control sequence in all six rows, but only one draft fit its smallest
  in-place allocation. DTE plus concise rewriting will cover some strings,
  but a complete translation will also require understanding and rebuilding
  the stage string references rather than assuming every string stays put.

## Provisional DTE bank

- Byte codes `87A0` through `87FC` are undefined in standard CP932.
- The retail renderer maps this range directly to atlas indices 1248 through
  1340, providing 93 candidate DTE slots.
- Raw occurrences in analyzed binaries were inspected and occur in executable
  instructions or packed data, not the aligned CP932 strings extracted from
  `STAGE.BIN`. The range remains provisional until an in-game encoded-string
  test is completed.

Runtime observation at the `0x001254D0` parser-entry breakpoint:

- `*(uint32_t *)0x004748F0 = 0x00FE9040`: loaded `FTALL.P04` source buffer.
- `*(uint32_t *)0x004748F8 = 0x00FA9710`: probable 64 KiB font work/cache buffer.
- Parser argument `a0` is zero on the observed initialization call, so it is
  likely a mode or starting index rather than the source pointer.
- The in-game name-entry screen renders ASCII `0-9`, `A-Z`, and `a-z`, proving
  usable Latin glyphs and an English input mapping already exist.
