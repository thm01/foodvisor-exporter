#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.9+ est requis / Python 3.9+ is required.' >&2
    exit 1
fi
if ! python3 -c 'import sys; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
    printf '%s\n' 'Python 3.9+ est requis / Python 3.9+ is required.' >&2
    exit 1
fi
exec python3 app/web_interface.py
