#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v10.py")], check=True)

# filesystem_android.cpp uses SDL3's Android JNI accessors. rexcore normally has
# no SDL include path because SDL is consumed by higher-level UI/audio/input
# targets. Link SDL3 privately on Android so its usage requirements (notably
# include directories) are available while compiling the Android filesystem
# bridge. PRIVATE keeps SDL out of rexcore's public interface.
core_cmake = REX / "src/core/CMakeLists.txt"
text = core_cmake.read_text()
old = '''elseif(ANDROID)
    target_link_libraries(rexcore PRIVATE dl)
elseif(UNIX)
'''
new = '''elseif(ANDROID)
    target_link_libraries(rexcore PRIVATE dl SDL3::SDL3)
elseif(UNIX)
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"{core_cmake}: expected Android rexcore link block once, found {count}")
core_cmake.write_text(text.replace(old, new, 1))
print("updated upstream/rexglue-sdk/src/core/CMakeLists.txt (SDL3 available to Android rexcore)")
print("Android v11 source transforms applied successfully")
