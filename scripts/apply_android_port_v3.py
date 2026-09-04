#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

# Apply the already validated Android source transform first.
subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v2.py")], check=True)

# Android's libc++ currently doesn't expose std::chrono::clock_time_conversion /
# clock_cast, just like Apple libc++. ReXGlue already provides its own fallback
# for Apple, so use that compatibility path on Android as well.
chrono = ROOT / "upstream/rexglue-sdk/include/rex/chrono/chrono.h"
text = chrono.read_text()
old = "#ifdef __APPLE__\n// Apple libc++ does not expose clock_time_conversion or clock_cast.\n"
new = "#if defined(__APPLE__) || defined(__ANDROID__)\n// Apple and Android libc++ do not expose clock_time_conversion or clock_cast.\n"
count = text.count(old)
if count != 1:
    raise RuntimeError(f"{chrono}: expected chrono compatibility marker once, found {count}")
chrono.write_text(text.replace(old, new, 1))
print("updated upstream/rexglue-sdk/include/rex/chrono/chrono.h")
print("Android v3 source transforms applied successfully")
