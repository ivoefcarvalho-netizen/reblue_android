#!/usr/bin/env python3
"""Apply after v12, once, to pinned upstream + generated guest sources."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]/'upstream/reblue'
S=R.parent/'rexglue-sdk'
def edit(p,a,b,n=1):
 t=p.read_text(); assert t.count(a)>=n,(p,a[:100]);p.write_text(t.replace(a,b,n))
def add(p,t):p.write_text(t+p.read_text())
# Build-time executables always belong to the host.
p=R/'thirdparty/XenosRecomp/thirdparty/dxc-bin/CMakeLists.txt'
edit(p,'if (CMAKE_OSX_ARCHITECTURES)','if(ANDROID)\n    set(DXC_ARCHITECTURE ${CMAKE_HOST_SYSTEM_PROCESSOR})\nelseif (CMAKE_OSX_ARCHITECTURES)')
p=R/'cmake/shader_cache.cmake'
edit(p,'    add_custom_command(','    if(ANDROID)\n        if(NOT EXISTS "${REBLUE_HOST_XENOS}")\n            message(FATAL_ERROR "REBLUE_HOST_XENOS must point to the host XenosRecomp executable")\n        endif()\n        set(shader_recompiler "${REBLUE_HOST_XENOS}")\n        set(shader_recompiler_dep "${REBLUE_HOST_XENOS}")\n    else()\n        set(shader_recompiler $<TARGET_FILE:${ARG_RECOMP_TARGET}>)\n        set(shader_recompiler_dep ${ARG_RECOMP_TARGET})\n    endif()\n\n    add_custom_command(')
edit(p,'COMMAND $<TARGET_FILE:${ARG_RECOMP_TARGET}>','COMMAND ${shader_recompiler}',2)
edit(p,'DEPENDS ${ARG_RECOMP_TARGET} "${ARG_INCLUDE_FILE}"','DEPENDS ${shader_recompiler_dep} "${ARG_INCLUDE_FILE}"')
# Restore Android-safe crash/log handling.
p=R/'src/platform/crash_handler.cpp';edit(p,'#include <execinfo.h>','#ifndef __ANDROID__\n#include <execinfo.h>\n#endif')
edit(p,'#else\n  (void)base;\n  void *frames[32]','#elif defined(__ANDROID__)\n  (void)base;\n  BD_CRITICAL("Android: crash registers recorded; libc backtrace unavailable");\n#else\n  (void)base;\n  void *frames[32]')
p=S/'src/ui/rex_app.cpp';edit(p,'log_config.log_dir = (exe_dir / "logs").string();','#ifdef __ANDROID__\n    log_config.log_dir = "/data/user/0/org.reblue.android.saf/files/reblue/profiles/default/logs";\n#else\n    log_config.log_dir = (exe_dir / "logs").string();\n#endif')
diag='''#pragma once
#include <cstdio>
#include <ctime>
#include <mutex>
#include <unordered_set>
#include <string>
namespace reblue_android {
inline void stage(const char* file,const char* message,bool reset=false) {
#ifdef __ANDROID__
 char path[256]; std::snprintf(path,sizeof(path),"/data/user/0/org.reblue.android.saf/files/reblue/%s",file);
 if(auto* f=std::fopen(path,reset?"w":"a")){std::fprintf(f,"%lld %s\\n",(long long)std::time(nullptr),message);std::fclose(f);}
#endif
}
inline void gpu(const char* message) {
#ifdef __ANDROID__
 static std::mutex m;static std::unordered_set<std::string> seen;
 std::lock_guard lock(m);if(seen.insert(message).second)stage("gpu-stage.txt",message);
#endif
}
}
'''
(S/'include/rex/android_diagnostics.h').write_text(diag)
(R/'src/gpu/android_diag.h').write_text(diag)
p=S/'src/ui/windowed_app_main_sdl.cpp';add(p,'#include "rex/android_diagnostics.h"\n')
edit(p,'int RunWindowedApp(int argc, char** argv) {','int RunWindowedApp(int argc, char** argv) {\n  reblue_android::stage("native-stage.log", "N00-v2.3-source-rebuild", true);\n  reblue_android::stage("gpu-stage.txt", "G00-v2.3-source-rebuild", true);')
edit(p,'    result = app->OnInitialize() ? app_context.RunMainMessageLoop() : EXIT_FAILURE;','    reblue_android::stage("native-stage.log", "N17-before-app-OnInitialize");\n    const bool initialized = app->OnInitialize();\n    reblue_android::stage("native-stage.log", initialized ? "N18-after-app-OnInitialize-ok" : "N18-after-app-OnInitialize-failed");\n    result = initialized ? app_context.RunMainMessageLoop() : EXIT_FAILURE;')
p=S/'src/ui/rex_app.cpp';add(p,'#include "rex/android_diagnostics.h"\n')
for a,m in [('  if (!SetupEnvironment())','A00-before-SetupEnvironment'),('  if (!SetupPresentation())','A01-before-SetupPresentation'),('  auto paths = OnFinalizePaths','A02-before-OnFinalizePaths'),('  if (!ConstructRuntime(*paths))','A03-before-ConstructRuntime'),('  LaunchModule();','A04-before-LaunchModule'),('  rex::InitLogging(log_config);','E00-before-InitLogging')]:
 edit(p,a,f'  reblue_android::stage("native-stage.log", "{m}");\n'+a)
edit(p,'  rex::InitLogging(log_config);','  rex::InitLogging(log_config);\n  reblue_android::stage("native-stage.log", "E01-after-InitLogging");')
# HCG Vulkan shaders: reproduce v2.2 push layout, no common-header BDA.
p=R/'src/gpu/shaders/hlsl/bd_2d_blit_vs.hlsl'
edit(p,'#include "thirdparty/XenosRecomp/XenosRecomp/shader_common.h"','')
a='#define g_BlitHalfPixelOffset \\\n    vk::RawBufferLoad<float2>(g_PushConstants.SharedConstants + 336)'
b='struct BlitPush { [[vk::offset(32)]] float2 halfPixel; };\n[[vk::push_constant]] ConstantBuffer<BlitPush> blitPush;\n#define g_BlitHalfPixelOffset blitPush.halfPixel'
edit(p,a,b)
p=R/'src/gpu/shaders/hlsl/bd_2d_blit_ps.hlsl';edit(p,'#include "thirdparty/XenosRecomp/XenosRecomp/shader_common.h"','#ifndef __spirv__\n#include "thirdparty/XenosRecomp/XenosRecomp/shader_common.h"\n#endif')
edit(p,'#define Tex0_ResourceDescriptorIndex vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 0)\n#define Tex0_SamplerDescriptorIndex  vk::RawBufferLoad<uint>(g_PushConstants.SharedConstants + 192)','struct BlitPush { [[vk::offset(24)]] uint textureIndex; [[vk::offset(28)]] uint samplerIndex; };\n[[vk::push_constant]] ConstantBuffer<BlitPush> blitPush;\n[[vk::binding(0,0)]] Texture2D<float4> g_Texture2DDescriptorHeap[];\n[[vk::binding(0,3)]] SamplerState g_SamplerDescriptorHeap[];\n#define Tex0_ResourceDescriptorIndex blitPush.textureIndex\n#define Tex0_SamplerDescriptorIndex blitPush.samplerIndex')
p=R/'src/gpu/resources.h';edit(p,'  const ShaderCacheEntry *shaderCacheEntry = nullptr;','  const ShaderCacheEntry *shaderCacheEntry = nullptr;\n  bool hcgBlit = false;')
p=R/'src/gpu/hooks/shader.cpp';edit(p,'  shader->shader =\n','  shader->hcgBlit = true;\n  shader->shader =\n')
p=R/'src/gpu/constant_buffers.h';edit(p,'void InvalidateSharedBinding();','void InvalidateSharedBinding();\nvoid GetBlitPushConstants(u32 (&out)[4]);')
p=R/'src/gpu/constant_buffers.cpp';edit(p,'void InvalidateSharedBinding()','void GetBlitPushConstants(u32 (&out)[4]) {\n  const auto &shared = upload_state().shared;\n  out[0] = shared.texture2DIndices[0];\n  out[1] = shared.samplerIndices[0];\n  std::memcpy(&out[2], &shared.blitHalfPixelOffsetX, sizeof(float));\n  std::memcpy(&out[3], &shared.blitHalfPixelOffsetY, sizeof(float));\n}\n\nvoid InvalidateSharedBinding()')
p=R/'src/gpu/draw.cpp';edit(p,'  // Lens flare occlusion count:','#if !defined(REBLUE_D3D12)\n  if (device_guest && s.pipelineState.vertexShader && s.pipelineState.vertexShader->hcgBlit) {\n    u32 blit[4]; GetBlitPushConstants(blit);\n    s.command_list->setGraphicsPushConstants(kGuestPushConstantRangeIndex, blit, 24, sizeof(blit));\n  }\n#endif\n\n  // Lens flare occlusion count:')
p=R/'src/gpu/pipeline/pipeline_cache.cpp';add(p,'#include "gpu/android_diag.h"\n')
edit(p,'  // One input slot per unique slotIndex.','  plume::RenderInputElement blitInputs[3];\n  if (state.vertexShader && state.vertexShader->hcgBlit) {\n    u32 count = 0;\n    for (u32 i=0;i<desc.inputElementsCount;++i) {\n      const auto &e=desc.inputElements[i];\n      if(e.location==0 || e.location==7 || e.location==10) {\n        if(count==3) return nullptr;\n        blitInputs[count++]=e;\n      }\n    }\n    if(count!=3) { BD_ERROR("[hcg-pipeline] invalid-input-count={}",count); return nullptr; }\n    desc.inputElements=blitInputs;desc.inputElementsCount=count;\n  }\n\n  // One input slot per unique slotIndex.')
needle='  return CreateHostGraphicsPipeline(device, desc, "pipeline");\n#endif'
edit(p,needle,'''  const bool hcg=state.vertexShader && state.vertexShader->hcgBlit;
  if(hcg) reblue_android::gpu("G20-before-hcg-pipeline");
  auto pipeline=CreateHostGraphicsPipeline(device, desc, "pipeline");
  if(hcg) {
    reblue_android::gpu(pipeline ? "G21-hcg-pipeline-ok" : "G21-hcg-pipeline-failed");
    static std::atomic<unsigned> calls{0};const auto n=++calls;
    if(n<=4 || (n & (n-1))==0) {
      BD_INFO("[hcg-pipeline] result={} inputs={} slots={}", pipeline?"ok":"failed", desc.inputElementsCount, desc.inputSlotsCount);
      if(!pipeline) {
        BD_ERROR("[pso-fail-kind] hcg_blit=1");
        for(u32 i=0;i<desc.inputSlotsCount;++i) BD_ERROR("[pso-fail-slot] slot={} stride={}",desc.inputSlots[i].index,desc.inputSlots[i].stride);
        for(u32 i=0;i<desc.inputElementsCount;++i) BD_ERROR("[pso-fail-elem] loc={} slot={} fmt={} offset={}",desc.inputElements[i].location,desc.inputElements[i].slotIndex,(unsigned)desc.inputElements[i].format,desc.inputElements[i].alignedByteOffset);
      }
    }
  }
  return pipeline;
#endif''')
p=R/'src/gpu/present.cpp';add(p,'#include "gpu/android_diag.h"\n')
edit(p,'void Video::Present(GuestTexture *frontBuffer) {','void Video::Present(GuestTexture *frontBuffer) {\n  reblue_android::gpu("G30-Present-enter");')
edit(p,'    s.queue->executeCommandLists(lists, 1, waits, 1, signals, 1,','    reblue_android::gpu("G31-before-queue-submit");\n    s.queue->executeCommandLists(lists, 1, waits, 1, signals, 1,')
edit(p,'    if (!s.swap_chain->present(texture_index, signals, 1)) {','    reblue_android::gpu("G32-after-queue-submit-before-present");\n    const bool presented=s.swap_chain->present(texture_index, signals, 1);\n    reblue_android::gpu(presented ? "G33-present-ok" : "G33-present-failed");\n    if (!presented) {')
p=R/'thirdparty/CMakeLists.txt';p.write_text(p.read_text()+'\nif(ANDROID)\n set_source_files_properties("${CMAKE_CURRENT_SOURCE_DIR}/implot/implot_items.cpp" PROPERTIES COMPILE_OPTIONS "-O0")\nendif()\n')
print('v2.3 source restoration applied')
# Capture unique guest shaders locally for a subsequent offline cache build.
p=R/'src/gpu/shaders/guest_shaders.cpp';add(p,'#include <filesystem>\n#include <unordered_set>\n#include "gpu/android_diag.h"\n')
edit(p,'    BD_WARN("Shader cache miss:','''#ifdef __ANDROID__
    static std::mutex captureMutex;
    static std::unordered_set<u64> captured;
    static size_t capturedBytes = 0;
    std::lock_guard captureLock(captureMutex);
    if(hash_len && hash_len<=1024*1024 && !captured.contains(hash) && capturedBytes+hash_len<=64*1024*1024) {
      const char* dir="/data/user/0/org.reblue.android.saf/files/reblue/shader-capture";
      std::error_code ec;std::filesystem::create_directories(dir,ec);
      char path[256];std::snprintf(path,sizeof(path),"%s/%016llX.%s",dir,(unsigned long long)hash,static_cast<u32>(type)==7 ? "vso":"pso");
      if(auto* f=std::fopen(path,"wb")) {
        const bool ok=std::fwrite(function,1,hash_len,f)==hash_len;
        std::fclose(f);
        if(ok) {captured.insert(hash);capturedBytes+=hash_len;
          BD_INFO("[shader-capture] unique={} bytes={} hash=0x{:016X}",captured.size(),capturedBytes,hash);
          reblue_android::gpu("G40-missing-shaders-captured");
        }
      }
    }
#endif
    BD_WARN("Shader cache miss:''')
p=R/'src/gpu/device.cpp';add(p,'#include "gpu/android_diag.h"\n')
for a,m in [('    s.device = s.render_iface->createDevice();','G01-before-createDevice'),('    s.backend_info = DescribeBackend(s.device.get());','G02-device-created'),('    s.swap_chain = s.queue->createSwapChain(desc);','G03-before-swapchain'),('    if (!BuildPipelineLayout(s)) {','G04-before-layout'),('    if (!BuildCopyPipeline(s)) {','G05-before-copy-pipeline'),('    if (!TryInit()) {','G06-before-TryInit'),('  s.ready = true;','G07-renderer-ready')]:
 edit(p,a,f'  reblue_android::gpu("{m}");\n'+a)
p=S/'thirdparty/CMakeLists.txt';edit(p,'target_compile_options(o1heap PRIVATE -w)','target_compile_options(o1heap PRIVATE -w)\nadd_library(rex::o1heap ALIAS o1heap)')
p=R/'CMakeLists.txt';edit(p,'add_subdirectory(thirdparty)','add_subdirectory(thirdparty)\nif(ANDROID AND TARGET rexruntime AND TARGET imgui)\n  target_include_directories(rexruntime INTERFACE $<TARGET_PROPERTY:imgui,INTERFACE_INCLUDE_DIRECTORIES>)\nendif()')
