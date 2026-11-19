#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p .build
xcrun clang -fobjc-arc -framework AppKit -framework Foundation -framework CoreBluetooth -framework IOBluetooth -Wl,-sectcreate,__TEXT,__info_plist,Info.plist Bluetooth.m -o .build/radio
exec python3 server.py "$@"
