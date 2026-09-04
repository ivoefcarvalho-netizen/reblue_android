#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REBLUE = ROOT / "upstream" / "reblue"
REXGLUE = ROOT / "upstream" / "rexglue-sdk"


def replace_once(path: Path, old: str, new: str):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected marker exactly once, found {count}\n--- marker ---\n{old}")
    path.write_text(text.replace(old, new, 1))
    print(f"updated {path.relative_to(ROOT)}")


def write_new(path: Path, content: str):
    if path.exists():
        raise RuntimeError(f"{path}: refusing to overwrite existing upstream file")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"created {path.relative_to(ROOT)}")


def patch_reblue():
    cmake = REBLUE / "CMakeLists.txt"
    replace_once(
        cmake,
        'option(REBLUE_BUILD_INSTALLER "Build the built-in first-run disc installer" ON)\n',
        'if(ANDROID)\n'
        '    set(REBLUE_INSTALLER_DEFAULT OFF)\n'
        'else()\n'
        '    set(REBLUE_INSTALLER_DEFAULT ON)\n'
        'endif()\n'
        'option(REBLUE_BUILD_INSTALLER "Build the built-in first-run disc installer" ${REBLUE_INSTALLER_DEFAULT})\n',
    )

    replace_once(
        cmake,
        'foreach(target IN LISTS REBLUE_TARGETS)\n'
        '    add_executable(${target})\n'
        '    set_target_properties(${target} PROPERTIES WIN32_EXECUTABLE ON)\n'
        'endforeach()\n',
        'foreach(target IN LISTS REBLUE_TARGETS)\n'
        '    if(ANDROID)\n'
        '        # SDLActivity loads libmain.so. Keep the target name so the existing wiring works.\n'
        '        add_library(${target} SHARED)\n'
        '        set_target_properties(${target} PROPERTIES OUTPUT_NAME main)\n'
        '    else()\n'
        '        add_executable(${target})\n'
        '        set_target_properties(${target} PROPERTIES WIN32_EXECUTABLE ON)\n'
        '    endif()\n'
        'endforeach()\n',
    )

    replace_once(cmake, 'if(NOT WIN32)\n    find_package(CURL QUIET)\n',
                 'if(NOT WIN32 AND NOT ANDROID)\n    find_package(CURL QUIET)\n')

    replace_once(
        cmake,
        '# SDL controller mappings, reached through the hid_mappings_file cvar.\n'
        'foreach(target IN LISTS REBLUE_TARGETS)\n'
        '    add_custom_command(TARGET ${target} POST_BUILD\n'
        '        COMMAND ${CMAKE_COMMAND} -E copy_if_different\n'
        '            "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty/gamecontrollerdb/gamecontrollerdb.txt"\n'
        '            $<TARGET_FILE_DIR:${target}>\n'
        '        VERBATIM)\n'
        'endforeach()\n',
        '# SDL controller mappings, reached through the hid_mappings_file cvar.\n'
        '# Android will package this as an application asset instead of a sidecar file.\n'
        'if(NOT ANDROID)\n'
        '    foreach(target IN LISTS REBLUE_TARGETS)\n'
        '        add_custom_command(TARGET ${target} POST_BUILD\n'
        '            COMMAND ${CMAKE_COMMAND} -E copy_if_different\n'
        '                "${CMAKE_CURRENT_SOURCE_DIR}/thirdparty/gamecontrollerdb/gamecontrollerdb.txt"\n'
        '                $<TARGET_FILE_DIR:${target}>\n'
        '            VERBATIM)\n'
        '    endforeach()\n'
        'endif()\n',
    )

    replace_once(
        cmake,
        '    else()\n'
        '        # plume builds the surface through SDL3, which dlopen\'s the X11 or Wayland\n'
        '        # client libraries itself, so nothing here links a window system.\n'
        '        find_package(Vulkan REQUIRED)\n'
        '        target_link_libraries(${target} PRIVATE Vulkan::Vulkan)\n'
        '    endif()\n',
        '    elseif(ANDROID)\n'
        '        # plume already has VK_KHR_android_surface support and uses ANativeWindow.\n'
        '        target_link_libraries(${target} PRIVATE android log)\n'
        '    else()\n'
        '        # plume builds the surface through SDL3, which dlopen\'s the X11 or Wayland\n'
        '        # client libraries itself, so nothing here links a window system.\n'
        '        find_package(Vulkan REQUIRED)\n'
        '        target_link_libraries(${target} PRIVATE Vulkan::Vulkan)\n'
        '    endif()\n',
    )

    replace_once(cmake, 'if(UNIX)\n    foreach(target IN LISTS REBLUE_TARGETS)\n',
                 'if(UNIX AND NOT ANDROID)\n    foreach(target IN LISTS REBLUE_TARGETS)\n')

    native = REBLUE / "src/platform/native_window.cpp"
    replace_once(
        native,
        '#elif defined(__APPLE__)\n',
        '#elif defined(__ANDROID__)\n\n'
        'bool GetNativeRenderWindow(rex::ui::Window *window, plume::RenderWindow &out) {\n'
        '  out = static_cast<plume::RenderWindow>(window->GetNativeWindowHandle());\n'
        '  if (!out) {\n'
        '    BD_ERROR("Window has no Android ANativeWindow yet");\n'
        '    return false;\n'
        '  }\n'
        '  return true;\n'
        '}\n\n'
        '#elif defined(__APPLE__)\n',
    )


