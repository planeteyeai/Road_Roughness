#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "Frontend: http://127.0.0.1:5500/"
exec python3 -m http.server 5500 --bind 127.0.0.1
