#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v5.py")], check=True)

header = REX / "include/rex/main_android.h"
if header.exists():
    raise RuntimeError(f"{header}: upstream file already exists")
header.write_text(r'''#pragma once

#include <rex/platform.h>

#if REX_PLATFORM_ANDROID
#include <android/api-level.h>
#endif

namespace rex {

#if REX_PLATFORM_ANDROID
// Runtime Android API level of the device. The NDK function is available from
// API 24; the Android port currently targets API 28+, so this is always safe.
inline int GetAndroidApiLevel() {
  return android_get_device_api_level();
}
#endif

}  // namespace rex
''')
print("created upstream/rexglue-sdk/include/rex/main_android.h")

# memory_posix.cpp already references GetAndroidApiLevel but its old Xenia
# include is commented out. Point it to the ReXGlue compatibility header too.
memory = REX / "src/core/memory_posix.cpp"
text = memory.read_text()
old = '// TODO(tomc): Android or maybe na. idk\n// #include "xenia/base/main_android.h"\n'
new = '#include <rex/main_android.h>\n'
count = text.count(old)
if count != 1:
    raise RuntimeError(f"{memory}: expected Android main header marker once, found {count}")
memory.write_text(text.replace(old, new, 1))
print("updated upstream/rexglue-sdk/src/core/memory_posix.cpp")
print("Android v6 source transforms applied successfully")
