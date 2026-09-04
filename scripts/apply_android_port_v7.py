#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v6.py")], check=True)

threading = REX / "src/core/threading_posix.cpp"
text = threading.read_text()

# Bionic does not provide the Linux robust-mutex extension used here
# (PTHREAD_MUTEX_ROBUST / pthread_mutex_consistent). On Android fall back to
# the normal std::mutex path; Linux desktop keeps owner-death recovery.
markers = [
    (
        "#if REX_PLATFORM_LINUX\n    // Use robust mutexes so waits can recover if owner thread terminates.\n",
        "#if REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID\n    // Use robust mutexes so waits can recover if owner thread terminates.\n",
    ),
    (
        "#if REX_PLATFORM_LINUX\n    auto native_mutex = static_cast<pthread_mutex_t*>(mutex_.native_handle());\n",
        "#if REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID\n    auto native_mutex = static_cast<pthread_mutex_t*>(mutex_.native_handle());\n",
    ),
    (
        "#if REX_PLATFORM_LINUX\n        auto native_mutex = static_cast<pthread_mutex_t*>(handles[i]->mutex_.native_handle());\n",
        "#if REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID\n        auto native_mutex = static_cast<pthread_mutex_t*>(handles[i]->mutex_.native_handle());\n",
    ),
]

for old, new in markers:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{threading}: expected robust-mutex marker once, found {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)

threading.write_text(text)
print("updated upstream/rexglue-sdk/src/core/threading_posix.cpp (Android robust-mutex fallback)")
print("Android v7 source transforms applied successfully")
