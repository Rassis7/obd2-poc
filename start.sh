#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p .build
if [ ! -x .build/venv/bin/python ]; then
  python3 -m venv .build/venv
fi
.build/venv/bin/python -m pip install -q -r requirements.txt
xcrun clang -fobjc-arc -framework AppKit -framework Foundation -framework CoreBluetooth -framework IOBluetooth -Wl,-sectcreate,__TEXT,__info_plist,Info.plist Bluetooth.m -o .build/radio
exec .build/venv/bin/python server.py "$@"
