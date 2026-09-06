#!/usr/bin/env python3
"""Package verified v2.3 source-built native libraries with existing SAF launcher."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
from build_v22_experiment import patch_manifest,patch_dex,BASE_SHA,CERT_SHA,sha,require
from cryptography import x509
from cryptography.hazmat.primitives import serialization
p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--main',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--cert',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
require(sha(a.base.read_bytes())==BASE_SHA,'Unexpected base APK')
require(sha(x509.load_pem_x509_certificate(a.cert.read_bytes()).public_bytes(serialization.Encoding.DER))==CERT_SHA,'Signing certificate mismatch')
libs={'lib/arm64-v8a/libmain.so':a.main.read_bytes(),'lib/arm64-v8a/librexruntime.so':a.runtime.read_bytes()}
all_native=b''.join(libs.values())
for marker in [b'N18-after-app-OnInitialize-ok',b'G21-hcg-pipeline-ok',b'G33-present-ok',b'[pso-fail-kind]',b'[shader-capture]',b'native-stage.log']:
 require(marker in all_native,'Missing native diagnostic: '+repr(marker))
a.output.mkdir(parents=True,exist_ok=True)
unsigned=a.output/'v23-unsigned.apk';aligned=a.output/'v23-aligned.apk';final=a.output/'reblue-android-arm64-v2.3-render-diagnostics.apk'
with zipfile.ZipFile(a.base) as src,zipfile.ZipFile(unsigned,'w') as dst:
 for e in src.infolist():
  if e.filename.startswith('META-INF/') and e.filename.endswith(('.SF','.RSA','.DSA','.EC','MANIFEST.MF')):continue
  data=src.read(e.filename)
  if e.filename in libs:data=libs[e.filename]
  elif e.filename=='AndroidManifest.xml':data=patch_manifest(data,23,'2.3')
  elif e.filename=='classes.dex':data=patch_dex(data,'2.3')
  dst.writestr(e,data)
subprocess.run(['zipalign','-P','16','-f','4',str(unsigned),str(aligned)],check=True)
subprocess.run(['apksigner','sign','--key',str(a.key),'--cert',str(a.cert),'--min-sdk-version','28','--out',str(final),str(aligned)],check=True)
subprocess.run(['apksigner','verify','--verbose','--print-certs',str(final)],check=True)
subprocess.run(['zipalign','-c','-P','16','4',str(final)],check=True)
metadata={'apk':final.name,'sha256':sha(final.read_bytes()),'package':'org.reblue.android.saf','versionCode':23,'versionName':'2.3','certificate_sha256':CERT_SHA,'native':{k:sha(v) for k,v in libs.items()},'device_tested':False,'shader_cache_populated':False}
(a.output/'build-v23.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(metadata,indent=2))
