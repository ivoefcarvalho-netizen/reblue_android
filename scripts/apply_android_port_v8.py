#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v7.py")], check=True)

# Android/Bionic provides pthread and POSIX realtime APIs from libc itself.
# There are no standalone libpthread.so / librt.so NDK link targets, so the
# generic UNIX link line (-lpthread -lrt -ldl) fails at the final shared-link
# step. Keep libdl for dlopen/dlsym, which is a real Android NDK library.
core_cmake = REX / "src/core/CMakeLists.txt"
text = core_cmake.read_text()
old = '''if(APPLE)
    target_link_libraries(rexcore PRIVATE pthread)
elseif(UNIX)
    target_link_libraries(rexcore PRIVATE pthread rt dl)
endif()
'''
new = '''if(APPLE)
    target_link_libraries(rexcore PRIVATE pthread)
elseif(ANDROID)
    target_link_libraries(rexcore PRIVATE dl)
elseif(UNIX)
    target_link_libraries(rexcore PRIVATE pthread rt dl)
endif()
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"{core_cmake}: expected POSIX link-library block once, found {count}")
core_cmake.write_text(text.replace(old, new, 1))
print("updated upstream/rexglue-sdk/src/core/CMakeLists.txt (Android libc pthread/rt linkage)")
print("Android v8 source transforms applied successfully")
