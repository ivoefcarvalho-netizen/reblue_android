#!/usr/bin/env python3
"""Inspect the packaged APK, never a loose shader or an intermediate .so.

Dependencies: requirements-audit.txt; spirv-dis, spirv-val and apksigner on PATH.
Without apksigner the inspection still runs, but the release gate fails closed.
No device access, private key, game data or APK modification is required.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

PACKAGE = "org.reblue.android.saf"
CERT = "49c6c9801b1528bd840180ee55d4c69ea453b3f71639cb714d30d786d3932c52"
SYMBOLS = {"vs": "_ZL21g_bd_2d_blit_vs_spirv", "ps": "_ZL21g_bd_2d_blit_ps_spirv"}
NATIVE_MARKERS = ["native-stage.log", "N18-after-app-OnInitialize-ok",
                  "[pso-fail-kind]", "[pso-fail-slot]", "[pso-fail-elem]",
                  "CreateHostGraphicsPipeline({}) failed: VkResult={}"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract_shader(elf, symbol):
    table = elf.get_section_by_name(".symtab")
    if table is None:
        raise ValueError("Symbol table absent: cannot identify the HCG shader reliably")
    matches = [s for s in table.iter_symbols() if s.name == symbol]
    if len(matches) != 1:
        raise ValueError(f"Expected one {symbol}, got {len(matches)}")
    s = matches[0]
    section = elf.get_section(s["st_shndx"])
    start = s["st_value"] - section["sh_addr"]
    end = start + s["st_size"]
    if start < 0 or end > section["sh_size"]:
        raise ValueError("Shader symbol extends outside its ELF section")
    blob = section.data()[start:end]
    if blob[:4] != b"\x03\x02\x23\x07" or len(blob) % 4:
        raise ValueError("Symbol is not a little-endian SPIR-V module")
    return blob


def inspect_assembly(text):
    """Report declarations; do not confuse them with enabled device features."""
    return {
        "capabilities": re.findall(r"OpCapability\s+(\w+)", text),
        "memory_models": re.findall(r"OpMemoryModel\s+(\w+)\s+(\w+)", text),
        "locations": re.findall(r"OpDecorate\s+(%\S+)\s+Location\s+(\d+)", text),
        "push_constant_offsets": re.findall(
            r"OpMemberDecorate\s+(%\S+)\s+(\d+)\s+Offset\s+(\d+)", text),
        "descriptor_sets": re.findall(r"OpDecorate\s+(%\S+)\s+DescriptorSet\s+(\d+)", text),
        "bindings": re.findall(r"OpDecorate\s+(%\S+)\s+Binding\s+(\d+)", text),
        "has_int64_type": bool(re.search(r"OpTypeInt\s+64\b", text)),
        "has_physical_storage": "PhysicalStorageBuffer" in text,
        "has_runtime_array_type": "OpTypeRuntimeArray" in text,
    }


def audit(apk_path, output, target_env, minimum_version):
    from androguard.core.apk import APK
    from elftools.elf.elffile import ELFFile
    from loguru import logger
    logger.disable("androguard")
    output.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "apk": apk_path.name, "sha256": sha(apk_path.read_bytes()),
              "target_env": target_env, "checks": [], "shaders": {},
              "limitations": [
                  "Static inspection does not execute Android or Vulkan.",
                  "Marker presence does not prove that the corresponding code runs.",
                  "Shader inputs do not prove the runtime vertex-input filtering.",
                  "Pipeline layout, device features and push-constant uploads require runtime evidence."]}

    def check(name, ok, detail):
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})

    report["tool_versions"] = {}
    for tool, flag in (("spirv-val", "--version"), ("spirv-dis", "--version"), ("apksigner", "version")):
        if shutil.which(tool):
            p = subprocess.run([tool, flag], capture_output=True, text=True, check=True)
            report["tool_versions"][tool] = p.stdout.strip()
    apk = APK(str(apk_path))
    report["package"] = apk.get_package()
    report["version_code"] = apk.get_androidversion_code()
    report["version_name"] = apk.get_androidversion_name()
    report["min_sdk"] = apk.get_min_sdk_version()
    check("package", report["package"] == PACKAGE, report["package"])
    check("min_sdk", report["min_sdk"] is not None and int(report["min_sdk"]) <= 28,
          report["min_sdk"])
    check("version_code", int(report["version_code"] or 0) >= minimum_version,
          {"actual": report["version_code"], "minimum": minimum_version})
    # These are certificate fingerprints, NOT cryptographic signature verification.
    certs = sorted({sha(c) for c in apk.get_certificates_der_v2() + apk.get_certificates_der_v3()})
    report["certificate_sha256"] = certs
    check("persistent_certificate", certs == [CERT], certs)
    signer = shutil.which("apksigner")
    if signer:
        p = subprocess.run([signer, "verify", "--verbose", "--print-certs", str(apk_path)],
                           capture_output=True, text=True)
        report["signature_verification"] = p.stdout + p.stderr
        check("signature_integrity", p.returncode == 0, p.returncode)
    else:
        check("signature_integrity", False, "apksigner unavailable; not verified")

    with zipfile.ZipFile(apk_path) as z:
        check("unique_zip_entries", len(z.namelist()) == len(set(z.namelist())), "Reject duplicate paths")
        libs = {n: z.read(n) for n in z.namelist() if n.startswith("lib/") and n.endswith(".so")}
        report["native_libraries"] = {n: {"bytes": len(b), "sha256": sha(b)} for n, b in libs.items()}
        for name in ("libmain.so", "librexruntime.so", "libprobe.so"):
            key = "lib/arm64-v8a/" + name
            check("library_" + name, key in libs, key)
        for n, blob in libs.items():
            e = ELFFile(io.BytesIO(blob))
            check("architecture_" + n, e.elfclass == 64 and e["e_machine"] == "EM_AARCH64",
                  {"class": e.elfclass, "machine": e["e_machine"]})
        native = b"\0".join(libs.values())
        report["native_markers"] = {s: s.encode() in native for s in NATIVE_MARKERS}
        for s, present in report["native_markers"].items():
            check("native_marker_" + s, present, "Search native libraries only, excluding DEX")
        main = ELFFile(io.BytesIO(libs["lib/arm64-v8a/libmain.so"]))
        for stage, symbol in SYMBOLS.items():
            blob = extract_shader(main, symbol)
            path = output / ("hcg_blit_" + stage + ".spv")
            path.write_bytes(blob)
            item = {"symbol": symbol, "bytes": len(blob), "sha256": sha(blob)}
            report["shaders"][stage] = item
            for tool in ("spirv-val", "spirv-dis"):
                check(stage + "_" + tool + "_available", shutil.which(tool) is not None, tool)
            if shutil.which("spirv-val"):
                p = subprocess.run(["spirv-val", "--target-env", target_env, str(path)],
                                   capture_output=True, text=True)
                item["validation"] = {"returncode": p.returncode, "output": p.stdout + p.stderr}
                check(stage + "_spirv_valid", p.returncode == 0, item["validation"])
            if shutil.which("spirv-dis"):
                p = subprocess.run(["spirv-dis", str(path)], capture_output=True, text=True, check=True)
                (output / ("hcg_blit_" + stage + ".spvasm")).write_text(p.stdout)
                item.update(inspect_assembly(p.stdout))
                forbidden = {"Int64", "Int64Atomics", "PhysicalStorageBufferAddresses"}
                check(stage + "_no_bda_int64", not (forbidden & set(item["capabilities"]))
                      and not item["has_int64_type"] and not item["has_physical_storage"], item["capabilities"])
                item["unused_runtime_array_capability"] = (
                    "RuntimeDescriptorArray" in item["capabilities"] and not item["has_runtime_array_type"])
    report["release_gate_passed"] = all(c["passed"] for c in report["checks"])
    (output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target-env", default="vulkan1.1")
    parser.add_argument("--minimum-version-code", type=int, default=21)
    args = parser.parse_args()
    r = audit(args.apk, args.output, args.target_env, args.minimum_version_code)
    print(json.dumps({"release_gate_passed": r["release_gate_passed"],
                      "failed_checks": [c for c in r["checks"] if not c["passed"]]}, indent=2))
    return 0 if r["release_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
