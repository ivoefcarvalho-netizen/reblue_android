#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v3.py")], check=True)


def replace(path: Path, old: str, new: str, expected: int = 1):
    text = path.read_text()
    found = text.count(old)
    if found != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrence(s), found {found}: {old[:100]!r}")
    path.write_text(text.replace(old, new))
    print(f"updated {path.relative_to(ROOT)}")


def create(path: Path, content: str):
    if path.exists():
        raise RuntimeError(f"{path}: upstream file already exists")
    path.write_text(content)
    print(f"created {path.relative_to(ROOT)}")

# Android/Bionic does not implement the obsolete POSIX ucontext API used by the
# desktop fiber backend. Use a tiny AArch64 cooperative context switch instead.
fiber_h = REX / "include/rex/thread/fiber.h"
replace(
    fiber_h,
    "#if REX_PLATFORM_LINUX || REX_PLATFORM_MAC\n#if REX_PLATFORM_MAC && !defined(_XOPEN_SOURCE)\n",
    "#if (REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID) || REX_PLATFORM_MAC\n#if REX_PLATFORM_MAC && !defined(_XOPEN_SOURCE)\n",
)
replace(
    fiber_h,
    "#include <cstdint>\n#include <vector>\n#endif\n\nnamespace rex::thread {\n",
    "#include <cstdint>\n#include <vector>\n#elif REX_PLATFORM_ANDROID\n#include <cstdint>\n#include <vector>\n#endif\n\nnamespace rex::thread {\n",
)
replace(
    fiber_h,
    "#elif REX_PLATFORM_LINUX || REX_PLATFORM_MAC\n  ucontext_t context_{};\n",
    "#elif REX_PLATFORM_ANDROID\n  // AAPCS64 callee-saved state. SwitchTo is a normal function call, so only\n  // registers required to survive a call need to be preserved. q8-q15 are\n  // saved in full even though AAPCS64 only requires their low 64 bits.\n  struct alignas(16) AndroidContext {\n    uint64_t x19_x30[12]{};\n    uint64_t sp = 0;\n    uint64_t reserved = 0;\n    alignas(16) uint8_t q8_q15[8 * 16]{};\n  };\n  AndroidContext context_{};\n  std::vector<uint8_t> stack_;\n  void (*entry_)(void*) = nullptr;\n  void* arg_ = nullptr;\n  bool is_thread_fiber_ = false;\n\n  [[noreturn]] static void Trampoline();\n#elif REX_PLATFORM_LINUX || REX_PLATFORM_MAC\n  ucontext_t context_{};\n",
)

core_cmake = REX / "src/core/CMakeLists.txt"
replace(
    core_cmake,
    "        fiber_posix.cpp\n        mapped_memory_posix.cpp\n",
    "        mapped_memory_posix.cpp\n",
)
replace(
    core_cmake,
    "        threading_posix.cpp\n    )\nendif()\n\n# Xenos data-format layer",
    "        threading_posix.cpp\n    )\n    if(ANDROID)\n        target_sources(rexcore PRIVATE fiber_android.cpp fiber_android_arm64.S)\n    else()\n        target_sources(rexcore PRIVATE fiber_posix.cpp)\n    endif()\nendif()\n\n# Xenos data-format layer",
)

create(
    REX / "src/core/fiber_android.cpp",
    r'''/**
 * @file rex/core/fiber_android.cpp
 * @brief Android ARM64 backend for rex::thread::Fiber
 */

#include <rex/platform.h>
#if REX_PLATFORM_ANDROID

#include <rex/thread/fiber.h>

#include <cassert>
#include <cstdint>
#include <cstdlib>

extern "C" void rex_fiber_swap_android(void* from_context, const void* to_context);

namespace rex::thread {

thread_local Fiber* Fiber::tls_current_ = nullptr;

Fiber* Fiber::ConvertCurrentThread() {
  auto* f = new Fiber();
  f->is_thread_fiber_ = true;
  tls_current_ = f;
  // The current register state is captured lazily on the first SwitchTo.
  return f;
}

Fiber* Fiber::Create(size_t stack_size, void (*entry)(void*), void* arg) {
  if (!entry || stack_size < 1024) {
    return nullptr;
  }

  auto* f = new Fiber();
  f->entry_ = entry;
  f->arg_ = arg;
  // Reserve a little alignment slack. AArch64 requires SP to remain 16-byte aligned.
  f->stack_.resize(stack_size + 16);
  uintptr_t stack_top = reinterpret_cast<uintptr_t>(f->stack_.data() + f->stack_.size());
  stack_top &= ~uintptr_t(0xF);
  f->context_.sp = static_cast<uint64_t>(stack_top);
  // x30 (LR) is the destination used by the final RET in rex_fiber_swap_android.
  f->context_.x19_x30[11] = reinterpret_cast<uint64_t>(&Fiber::Trampoline);
  return f;
}

[[noreturn]] void Fiber::Trampoline() {
  Fiber* f = tls_current_;
  assert(f && f->entry_);
  f->entry_(f->arg_);
  // A fiber entry point is not allowed to fall off the end (matching the
  // semantics expected by the existing POSIX backend with uc_link == nullptr).
  std::abort();
}

void Fiber::SwitchTo(Fiber* target) {
  assert(target);
  Fiber* from = tls_current_;
  assert(from && "ConvertCurrentThread must be called before SwitchTo");
  if (from == target) {
    return;
  }
  tls_current_ = target;
  rex_fiber_swap_android(&from->context_, &target->context_);
}

void Fiber::Destroy() {
  if (is_thread_fiber_) {
    tls_current_ = nullptr;
  } else {
    assert(this != tls_current_ && "Destroy called on the currently running fiber");
  }
  delete this;
}

}  // namespace rex::thread

#endif  // REX_PLATFORM_ANDROID
''',
)

create(
    REX / "src/core/fiber_android_arm64.S",
    r'''/* Android AArch64 cooperative fiber context switch.
 * AndroidContext offsets (see include/rex/thread/fiber.h):
 *   0..95   x19..x30
 *   96      sp
 *   104     reserved/padding
 *   112..239 q8..q15
 */

.text
.align 2
.global rex_fiber_swap_android
.type rex_fiber_swap_android, %function
rex_fiber_swap_android:
    stp x19, x20, [x0, #0]
    stp x21, x22, [x0, #16]
    stp x23, x24, [x0, #32]
    stp x25, x26, [x0, #48]
    stp x27, x28, [x0, #64]
    stp x29, x30, [x0, #80]
    mov x9, sp
    str x9, [x0, #96]
    stp q8,  q9,  [x0, #112]
    stp q10, q11, [x0, #144]
    stp q12, q13, [x0, #176]
    stp q14, q15, [x0, #208]

    ldp x19, x20, [x1, #0]
    ldp x21, x22, [x1, #16]
    ldp x23, x24, [x1, #32]
    ldp x25, x26, [x1, #48]
    ldp x27, x28, [x1, #64]
    ldp x29, x30, [x1, #80]
    ldr x9, [x1, #96]
    ldp q8,  q9,  [x1, #112]
    ldp q10, q11, [x1, #144]
    ldp q12, q13, [x1, #176]
    ldp q14, q15, [x1, #208]
    mov sp, x9
    ret
.size rex_fiber_swap_android, .-rex_fiber_swap_android
''',
)

print("Android v4 source transforms applied successfully")
