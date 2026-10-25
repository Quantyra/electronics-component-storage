"""OpenSCAD static renders of actual exported STL geometry, then a PNG contact sheet."""
from pathlib import Path
import argparse, json, subprocess, shutil, sys

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--openscad',default=shutil.which('openscad') or shutil.which('openscad.com') or 'openscad')
p.add_argument('--deps', default='')
args=p.parse_args()
if args.deps: sys.path.insert(0,args.deps)
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps
(ROOT/'previews').mkdir(exist_ok=True)
for view in ('cases','racks','print'):
    result=subprocess.run([args.openscad,'-o',str(ROOT/'previews'/('cad-'+view+'.png')),
        '--preview','--autocenter','--viewall','--projection=o','--imgsize=1500,650',
        '--colorscheme=Tomorrow','-D','view='+json.dumps(view),str(ROOT/'cad/preview.scad')],
        capture_output=True,text=True)
    if result.returncode or 'ERROR:' in result.stderr or 'WARNING:' in result.stderr:
        raise RuntimeError('OpenSCAD preview failed: '+view)
    print('Rendered',view,flush=True)

def cropped(path):
    img=Image.open(path).convert('RGB')
    difference=ImageChops.difference(img,Image.new('RGB',img.size,img.getpixel((0,0))))
    bounds=difference.getbbox()
    if bounds:
        x0,y0,x1,y1=bounds
        img=img.crop((max(0,x0-24),max(0,y0-24),min(img.width,x1+24),min(img.height,y1+24)))
    return img

def panel(canvas,path,rect):
    x,y,w,h=rect
    img=ImageOps.contain(cropped(path),(w,h),Image.Resampling.LANCZOS)
    canvas.paste(img,(x+(w-img.width)//2,y+(h-img.height)//2))

canvas=Image.new('RGB',(1500,1470),'#fafafa')
d=ImageDraw.Draw(canvas)
try:
    font=ImageFont.truetype('DejaVuSans.ttf',25)
    small=ImageFont.truetype('DejaVuSans.ttf',21)
except OSError:
    font=small=ImageFont.load_default()
d.text((25,15),'Quantyra electronics component storage - v1.0.0',fill='#202c35',font=font)
d.text((25,50),'Actual exported STL geometry rendered by OpenSCAD - physical fit unverified',fill='#40525f',font=small)
panel(canvas,ROOT/'previews/cad-cases.png',(0,135,1500,580))
d.text((25,85),'Closed 1x1 / 2x1 / 2x2 / 3x3 cases; exploded 1x1 at right',fill='#202c35',font=small)
d.text((25,112),'Outer W x L x H / mm: 24 x 100 x 20; 50 x 100 x 20; 50 x 100 x 42; 76 x 100 x 64',fill='#40525f',font=small)
panel(canvas,ROOT/'previews/cad-racks.png',(0,825,1500,625))
d.text((25,765),'Upright use: 36 narrow / 9 medium / 4 large bays; one case partly withdrawn per rack',fill='#202c35',font=small)
d.text((25,795),'Each full rack: 158.8 W x 102.4 D x 134.8 H mm. Separate fixed partition layouts.',fill='#40525f',font=small)
canvas.save(ROOT/'previews/actual-cad-preview.png')
canvas=Image.new('RGB',(1500,780),'#fafafa')
panel(canvas,ROOT/'previews/cad-print.png',(0,130,1500,650))
d=ImageDraw.Draw(canvas)
d.text((25,15),'Rack PRINT orientation: back DOWN, openings UP',fill='#202c35',font=font)
d.text((25,55),'158.8 x 134.8 mm footprint; 102.4 mm high. With 5 mm brim: 168.8 x 144.8 mm.',fill='#40525f',font=small)
d.text((25,85),'Gray reference bed at Z=0; full solid back at Z=0..2; all openings face +Z.',fill='#40525f',font=small)
canvas.save(ROOT/'previews/rack-print-orientation.png')
