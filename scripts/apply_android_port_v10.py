#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REBLUE = ROOT / "upstream/reblue"

# v10 extends the validated Android runtime/source changes without changing
# their behaviour.
subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v9.py")], check=True)

rexglue_cmake = REBLUE / "generated/rexglue.cmake"
text = rexglue_cmake.read_text()

anchor = '''set(REXGLUE_RECOMP_DEBUG_INFO "line-tables-only" CACHE STRING
    "Debug info level for generated code: line-tables-only, full, or none")
'''
insert = '''set(REXGLUE_RECOMP_DEBUG_INFO "line-tables-only" CACHE STRING
    "Debug info level for generated code: line-tables-only, full, or none")

# Cross-compiling ReXGlue also creates a target-platform rexglue CLI, which
# cannot run on the host. Android builds therefore consume sources generated
# beforehand by the official host SDK.
option(REBLUE_PREGENERATED "Use already-generated re:Blue recompilation sources" OFF)
if(REBLUE_PREGENERATED AND NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/generated/sources.cmake")
    message(FATAL_ERROR
        "REBLUE_PREGENERATED=ON requires generated/sources.cmake from a prior host codegen run")
endif()
'''
if text.count(anchor) != 1:
    raise RuntimeError("generated/rexglue.cmake: expected recomp debug-info anchor once")
text = text.replace(anchor, insert, 1)

old_codegen = '''# Codegen runs as part of the build, re-running only when an input in codegen.d
# changes. Build it alone with 'cmake --build . --target reblue_codegen'.
# Listing the sources as outputs orders any target that compiles them after
# codegen, including one a project assembles itself rather than taking the
# library rexglue_setup_target() builds. The stamp comes first: the DEPFILE
# names it.
add_custom_command(
    OUTPUT "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.build.stamp"
           ${REXGLUE_ENTRYPOINT_GENERATED_SOURCES}
    COMMAND $<TARGET_FILE:rex::rexglue> codegen ${CMAKE_CURRENT_SOURCE_DIR}/reblue_manifest.toml
    DEPFILE "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.d"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "Generating recompiled code for reblue"
    VERBATIM
)
add_custom_target(reblue_codegen
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.build.stamp")
'''
new_codegen = '''# Codegen runs as part of normal desktop builds. Cross-builds may instead
# consume sources produced beforehand by a host-native ReXGlue CLI.
if(REBLUE_PREGENERATED)
    add_custom_target(reblue_codegen)
    message(STATUS "Using pre-generated re:Blue recompilation sources")
else()
    add_custom_command(
        OUTPUT "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.build.stamp"
               ${REXGLUE_ENTRYPOINT_GENERATED_SOURCES}
        COMMAND $<TARGET_FILE:rex::rexglue> codegen ${CMAKE_CURRENT_SOURCE_DIR}/reblue_manifest.toml
        DEPFILE "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.d"
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        COMMENT "Generating recompiled code for reblue"
        VERBATIM
    )
    add_custom_target(reblue_codegen
        DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/generated/codegen.build.stamp")
endif()
'''
if text.count(old_codegen) != 1:
    raise RuntimeError("generated/rexglue.cmake: expected codegen block once")
text = text.replace(old_codegen, new_codegen, 1)
rexglue_cmake.write_text(text)
print("updated upstream/reblue/generated/rexglue.cmake (pre-generated Android codegen mode)")
print("Android v10 source transforms applied successfully")
