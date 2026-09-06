# Android v2.3 source rebuild (in progress)

Baseline: reblue 957ac623199ebb3cfe40f6af28bc4958490b6067, rexglue-sdk
c94f5ebdcb3c9d1a460ca48e04f9758448f8d518. Pin the commit explicitly: the
v0.10.0 tag currently points at a different release-packaging commit.

Run host rexglue codegen first (219 translation units), then
apply_android_port_v12.py, then apply_android_recovery_v23.py, each once.
Generated guest sources and default.xex must never be committed here.

Host tools: NDK r29's Linux Clang 21 can also compile XenosRecomp for the host
with -DREBLUE_RECOMP -fms-extensions (without the Android toolchain file).
Restore executable permissions and symbolic links when extracting NDK ZIPs.
Build only the XenosRecomp target and pass its executable via REBLUE_HOST_XENOS.
Android configuration: arm64-v8a, android-28, c++_static, Release,
REBLUE_PREGENERATED=ON, REXSDK_DIR pointing at source SDK, Vulkan ON, D3D12 OFF,
installer OFF. Compile the reblue target; its output is libmain.so.

Restored behavior:
- Android log directory under the existing app's profiles/default/logs.
- Native startup markers including N18, GPU stages reset per process launch.
- Existing Plume VkResult diagnostics plus HCG success/failure and input logs.
- v2.2 HCG input locations 0/7/10 and push offsets 24/28/32 (40-byte range).
- HCG VS has Shader only; PS retains RuntimeDescriptorArray. Neither uses
  Int64 or PhysicalStorageBufferAddresses. Keep desktop shader branches.
- Unique missing shader containers saved in app-private shader-capture,
  capped at 64 MiB per process. The installed game is read normally.
- Android crash logging avoids Bionic backtrace symbols; implot_items uses O0.

The supplied v2.2 black-screen log contains no pipeline error in its tail,
but does not establish that pipelines succeeded or any image was presented.
Missing native-stage.log is a known instrumentation regression, not proof of
failed Java or SDL initialization. Shader cache remains empty without the
actual game shader assets. Capturing them does not itself populate that cache.

Device report markers:
- N18-after-app-OnInitialize-ok: initialization returned successfully.
- G21-hcg-pipeline-ok / failed: actual host HCG PSO creation result.
- G30-Present-enter, G31-before-queue-submit, G32-after-queue-submit-before-present.
- G33-present-ok / failed: swapchain present result, not proof of visible content.
- G40-missing-shaders-captured and [shader-capture]: cache inputs captured.

Package using package_v23.py and the exact v2.1 base APK. It preserves the SAF
launcher and package, uses versionCode 23/versionName 2.3, verifies the v1.5+
certificate, replaces only the source-built main/runtime libraries and version
metadata, aligns and signs. Run audit_android_apk.py on the final signed APK.
Do not deliver a failed build or claim console validation without device logs.
