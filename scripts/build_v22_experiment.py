#!/usr/bin/env python3
"""Reproducible, one-variable APK experiment on the exact v2.1 binary.

Not a full source rebuild. Keep all machine code and ELF symbol sizes intact;
remove the unused VS RuntimeDescriptorArray capability and replace its two
words with two OpNops inside main. SPIR-V validation is mandatory before and
after packaging. APK version metadata changes to 2.2 / 22.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import subprocess
import zipfile
import zlib

from elftools.elf.elffile import ELFFile

BASE_SHA = "f2a70492105acc19bf13c1ecbef09bd3cf01de6ad479c50f488ae7a86a3ba24d"
VS_SHA = "5b89745deb51e88be59ecb525a316e3dd02fd2f34587df6675a373b72c67e030"
CERT_SHA = "49c6c9801b1528bd840180ee55d4c69ea453b3f71639cb714d30d786d3932c52"
VS_SYMBOL = "_ZL21g_bd_2d_blit_vs_spirv"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_vs(blob):
    require(sha(blob) == VS_SHA, "Unexpected source vertex shader")
    words = list(struct.unpack('<' + 'I' * (len(blob) // 4), blob))
    instructions = []
    cursor = 5
    while cursor < len(words):
        count = words[cursor] >> 16
        require(count and cursor + count <= len(words), "Invalid instruction bounds")
        instructions.append(words[cursor:cursor + count])
        cursor += count
    # SPIR-V OpCapability=17, RuntimeDescriptorArray=5302; OpNop=0.
    removed = sum(i == [(2 << 16) | 17, 5302] for i in instructions)
    require(removed == 1, "Expected exactly one RuntimeDescriptorArray capability")
    require(not any(i[0] & 0xffff == 29 for i in instructions), "VS uses a runtime array")
    require(sum(i[0] & 0xffff == 253 for i in instructions) == 1, "Expected one OpReturn")
    output = words[:5]
    for i in instructions:
        if i == [(2 << 16) | 17, 5302]:
            continue
        if i[0] & 0xffff == 253:
            output += [1 << 16, 1 << 16]
        output += i
    result = struct.pack('<' + 'I' * len(output), *output)
    require(len(result) == len(blob), "SPIR-V byte size must remain identical")
    return result


def patch_manifest(data, version_code=22, version_name="2.2"):
    """Change only the typed versionCode and its versionName string-pool item."""
    b = bytearray(data)
    cursor = struct.unpack_from('<H', b, 2)[0]
    strings = []
    locations = []
    version_code_count = 0
    version_name_count = 0

    def length_at(pos, utf8):
        if utf8:
            x = b[pos]
            return (((x & 0x7f) << 8) | b[pos+1], pos+2) if x & 0x80 else (x, pos+1)
        x = struct.unpack_from('<H', b, pos)[0]
        return (((x & 0x7fff) << 16) | struct.unpack_from('<H', b, pos+2)[0], pos+4) if x & 0x8000 else (x, pos+2)

    while cursor < len(b):
        kind, header, size = struct.unpack_from('<HHI', b, cursor)
        require(size >= header and cursor + size <= len(b), "Invalid AXML chunk")
        if kind == 1:
            count, _, flags, start, _ = struct.unpack_from('<IIIII', b, cursor+8)
            utf8 = bool(flags & 0x100)
            for index in range(count):
                relative = struct.unpack_from('<I', b, cursor+header+index*4)[0]
                pos = cursor + start + relative
                length, pos = length_at(pos, utf8)
                if utf8:
                    length, pos = length_at(pos, True)
                byte_count = length if utf8 else length*2
                encoding = 'utf-8' if utf8 else 'utf-16-le'
                strings.append(bytes(b[pos:pos+byte_count]).decode(encoding))
                locations.append((pos, byte_count, encoding))
        elif kind == 0x102:
            ext = cursor + header
            _, name, start, attr_size, count = struct.unpack_from('<IIHHH', b, ext)
            if strings[name] == 'manifest':
                for i in range(count):
                    attr = ext + start + attr_size*i
                    name_index = struct.unpack_from('<I', b, attr+4)[0]
                    name = strings[name_index]
                    if name == 'versionCode':
                        require(b[attr+15] == 0x10 and struct.unpack_from('<I', b, attr+16)[0] == 21,
                                "Unexpected typed versionCode")
                        struct.pack_into('<I', b, attr+16, version_code)
                        version_code_count += 1
                    elif name == 'versionName':
                        require(b[attr+15] == 3, "Expected versionName string")
                        index = struct.unpack_from('<I', b, attr+16)[0]
                        require(strings[index] == '2.1', "Unexpected versionName")
                        pos, count_bytes, encoding = locations[index]
                        replacement = version_name.encode(encoding)
                        require(len(replacement) == count_bytes, "Manifest string size changed")
                        b[pos:pos+count_bytes] = replacement
                        version_name_count += 1
        cursor += size
    require(version_code_count == version_name_count == 1, "Version attributes not unique")
    return bytes(b)


def patch_dex(data, version_name="2.2"):
    b = bytearray(data)
    for old, new in [(b're:Blue Android v2.1 diagnostic', ('re:Blue Android v'+version_name+' diagnostic').encode()),
                     (b're:Blue Android v1.5', ('re:Blue Android v'+version_name).encode())]:
        require(b.count(old) == 1 and len(old) == len(new), "Unexpected DEX version label")
        b = b.replace(old, new)
    b[12:32] = hashlib.sha1(b[32:]).digest()
    struct.pack_into('<I', b, 8, zlib.adler32(b[12:]) & 0xffffffff)
    return bytes(b)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('base', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--key', type=Path, required=True)
    p.add_argument('--cert', type=Path, required=True)
    args = p.parse_args()
    require(sha(args.base.read_bytes()) == BASE_SHA, "Wrong base APK")
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    certificate = x509.load_pem_x509_certificate(args.cert.read_bytes())
    require(sha(certificate.public_bytes(serialization.Encoding.DER)) == CERT_SHA,
            "Wrong persistent signing certificate")
    subprocess.run(['apksigner', 'verify', str(args.base)], check=True)
    args.output.mkdir(parents=True, exist_ok=True)
    unsigned = args.output / 'v22-unsigned.apk'
    aligned = args.output / 'v22-aligned.apk'
    signed = args.output / 'reblue-android-arm64-v2.2-vs-capability-test.apk'
    changes = {}
    with zipfile.ZipFile(args.base) as src:
        main_name = 'lib/arm64-v8a/libmain.so'
        original = src.read(main_name)
        elf = ELFFile(io.BytesIO(original))
        symbols = [s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name == VS_SYMBOL]
        require(len(symbols) == 1, "Shader symbol is ambiguous")
        symbol = symbols[0]
        section = elf.get_section(symbol['st_shndx'])
        offset = section['sh_offset'] + symbol['st_value'] - section['sh_addr']
        old_vs = original[offset:offset+symbol['st_size']]
        new_vs = patch_vs(old_vs)
        new_main = original[:offset] + new_vs + original[offset+len(old_vs):]
        require(new_main[:offset] == original[:offset] and new_main[offset+len(new_vs):] == original[offset+len(old_vs):],
                "Change escaped the shader symbol")
        for label, shader in [('v21-vs', old_vs), ('v22-vs', new_vs)]:
            path = args.output / (label + '.spv')
            path.write_bytes(shader)
            subprocess.run(['spirv-val', '--target-env', 'vulkan1.1', str(path)], check=True)
            subprocess.run(['spirv-dis', str(path), '-o', str(path.with_suffix('.spvasm'))], check=True)
        with zipfile.ZipFile(unsigned, 'w') as dst:
            for entry in src.infolist():
                if entry.filename.startswith('META-INF/') and entry.filename.endswith(('.SF', '.RSA', '.DSA', '.EC', 'MANIFEST.MF')):
                    continue
                data = src.read(entry.filename)
                if entry.filename == main_name:
                    new_data = new_main
                elif entry.filename == 'AndroidManifest.xml':
                    new_data = patch_manifest(data)
                elif entry.filename == 'classes.dex':
                    new_data = patch_dex(data)
                else:
                    new_data = data
                if new_data != data:
                    changes[entry.filename] = {'before': sha(data), 'after': sha(new_data)}
                dst.writestr(entry, new_data)
    require(set(changes) == {'AndroidManifest.xml', 'classes.dex', main_name}, "Unexpected payload changes")
    subprocess.run(['zipalign', '-P', '16', '-f', '4', str(unsigned), str(aligned)], check=True)
    subprocess.run(['apksigner', 'sign', '--key', str(args.key), '--cert', str(args.cert),
                    '--min-sdk-version', '28', '--out', str(signed), str(aligned)], check=True)
    subprocess.run(['apksigner', 'verify', '--verbose', '--print-certs', str(signed)], check=True)
    subprocess.run(['zipalign', '-c', '-P', '16', '4', str(signed)], check=True)
    metadata = {'base_sha256': BASE_SHA, 'apk': signed.name, 'sha256': sha(signed.read_bytes()),
                'method': 'Fixed-size SPIR-V binary edit; not a native source rebuild',
                'experiment': 'Remove unused RuntimeDescriptorArray capability from HCG VS only',
                'changes': changes, 'vs_symbol_file_offset': offset, 'vs_size_bytes': len(new_vs),
                'vs_sha256': sha(new_vs), 'signing_certificate_sha256': CERT_SHA,
                'known_inherited_regression': 'v2.1 native-stage.log and N18 markers remain absent; PSO diagnostics unchanged',
                'device_tested': False}
    (args.output / 'build-v22.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
