# PCSX2 prologue texture replacements

The `SLPS-25228/replacements` directory contains exact-hash English
replacements for the five pre-rendered prologue text cards. The shared artwork
and alpha layout are copied from textures dumped from the user's own disc.

Enable **Load Textures** under PCSX2's Texture Replacement settings. Keep
**Dump Textures** disabled during normal play.

Run `tools/build_intro_texture_pack.py` to regenerate and install the files into
the project-local PCSX2 directory after obtaining the matching original dumps.
