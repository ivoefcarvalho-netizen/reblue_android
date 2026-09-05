#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REBLUE = ROOT / "upstream/reblue"
PLUME = REBLUE / "thirdparty/plume"

subprocess.run([sys.executable, str(ROOT / "scripts/apply_android_port_v11.py")], check=True)


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected {label} exactly once, found {count}")
    path.write_text(text.replace(old, new, 1))
    print(f"updated {path.relative_to(ROOT)} ({label})")


# Preserve the VkResult returned by shader-module and graphics-pipeline creation.
# Plume historically only printed these failures to stderr, which Android sends
# to logcat and therefore does not reach re:Blue's persistent run log.
plume_h = PLUME / "plume_vulkan.h"
replace_once(
    plume_h,
    """    struct VulkanShader : RenderShader {
        VkShaderModule vk = VK_NULL_HANDLE;
        std::string entryPointName;
""",
    """    struct VulkanShader : RenderShader {
        VkShaderModule vk = VK_NULL_HANDLE;
        VkResult creationResult = VK_NOT_READY;
        std::string entryPointName;
""",
    "VulkanShader creationResult",
)
replace_once(
    plume_h,
    """    struct VulkanGraphicsPipeline : VulkanPipeline {
        VkPipeline vk = VK_NULL_HANDLE;
        VkRenderPass renderPass = VK_NULL_HANDLE;
""",
    """    struct VulkanGraphicsPipeline : VulkanPipeline {
        VkPipeline vk = VK_NULL_HANDLE;
        VkRenderPass renderPass = VK_NULL_HANDLE;
        VkResult creationResult = VK_NOT_READY;
""",
    "VulkanGraphicsPipeline creationResult",
)

plume_cpp = PLUME / "plume_vulkan.cpp"
replace_once(
    plume_cpp,
    """        VkResult res = vkCreateShaderModule(device->vk, &shaderInfo, nullptr, &vk);
        if (res != VK_SUCCESS) {
""",
    """        VkResult res = vkCreateShaderModule(device->vk, &shaderInfo, nullptr, &vk);
        creationResult = res;
        if (res != VK_SUCCESS) {
""",
    "vkCreateShaderModule result capture",
)
replace_once(
    plume_cpp,
    """        VkResult res = vkCreateGraphicsPipelines(device->vk, VK_NULL_HANDLE, 1, &pipelineInfo, nullptr, &vk);
        if (res != VK_SUCCESS) {
""",
    """        VkResult res = vkCreateGraphicsPipelines(device->vk, VK_NULL_HANDLE, 1, &pipelineInfo, nullptr, &vk);
        creationResult = res;
        if (res != VK_SUCCESS) {
""",
    "vkCreateGraphicsPipelines result capture",
)

