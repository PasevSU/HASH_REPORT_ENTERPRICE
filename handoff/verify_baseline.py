from pathlib import Path
import json,hashlib,sys
base=Path(__file__).resolve().parents[1]
manifest=json.loads((Path(__file__).parent/'BASELINE_INVENTORY.json').read_text(encoding='utf-8'))
fail=[]
for item in manifest['files']:
 p=base/item['path']
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
  fail.append(item['path'])
print(f"Baseline files checked: {len(manifest['files'])}; mismatches: {len(fail)}")
for f in fail:print('MISMATCH',f)
sys.exit(bool(fail))
