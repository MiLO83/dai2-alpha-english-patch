#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
table="${1:-$repo_dir/translation/all-known-game-text.tsv}"
source_iso="${2:-$repo_dir/original/SLPS-25228.iso}"
output_iso="${3:-$repo_dir/build/SLPS-25228-English-web-edited.iso}"
work_dir="$repo_dir/work/web-editor/build"
mkdir -p "$work_dir" "$(dirname "$output_iso")"

# First build all spreadsheet-controlled extents and their synchronized font.
"$repo_dir/tools/build-edited-iso.sh" \
  "$table" "$source_iso" "$work_dir/spreadsheet-base.iso" --force

# Recreate the tested release baseline, which carries the native custom title
# logo and line-aligned English intro cards outside the editable extents.
"$repo_dir/tools/xdelta3" -f -d -s "$source_iso" \
  "$repo_dir/patches/SLPS-25228-English-current.xdelta" \
  "$work_dir/visual-release-base.iso"

# Overlay the newly generated spreadsheet data onto that visual baseline.
python3 "$repo_dir/tools/replace_iso_extent.py" \
  "$work_dir/visual-release-base.iso" "$repo_dir/work/editor-build/editable-SLPS_252.28" \
  "$work_dir/with-elf.iso" --offset 0xB5000
python3 "$repo_dir/tools/replace_iso_extent.py" \
  "$work_dir/with-elf.iso" "$repo_dir/work/editor-build/editable-FTALL.P04" \
  "$work_dir/with-font.iso" --offset 0x6DFA8800
stage="$repo_dir/work/editor-build/editable-STAGE-expanded.BIN"
if [[ $(stat -c %s "$stage") -eq 8484480 ]]; then
  python3 "$repo_dir/tools/replace_iso_extent.py" \
    "$work_dir/with-font.iso" "$stage" "$output_iso" --offset 0x6EE0B800
else
  python3 "$repo_dir/tools/append_iso_extent.py" \
    "$work_dir/with-font.iso" "$stage" "$work_dir/with-expanded-stage.iso" \
    --directory-extent 0x10B --iso-name 'STAGE.BIN;1'
  python3 "$repo_dir/tools/replace_iso_extent.py" \
    "$work_dir/with-expanded-stage.iso" "$repo_dir/work/editor-build/editable-SLPS_252.28-expanded" \
    "$output_iso" --offset 0xB5000
fi

echo "Built spreadsheet ISO with native title logo and English intro cards:"
echo "$output_iso"
sha256sum "$output_iso"