def patch_rexglue():
    cmake = REXGLUE / "CMakeLists.txt"
    replace_once(cmake, 'if(UNIX AND NOT APPLE)\n    # Keep installed binaries self-contained',
                 'if(UNIX AND NOT APPLE AND NOT ANDROID)\n    # Keep installed binaries self-contained')

    replace_once(
        cmake,
        'elseif(UNIX AND NOT APPLE)\n'
        '    if(REX_TARGET_PROCESSOR MATCHES "AMD64|x86_64")\n',
        'elseif(ANDROID)\n'
        '    if(REX_TARGET_PROCESSOR MATCHES "aarch64|ARM64|arm64")\n'
        '        set(REX_PLATFORM "android-arm64")\n'
        '    else()\n'
        '        message(FATAL_ERROR "Unsupported Android architecture: ${REX_TARGET_PROCESSOR}; this port targets ARM64 only")\n'
        '    endif()\n'
        '    add_compile_definitions(REX_PLATFORM_ANDROID=1 REX_PLATFORM_LINUX=1)\n'
        'elseif(UNIX AND NOT APPLE)\n'
        '    if(REX_TARGET_PROCESSOR MATCHES "AMD64|x86_64")\n',
    )
    replace_once(
        cmake,
        'message(FATAL_ERROR "Unsupported platform. ReXGlue supports Windows, Linux, and macOS only.")',
        'message(FATAL_ERROR "Unsupported platform. ReXGlue supports Windows, Linux, macOS, and Android ARM64.")',
    )

    helpers = REXGLUE / "cmake/rexglue_helpers.cmake"
    replace_once(helpers, 'if(UNIX AND NOT APPLE)\n        # Large executable support',
                 'if(UNIX AND NOT APPLE AND NOT ANDROID)\n        # Large executable support')
    replace_once(helpers, 'if(UNIX AND NOT APPLE)\n        set_target_properties(${target_name} PROPERTIES\n            INSTALL_RPATH "$ORIGIN"',
                 'if(UNIX AND NOT APPLE AND NOT ANDROID)\n        set_target_properties(${target_name} PROPERTIES\n            INSTALL_RPATH "$ORIGIN"')
    replace_once(helpers, 'if(UNIX AND NOT APPLE)\n        set_target_properties(${target_name} PROPERTIES\n            INSTALL_RPATH "$ORIGIN"\n            BUILD_WITH_INSTALL_RPATH ON\n        )\n    endif()\n\n    rexglue_apply_target_settings(${target_name})',
                 'if(UNIX AND NOT APPLE AND NOT ANDROID)\n        set_target_properties(${target_name} PROPERTIES\n            INSTALL_RPATH "$ORIGIN"\n            BUILD_WITH_INSTALL_RPATH ON\n        )\n    endif()\n\n    rexglue_apply_target_settings(${target_name})')

    thirdparty = REXGLUE / "thirdparty/CMakeLists.txt"
    replace_once(
        thirdparty,
        'set(SDL_UNIX_CONSOLE_BUILD ON CACHE BOOL "" FORCE)\n',
        'if(ANDROID)\n'
        '    set(SDL_UNIX_CONSOLE_BUILD OFF CACHE BOOL "" FORCE)\n'
        'else()\n'
        '    set(SDL_UNIX_CONSOLE_BUILD ON CACHE BOOL "" FORCE)\n'
        'endif()\n',
    )
    replace_once(
        thirdparty,
        'if(UNIX AND NOT APPLE)\n'
        '    set(SDL_X11               ON  CACHE BOOL "" FORCE)\n',
        'if(UNIX AND NOT APPLE AND NOT ANDROID)\n'
        '    set(SDL_X11               ON  CACHE BOOL "" FORCE)\n',
    )

    ui_cmake = REXGLUE / "src/ui/CMakeLists.txt"
    replace_once(
        ui_cmake,
        'if(WIN32)\n'
        '    set(REXUI_PLATFORM_SOURCES\n'
        '        surface_win.cpp\n'
        '    )\n'
        'elseif(APPLE)\n',
        'if(WIN32)\n'
        '    set(REXUI_PLATFORM_SOURCES\n'
        '        surface_win.cpp\n'
        '    )\n'
        'elseif(ANDROID)\n'
        '    set(REXUI_PLATFORM_SOURCES\n'
        '        surface_android.cpp\n'
        '    )\n'
        'elseif(APPLE)\n',
    )
    replace_once(ui_cmake, 'if(UNIX AND NOT APPLE)\n    find_package(PkgConfig REQUIRED)',
                 'if(UNIX AND NOT APPLE AND NOT ANDROID)\n    find_package(PkgConfig REQUIRED)')
    replace_once(
        ui_cmake,
        'elseif(APPLE)\n    target_link_libraries(rexui PRIVATE "-framework CoreFoundation")\nendif()\n',
        'elseif(APPLE)\n'
        '    target_link_libraries(rexui PRIVATE "-framework CoreFoundation")\n'
        'elseif(ANDROID)\n'
        '    target_link_libraries(rexui PUBLIC android log)\n'
        'endif()\n',
    )

    write_new(
        REXGLUE / "include/rex/ui/surface_android.h",
        '#pragma once\n\n'
        '#include <android/native_window.h>\n'
        '#include <rex/ui/surface.h>\n\n'
        'namespace rex::ui {\n\n'
        'class AndroidNativeWindowSurface final : public Surface {\n'
        ' public:\n'
        '  explicit AndroidNativeWindowSurface(ANativeWindow* window) : window_(window) {}\n'
        '  TypeIndex GetType() const override { return kTypeIndex_AndroidNativeWindow; }\n'
        '  ANativeWindow* window() const { return window_; }\n\n'
        ' protected:\n'
        '  bool GetSizeImpl(uint32_t& width_out, uint32_t& height_out) const override;\n\n'
        ' private:\n'
        '  ANativeWindow* window_ = nullptr;\n'
        '};\n\n'
        '}  // namespace rex::ui\n',
    )
    write_new(
        REXGLUE / "src/ui/surface_android.cpp",
        '#include <rex/ui/surface_android.h>\n\n'
        '#include <android/native_window.h>\n\n'
        'namespace rex::ui {\n\n'
        'bool AndroidNativeWindowSurface::GetSizeImpl(uint32_t& width_out, uint32_t& height_out) const {\n'
        '  if (!window_) return false;\n'
        '  const int width = ANativeWindow_getWidth(window_);\n'
        '  const int height = ANativeWindow_getHeight(window_);\n'
        '  if (width <= 0 || height <= 0) return false;\n'
        '  width_out = static_cast<uint32_t>(width);\n'
        '  height_out = static_cast<uint32_t>(height);\n'
        '  return true;\n'
        '}\n\n'
        '}  // namespace rex::ui\n',
    )

    window = REXGLUE / "src/ui/window_sdl.cpp"
    replace_once(
        window,
        '#if REX_PLATFORM_WIN32\n#include <rex/ui/surface_win.h>\n#elif REX_PLATFORM_MAC\n',
        '#if REX_PLATFORM_WIN32\n'
        '#include <rex/ui/surface_win.h>\n'
        '#elif REX_PLATFORM_ANDROID\n'
        '#include <android/native_window.h>\n'
        '#include <rex/ui/surface_android.h>\n'
        '#elif REX_PLATFORM_MAC\n',
    )
    replace_once(
        window,
        '  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),\n'
        '                                SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr);\n'
        '#else\n'
        '  return nullptr;\n'
        '#endif\n',
        '  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),\n'
        '                                SDL_PROP_WINDOW_WIN32_HWND_POINTER, nullptr);\n'
        '#elif REX_PLATFORM_ANDROID\n'
        '  if (!sdl_window_) return nullptr;\n'
        '  return SDL_GetPointerProperty(SDL_GetWindowProperties(sdl_window_),\n'
        '                                SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER, nullptr);\n'
        '#else\n'
        '  return nullptr;\n'
        '#endif\n',
    )
    replace_once(
        window,
        '#elif REX_PLATFORM_MAC\n'
        '  if (allowed_types & Surface::kTypeFlag_CAMetalLayer) {\n',
        '#elif REX_PLATFORM_ANDROID\n'
        '  if (allowed_types & Surface::kTypeFlag_AndroidNativeWindow) {\n'
        '    SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);\n'
        '    auto* native_window = static_cast<ANativeWindow*>(SDL_GetPointerProperty(\n'
        '        props, SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER, nullptr));\n'
        '    if (native_window) {\n'
        '      return std::make_unique<AndroidNativeWindowSurface>(native_window);\n'
        '    }\n'
        '  }\n'
        '#elif REX_PLATFORM_MAC\n'
        '  if (allowed_types & Surface::kTypeFlag_CAMetalLayer) {\n',
    )

    app_main = REXGLUE / "src/ui/windowed_app_main_sdl.cpp"
    replace_once(
        app_main,
        '#include <rex/ui/windowed_app_context_sdl.h>\n',
        '#include <rex/ui/windowed_app_context_sdl.h>\n\n'
        '#if REX_PLATFORM_ANDROID\n'
        '#include <SDL3/SDL_main.h>\n'
        '#endif\n',
    )


def main():
    if not REBLUE.exists() or not REXGLUE.exists():
        raise RuntimeError("Expected upstream/reblue and upstream/rexglue-sdk to exist")
    patch_reblue()
    patch_rexglue()
    print("Android source transforms applied successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
