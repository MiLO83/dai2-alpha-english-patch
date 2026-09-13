#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="$repo_dir/work/editor-venv/bin/python"
if [[ ! -x "$python" ]]; then
    echo "Preparing the project-local Python environment..."
    python3 -m venv "$repo_dir/work/editor-venv"
    "$python" -m pip install Pillow
fi

table="${1:-$repo_dir/translation/all-known-game-text.tsv}"
header="$(head -n 1 "$table")"
header="${header#$'\xEF\xBB\xBF'}"
# A combined master has Scope and can drive both domains. A legacy/plain
# dialogue table has no UI rows, so retain the packaged reviewed UI table
# instead of accidentally rebuilding every menu from an empty selection.
if [[ "$header" == Scope$'\t'* ]]; then
    ui_table="$table"
else
    ui_table="$repo_dir/translation/ui-script.tsv"
fi
exec "$python" "$repo_dir/tools/editable_translation.py" build \
    "$table" \
    "${2:-$repo_dir/original/SLPS-25228.iso}" \
    "${3:-$repo_dir/build/SLPS-25228-English-edited.iso}" \
    --ui-table "$ui_table" "${@:4}"
