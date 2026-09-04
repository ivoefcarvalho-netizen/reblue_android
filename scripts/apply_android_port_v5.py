#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v4.py")], check=True)

cmake = REX / "CMakeLists.txt"
text = cmake.read_text()
marker = ")\n# Floor only: bump MAJOR.MINOR for API changes. Patch is derived from git tags\n"
insert = ")\n\n# The Android ARM64 fiber backend lives in src/core while FFmpeg also has ARM64\n# assembly under thirdparty. Enable ASM at the project root so the compile rule\n# is visible to every subdirectory (not just thirdparty).\nif(ANDROID)\n    enable_language(ASM)\nendif()\n\n# Floor only: bump MAJOR.MINOR for API changes. Patch is derived from git tags\n"
count = text.count(marker)
if count != 1:
    raise RuntimeError(f"{cmake}: expected project marker once, found {count}")
cmake.write_text(text.replace(marker, insert, 1))
print("updated upstream/rexglue-sdk/CMakeLists.txt (top-level ASM enablement)")
print("Android v5 source transforms applied successfully")
