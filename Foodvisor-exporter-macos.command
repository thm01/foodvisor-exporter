#!/usr/bin/env bash
set -u
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir" || exit 1
bash Foodvisor-exporter-linux.sh
result=$?
if [ "$result" -ne 0 ] && [ -t 0 ]; then
    read -r -p "L'application s'est arrêtée. Appuyez sur Entrée pour fermer..." _
fi
exit "$result"
