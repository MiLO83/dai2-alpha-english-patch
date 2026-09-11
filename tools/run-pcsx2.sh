#!/usr/bin/env bash
set -euo pipefail

project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
pcsx2_dir="$project_dir/work/pcsx2"
local_lib="$pcsx2_dir/runtime/usr/lib/x86_64-linux-gnu"
windows_exe="$pcsx2_dir/windows/app/pcsx2-qt.exe"

# The native Windows build is substantially more reliable than Linux Qt
# through WSLg. An empty portable.ini keeps all of its state beside the EXE.
if grep -qi microsoft /proc/sys/kernel/osrelease && [[ -f "$windows_exe" ]]; then
    exec "$windows_exe" "$@"
fi

if [[ ! -x "$pcsx2_dir/pcsx2.AppImage" ]]; then
    echo "PCSX2 AppImage is missing from $pcsx2_dir" >&2
    exit 1
fi

mkdir -p \
    "$pcsx2_dir/config" \
    "$pcsx2_dir/data" \
    "$pcsx2_dir/cache"

export LD_LIBRARY_PATH="$local_lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_CONFIG_HOME="$pcsx2_dir/config"
export XDG_DATA_HOME="$pcsx2_dir/data"
export XDG_CACHE_HOME="$pcsx2_dir/cache"

# Qt otherwise prefers X11 under WSLg, where an inherited DISPLAY can exist
# even when the usable connection for this shell is the Wayland socket.
if [[ -S /mnt/wslg/runtime-dir/wayland-0 ]]; then
    runtime_dir="/run/user/$(id -u)"
    if [[ ! -S "$runtime_dir/wayland-0" ]]; then
        echo "WSLg Wayland socket is unavailable at $runtime_dir/wayland-0" >&2
        exit 1
    fi
    export XDG_RUNTIME_DIR="$runtime_dir"
    export WAYLAND_DISPLAY=wayland-0
    export QT_QPA_PLATFORM=wayland
    export QT_WAYLAND_SHELL_INTEGRATION=xdg-shell
    unset QT_PLUGIN_PATH QML2_IMPORT_PATH QT_QPA_PLATFORM_PLUGIN_PATH
fi

exec "$pcsx2_dir/pcsx2.AppImage" "$@"
