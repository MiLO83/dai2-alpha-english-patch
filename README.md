# 2nd Super Robot Wars Alpha — English Translation Project

Research and tooling for an English translation patch of the Japanese
PlayStation 2 game **Dai-2-Ji Super Robot Taisen Alpha**
(`第2次スーパーロボット大戦α`).

## Target

- Platform: PlayStation 2
- Original Japanese retail serial: `SLPS-25228`
- Planned distribution format: `xdelta3`

Only original tooling, translation data, and binary differences belong in this
repository. Disc images, extracted game assets, and other copyrighted source
material must not be committed.

## Local layout

Place a legally dumped source image at:

```text
original/SLPS-25228.iso
```

The entire `original/` directory is ignored by Git. Future scripts will use:

```text
tools/       extraction, analysis, and rebuilding programs
translation/ translated text and terminology
work/        extracted or intermediate game data (ignored)
build/       generated patches and reports (ignored)
docs/        reverse-engineering notes
```

## First milestone

1. Record the exact ISO size and SHA-256 digest.
2. Inventory the ISO9660 filesystem without modifying the source image.
3. Identify archives, the boot ELF, fonts, and likely scenario data.
4. Search candidate files for Shift-JIS text and validate control codes.
5. Build a lossless extract/reinsert round trip before translation begins.

The local source image has been fingerprinted and its disc-format analysis is
in progress. See `docs/RESEARCH.md` for verified findings.

## Local PCSX2 development build

An ignored, project-local PCSX2 nightly installation can be launched with:

```bash
./tools/run-pcsx2.sh
```

The launcher keeps PCSX2 configuration, cache, data, and texture dumps below
`work/pcsx2/` instead of writing project state into the repository or relying
on system-installed OpenGL/Qt support libraries.
