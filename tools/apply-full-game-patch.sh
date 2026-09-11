#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
patch_file="$repo_dir/patches/SLPS-25228-English-current.xdelta"
expected_source="1f63e4acb06a689221a021a693063291d9448bb71776e6bd3d2da050de3cefdd"
expected_output="bb0e5f810e29e55291e28ded156d952919e8369a4d592cf1038155d97b89a8be"

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 ORIGINAL.iso [OUTPUT.iso]" >&2
    exit 2
fi

source_iso="$(realpath "$1")"
output_iso="${2:-SLPS-25228-English-current.iso}"

if [[ ! -f "$source_iso" ]]; then
    echo "Original ISO not found: $source_iso" >&2
    exit 1
fi
if [[ -e "$output_iso" ]]; then
    echo "Refusing to overwrite: $output_iso" >&2
    exit 1
fi

actual_source="$(sha256sum "$source_iso" | awk '{print $1}')"
if [[ "$actual_source" != "$expected_source" ]]; then
    echo "Wrong source ISO." >&2
    echo "Expected SHA-256: $expected_source" >&2
    echo "Actual SHA-256:   $actual_source" >&2
    exit 1
fi

if command -v xdelta3 >/dev/null 2>&1; then
    xdelta_bin="$(command -v xdelta3)"
elif [[ -x "$repo_dir/tools/xdelta3" ]]; then
    xdelta_bin="$repo_dir/tools/xdelta3"
else
    echo "xdelta3 is required (the Linux build is normally bundled in tools/)." >&2
    exit 1
fi

echo "Applying English patch..."
"$xdelta_bin" -d -s "$source_iso" "$patch_file" "$output_iso"

actual_output="$(sha256sum "$output_iso" | awk '{print $1}')"
if [[ "$actual_output" != "$expected_output" ]]; then
    echo "Output verification failed; removing invalid output." >&2
    rm -f -- "$output_iso"
    exit 1
fi

echo "Success: $output_iso"
echo "SHA-256: $actual_output"
