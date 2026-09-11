# Full-game English patch

## Current tested patch

`SLPS-25228-English-current.xdelta` recreates the v23 release candidate with
DTE menus and dialogue, the numeric/name-entry lookup-table fix, expanded UI
translations, the native English title logo, five line-aligned English intro
cards, and the latest Hero Setup spacing fixes (`AKA`, `Confirm`, and the
birthday separator).

- Patch SHA-256: `4ed81c26f9d0cf931ca41ebb0f53cb663c2412e04f6931a84096de08f8a03f1a`
- Patched ISO SHA-256: `ab1c79e9499f40851ec58a673ed8a1141e97d163134a36a86e76822c25044f6f`
- Original ISO SHA-256: `1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd`

Apply it with `./tools/apply-full-game-patch.sh`.

`SLPS-25228-English-full-game-second-pass-all-DTE-TTF-mono.xdelta` converts an
unmodified Japanese `SLPS-25228` disc image into the full-game, second-pass,
all-DTE TTF mono English test image.

Run from the repository root:

```sh
./tools/apply-full-game-patch.sh original/SLPS-25228.iso build/patched.iso
```

The script refuses an incorrect source image or an existing output path and
verifies the finished ISO before reporting success.

## Checksums

- Original ISO SHA-256: `1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd`
- Patch SHA-256: `3db4ef5ad3dd0027437cc11d562b054eb0c6026d639193263c720f8dd9da6c71`
- Patched ISO SHA-256: `e851e9a271077a80fbb6e94d44f73afa746a4204e3453d30e4e0d0d16f9d0c04`

This is an xdelta disc patch, not a PCSX2 `.pnach`: PCSX2 cheat patches alter
emulated memory and are not suitable for replacing the multi-megabyte font and
scenario data used by this translation.

## Residual-pass patch

`SLPS-25228-English-full-game-residual-pass-all-DTE-TTF-mono.xdelta` includes
the newer validated residual-string additions while retaining the conservative
original-slot insertion method.

- Patch SHA-256: `3e30bccb8465649f78f57582c6558de60e808c8f6c25ae2773f5680679416316`
- Patched ISO SHA-256: `e139840dca55a184425b61bd0b3472f4090bebde27f2706c1f5861b9e20117f9`

## Menu first-pass patch

`SLPS-25228-English-full-game-menu-first-pass-all-DTE.xdelta` adds the
gameplay-tested dialogue pointer swaps and the first executable menu,
inventory, unit, pilot, weapon, skill, and description translation batch.

- Patch SHA-256: `5df3e8cad88a668c7ff46bb01aad671f664e2c0691ac7ed43f37e5c5dfba1291`
- Patched ISO SHA-256: `9c73afa41286a6c4672a3800f3848808cff3f39519a70090115c8efadf70e240`
