#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REX = ROOT / "upstream/rexglue-sdk"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v8.py")], check=True)


def replace(path: Path, old: str, new: str, expected: int = 1):
    text = path.read_text()
    found = text.count(old)
    if found != expected:
        raise RuntimeError(f"{path}: expected {expected} occurrence(s), found {found}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))
    print(f"updated {path.relative_to(ROOT)}")


def create(path: Path, content: str):
    if path.exists():
        raise RuntimeError(f"{path}: upstream file already exists")
    path.write_text(content)
    print(f"created {path.relative_to(ROOT)}")


# ReXGlue inherited the Android content-URI declarations and call sites from
# Xenia, but not filesystem_android.cc. SDL3 already owns the JavaVM/activity
# lifecycle for SDLActivity, so use SDL's Android accessors rather than adding
# a second JNI attachment/lifetime system.
core_cmake = REX / "src/core/CMakeLists.txt"
replace(
    core_cmake,
    "target_sources(rexcore PRIVATE fiber_android.cpp fiber_android_arm64.S)",
    "target_sources(rexcore PRIVATE fiber_android.cpp fiber_android_arm64.S filesystem_android.cpp)",
)

create(
    REX / "src/core/filesystem_android.cpp",
    r'''/**
 * @file rex/core/filesystem_android.cpp
 * @brief Android content:// filesystem bridge using SDL3's JNI lifecycle.
 */

#include <rex/platform.h>
#if REX_PLATFORM_ANDROID

#include <SDL3/SDL_system.h>
#include <jni.h>

#include <cstring>
#include <string>
#include <string_view>
#include <strings.h>

#include <rex/filesystem.h>
#include <rex/string.h>

namespace rex::filesystem {

void AndroidInitialize() {
  // SDLActivity owns the JavaVM/activity lifecycle. The content resolver is
  // intentionally obtained lazily so this remains safe before SDL has created
  // the Activity and after it has been recreated.
}

void AndroidShutdown() {
  // No global JNI references are retained by this backend.
}

bool IsAndroidContentUri(const std::string_view source) {
  static constexpr char kContentSchema[] = "content://";
  constexpr size_t kContentSchemaLength = sizeof(kContentSchema) - 1;
  return source.size() >= kContentSchemaLength &&
         strncasecmp(source.data(), kContentSchema, kContentSchemaLength) == 0;
}

int OpenAndroidContentFileDescriptor(const std::string_view uri,
                                     const char* mode) {
  if (!IsAndroidContentUri(uri) || !mode) {
    return -1;
  }

  auto* env = static_cast<JNIEnv*>(SDL_GetAndroidJNIEnv());
  auto activity = static_cast<jobject>(SDL_GetAndroidActivity());
  if (!env || !activity) {
    return -1;
  }

  jclass activity_class = env->GetObjectClass(activity);
  if (!activity_class) {
    return -1;
  }

  jmethodID get_content_resolver = env->GetMethodID(
      activity_class, "getContentResolver", "()Landroid/content/ContentResolver;");
  env->DeleteLocalRef(activity_class);
  if (!get_content_resolver) {
    if (env->ExceptionCheck()) env->ExceptionClear();
    return -1;
  }

  jobject resolver = env->CallObjectMethod(activity, get_content_resolver);
  if (env->ExceptionCheck()) {
    env->ExceptionClear();
    return -1;
  }
  if (!resolver) {
    return -1;
  }

  jclass uri_class = env->FindClass("android/net/Uri");
  if (!uri_class) {
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(resolver);
    return -1;
  }
  jmethodID parse_uri = env->GetStaticMethodID(
      uri_class, "parse", "(Ljava/lang/String;)Landroid/net/Uri;");
  if (!parse_uri) {
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(uri_class);
    env->DeleteLocalRef(resolver);
    return -1;
  }

  const std::u16string uri_utf16 = rex::string::to_utf16(uri);
  jstring uri_string = env->NewString(
      reinterpret_cast<const jchar*>(uri_utf16.data()),
      static_cast<jsize>(uri_utf16.size()));
  if (!uri_string) {
    env->DeleteLocalRef(uri_class);
    env->DeleteLocalRef(resolver);
    return -1;
  }

  jobject uri_object = env->CallStaticObjectMethod(uri_class, parse_uri, uri_string);
  env->DeleteLocalRef(uri_string);
  env->DeleteLocalRef(uri_class);
  if (env->ExceptionCheck()) {
    env->ExceptionClear();
    env->DeleteLocalRef(resolver);
    return -1;
  }
  if (!uri_object) {
    env->DeleteLocalRef(resolver);
    return -1;
  }

  jstring mode_string = env->NewStringUTF(mode);
  if (!mode_string) {
    env->DeleteLocalRef(uri_object);
    env->DeleteLocalRef(resolver);
    return -1;
  }

  jclass resolver_class = env->GetObjectClass(resolver);
  if (!resolver_class) {
    env->DeleteLocalRef(mode_string);
    env->DeleteLocalRef(uri_object);
    env->DeleteLocalRef(resolver);
    return -1;
  }
  jmethodID open_fd = env->GetMethodID(
      resolver_class, "openFileDescriptor",
      "(Landroid/net/Uri;Ljava/lang/String;)Landroid/os/ParcelFileDescriptor;");
  env->DeleteLocalRef(resolver_class);
  if (!open_fd) {
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(mode_string);
    env->DeleteLocalRef(uri_object);
    env->DeleteLocalRef(resolver);
    return -1;
  }

  jobject parcel_fd = env->CallObjectMethod(resolver, open_fd, uri_object, mode_string);
  env->DeleteLocalRef(mode_string);
  env->DeleteLocalRef(uri_object);
  env->DeleteLocalRef(resolver);
  if (env->ExceptionCheck()) {
    env->ExceptionClear();
    return -1;
  }
  if (!parcel_fd) {
    return -1;
  }

  jclass parcel_fd_class = env->GetObjectClass(parcel_fd);
  if (!parcel_fd_class) {
    env->DeleteLocalRef(parcel_fd);
    return -1;
  }
  jmethodID detach_fd = env->GetMethodID(parcel_fd_class, "detachFd", "()I");
  env->DeleteLocalRef(parcel_fd_class);
  if (!detach_fd) {
    if (env->ExceptionCheck()) env->ExceptionClear();
    env->DeleteLocalRef(parcel_fd);
    return -1;
  }

  const jint fd = env->CallIntMethod(parcel_fd, detach_fd);
  env->DeleteLocalRef(parcel_fd);
  if (env->ExceptionCheck()) {
    env->ExceptionClear();
    return -1;
  }
  return static_cast<int>(fd);
}

}  // namespace rex::filesystem

#endif  // REX_PLATFORM_ANDROID
''',
)

print("Android v9 source transforms applied successfully")