# Route the captured Vulkan error into re:Blue's own logger and attach enough
# state to identify whether the failure came from a shader, render pass, or
# graphics-pipeline state. Throttle repeated failures to keep diagnostics small:
# first eight failures, then powers of two (16, 32, 64, ...).
device_cpp = REBLUE / "src/gpu/device.cpp"
old = """std::unique_ptr<plume::RenderPipeline>
CreateHostGraphicsPipeline(plume::RenderDevice *device,
                           const plume::RenderGraphicsPipelineDesc &desc,
                           const char *tag) {
  if (!device) {
    BD_ERROR(\"CreateHostGraphicsPipeline({}): no host device\", tag ? tag : \"?\");
    return nullptr;
  }
  auto pipeline = device->createGraphicsPipeline(desc);
  // Both backends fail soft: a failed
  // vkCreateGraphicsPipelines/CreatePipelineState still hands back a live
  // wrapper holding a null pipeline, which only faults later at bind time.
  if (!pipeline
#if defined(REBLUE_D3D12)
      || static_cast<plume::D3D12GraphicsPipeline *>(pipeline.get())->d3d ==
             nullptr
#else
      || static_cast<plume::VulkanGraphicsPipeline *>(pipeline.get())->vk ==
             VK_NULL_HANDLE
#endif
  ) {
    BD_ERROR(\"CreateHostGraphicsPipeline({}) failed: backend pipeline null\",
             tag ? tag : \"?\");
    CheckDeviceRemoved(tag ? tag : \"pipeline\");
    return nullptr;
  }
  return pipeline;
}
"""
new = """std::unique_ptr<plume::RenderPipeline>
CreateHostGraphicsPipeline(plume::RenderDevice *device,
                           const plume::RenderGraphicsPipelineDesc &desc,
                           const char *tag) {
  if (!device) {
    BD_ERROR(\"CreateHostGraphicsPipeline({}): no host device\", tag ? tag : \"?\");
    return nullptr;
  }
  auto pipeline = device->createGraphicsPipeline(desc);

#if defined(REBLUE_D3D12)
  if (!pipeline ||
      static_cast<plume::D3D12GraphicsPipeline *>(pipeline.get())->d3d ==
          nullptr) {
    BD_ERROR(\"CreateHostGraphicsPipeline({}) failed: backend pipeline null\",
             tag ? tag : \"?\");
    CheckDeviceRemoved(tag ? tag : \"pipeline\");
    return nullptr;
  }
#else
  auto *vk_pipeline =
      pipeline ? static_cast<plume::VulkanGraphicsPipeline *>(pipeline.get())
               : nullptr;
  if (!vk_pipeline || vk_pipeline->vk == VK_NULL_HANDLE) {
    static std::atomic<u32> failure_count{0};
    const u32 n = failure_count.fetch_add(1, std::memory_order_relaxed) + 1;
    const bool log_now = n <= 8 || (n & (n - 1)) == 0;

    if (log_now) {
      const auto shader_result = [](const plume::RenderShader *shader) -> i32 {
        return shader
                   ? static_cast<i32>(
                         static_cast<const plume::VulkanShader *>(shader)
                             ->creationResult)
                   : static_cast<i32>(VK_NOT_READY);
      };
      auto *vk_device = static_cast<plume::VulkanDevice *>(device);
      const auto &props = vk_device->physicalDeviceProperties;
      const i32 vk_result =
          vk_pipeline ? static_cast<i32>(vk_pipeline->creationResult)
                      : static_cast<i32>(VK_ERROR_INITIALIZATION_FAILED);
      const u32 rt0 =
          desc.renderTargetCount
              ? static_cast<u32>(desc.renderTargetFormat[0])
              : static_cast<u32>(plume::RenderFormat::UNKNOWN);

      BD_ERROR(
          \"CreateHostGraphicsPipeline({}) failed: VkResult={} occurrence={} \"
          \"render_pass={} vs_result={} ps_result={} rt_count={} rt0={} depth={} \"
          \"samples=0x{:X} topology={} cull={} fill={} | GPU='{}' \"
          \"api={}.{}.{} driver=0x{:08X} vendor=0x{:04X} device=0x{:04X}\",
          tag ? tag : \"?\", vk_result, n,
          vk_pipeline && vk_pipeline->renderPass != VK_NULL_HANDLE ? 1 : 0,
          shader_result(desc.vertexShader), shader_result(desc.pixelShader),
          desc.renderTargetCount, rt0, static_cast<u32>(desc.depthTargetFormat),
          static_cast<u32>(desc.multisampling.sampleCount),
          static_cast<u32>(desc.primitiveTopology),
          static_cast<u32>(desc.cullMode), static_cast<u32>(desc.fillMode),
          device->getDescription().name, VK_API_VERSION_MAJOR(props.apiVersion),
          VK_API_VERSION_MINOR(props.apiVersion),
          VK_API_VERSION_PATCH(props.apiVersion), props.driverVersion,
          props.vendorID, props.deviceID);
    }

    CheckDeviceRemoved(tag ? tag : \"pipeline\");
    return nullptr;
  }
#endif

  return pipeline;
}
"""
replace_once(device_cpp, old, new, "Vulkan pipeline diagnostics and throttling")

print("Android v12 Vulkan diagnostics transforms applied successfully")
