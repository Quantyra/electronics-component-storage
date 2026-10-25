"""Verify the complete public inventory, source notices and exact release mesh bytes."""
from pathlib import Path
import argparse, hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--write',action='store_true',help='Refresh inventory after intentional review')
p.add_argument('--deps',default='')
args=p.parse_args()
if args.deps: sys.path.insert(0,args.deps)
from PIL import Image
EXPECTED_STLS = {'body_1x1.stl': 'e23701a7bc8025fcd6a57abe599f0d2fea50aaf47f7fd961a890de935d77ae0a', 'body_2x1.stl': '93a0fd8e804c64281417024921fcc69163d9b1e9da75f15d8754dc652b1e3ba2', 'body_2x2.stl': '3b1fd71ee08d56dbe5b01525ba5544ceb4e838d6699539bb1fe2c2c970f035e8', 'body_3x3.stl': '61a57f5f1f6216ee5b897ff156030c1f6c0d55ddf24bf5de3f84e52c33440718', 'lid_1.stl': 'bd72f4b8808603391551b4f6ae1d9b3e85df5ae9f7effb0ea2bba9076a66a5d8', 'lid_2.stl': 'e468a922dbd72052d852603c7f1fd4d4caf3196ee5d5579a8764278f7e3c409e', 'lid_3.stl': '881dac7399c446730a5d18a2babb8815621a79f8561611cf339a403b1e1a13a8', 'rack_large_4.stl': '9532842c26a34ec169f19b0a85f0e4d2eb7ff17d35d2b7a5120fa4ed2f3793a4', 'rack_medium_9.stl': '61445b5acc4887f00ee020cc2371154a508577fd299810d22a65f28764126d80', 'rack_narrow_36.stl': '9780b61b442da058e212fe94681205da04fecd6d569a1c3c2f83e865e2e16568', 'rack_short_18.stl': '58af8322ae903aed498da1c732ead38cc68de5b388efd674cc691abc713fb04b', 'rack_test_2x2.stl': '109bf88bc86568c6c6ef9ba1c51668a02c8508be67632adc42f12b5da32cace8'}
LICENSE_SHA256 = '1378410f52f977bc20cfa85054f6d2075f6b222de18492d14f63f9bd544e9f95'

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and
                  not any(x in {'.git','__pycache__','.venv'} for x in p.relative_to(ROOT).parts)
                  and p.suffix != '.pyc')
def key(p): return p.relative_to(ROOT).as_posix()
errors=[]
def check(ok, text):
    if not ok: errors.append(text)
all_files=files()
mesh_files={p.name:digest(p) for p in all_files if p.suffix=='.stl'}
check(mesh_files==EXPECTED_STLS,'Exact 12-mesh inventory/hash mismatch')
check(digest(ROOT/'LICENSE')==LICENSE_SHA256,'License text changed')
# Publication hygiene: private planning identifiers, machine paths and local history.
patterns=[r'(?i)\b[SE]0\d{2}\b',r'(?i)[A-Z]:[/\\](?:Users|Program Files)',
          r'(?i)pqcf-'+'private|private-'+'artifacts|QX'+'ccel\b|session[_ -]?id',
          r'(?i)patent '+'pending']
for f in all_files:
    content=f.read_bytes().decode('utf-8',errors='ignore')
    if f.suffix not in {'.png'}:
        for pattern in patterns: check(not re.search(pattern,content),'Private/unsupported content: '+key(f))
    if f.suffix=='.md':
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',content):
            if ':' in link or link.startswith('#'): continue
            target=link.split('#')[0]
            check((f.parent/target).exists() or (args.write and target in {'manifest.json','SHA256SUMS'}),
                  'Broken local link: '+key(f)+' -> '+link)
    if f.suffix=='.png':
        with Image.open(f) as im:
            im.verify()
        with Image.open(f) as im:
            check(not im.getexif(),'Unexpected image EXIF: '+key(f))
            metadata=json.dumps(im.info,default=str)
            for pattern in patterns: check(not re.search(pattern,metadata),'Private image metadata: '+key(f))
check('doi:' not in (ROOT/'CITATION.cff').read_text().lower(),'Unexpected DOI field')
check('CERN-OHL-S-2.0' in (ROOT/'CITATION.cff').read_text(),'Missing CFF license')
items=[dict(path=key(f),bytes=f.stat().st_size,sha256=digest(f)) for f in all_files
       if f.name not in {'manifest.json','SHA256SUMS'}]
if errors:
    print('\n'.join(errors));sys.exit(1)
if args.write:
    manifest=dict(version='v1.0.0',source_location='https://github.com/Quantyra/electronics-component-storage',
                  license='CERN-OHL-S-2.0',stl_count=12,files=items)
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    sums=''.join(digest(f)+'  '+key(f)+'\n' for f in files() if f.name!='SHA256SUMS')
    (ROOT/'SHA256SUMS').write_text(sums,encoding='utf-8',newline='\n')
else:
    check((ROOT/'manifest.json').exists(),'Missing manifest.json')
    check((ROOT/'SHA256SUMS').exists(),'Missing SHA256SUMS')
    if errors: print('\n'.join(errors));sys.exit(1)
    check(json.loads((ROOT/'manifest.json').read_text())['files']==items,'Manifest inventory/bytes mismatch')
    expected=''.join(digest(f)+'  '+key(f)+'\n' for f in all_files if f.name!='SHA256SUMS')
    check((ROOT/'SHA256SUMS').read_text()==expected,'SHA256SUMS inventory/bytes mismatch')
if errors:
    print('\n'.join(errors));sys.exit(1)
print('PASS: exact 12 meshes, license, inventory, hashes, local links and publication hygiene')
