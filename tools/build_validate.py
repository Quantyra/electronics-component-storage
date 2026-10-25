"""Export original CAD, then test the resulting meshes (not only parameters).
Python 3 with numpy, trimesh, manifold3d, scipy, matplotlib. No downloads.
Default: validate supplied meshes. --regenerate also proves temporary CAD exports equivalent.
"""
from pathlib import Path
import argparse, concurrent.futures, hashlib, json, os, subprocess, sys, shutil, tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--openscad', default=shutil.which('openscad') or shutil.which('openscad.com') or 'openscad')
parser.add_argument('--deps', default=os.environ.get('COMPONENT_STORAGE_DEPS', ''))
parser.add_argument('--regenerate', action='store_true', help='Export to temporary files and compare solids; never overwrite supplied STLs')
args = parser.parse_args()
if args.deps:
    sys.path.insert(0, args.deps)
import numpy as np
import trimesh
import manifold3d as md

SCAD = ROOT / 'cad/storage.scad'
SIZES = {'1x1': (1, 1), '2x1': (2, 1), '2x2': (2, 2), '3x3': (3, 3)}
RACKS = {'test_2x2': (2, 2, 1, 1), 'narrow_36': (6, 6, 1, 1),
         'short_18': (6, 6, 2, 1), 'medium_9': (6, 6, 2, 2),
         'large_4': (6, 6, 3, 3)}
jobs = {}
for name, (nx, nz) in SIZES.items():
    jobs['body_' + name] = dict(part='body', span_x=nx, span_z=nz)
for nx in (1, 2, 3):
    jobs['lid_' + str(nx)] = dict(part='lid', span_x=nx)
for name, (cols, rows, bx, bz) in RACKS.items():
    jobs['rack_' + name] = dict(part='rack', cols=cols, rows=rows, bay_x=bx, bay_z=bz)

def export(name, params):
    out = EXPORT_ROOT / (name + '.stl')
    cmd = [args.openscad, '-o', str(out)]
    for key, value in params.items():
        cmd += ['-D', key + '=' + json.dumps(value)]
    cmd += [str(SCAD)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode or 'ERROR:' in p.stderr or 'WARNING:' in p.stderr:
        raise RuntimeError(name + ': OpenSCAD export failed (check executable and CAD)')
    return name

temp_exports = tempfile.TemporaryDirectory(prefix='component-storage-')
EXPORT_ROOT = Path(temp_exports.name)
if args.regenerate:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for name in pool.map(lambda kv: export(*kv), jobs.items()):
            print('Exported', name, flush=True)

def manifold(mesh):
    return md.Manifold(md.Mesh(np.asarray(mesh.vertices, dtype=np.float32),
                               np.asarray(mesh.faces, dtype=np.uint32)))

def translated(mesh, xyz):
    copy = mesh.copy()
    copy.apply_translation(xyz)
    return copy

def box(bounds):
    bounds = np.asarray(bounds)
    m = trimesh.creation.box(extents=bounds[1]-bounds[0])
    m.apply_translation(bounds.mean(axis=0))
    return m

def overlap(a, b):
    return abs((manifold(a) ^ manifold(b)).volume())

checks = []
def check(name, condition, **evidence):
    checks.append(dict(test=name, passed=bool(condition), **evidence))
    if not condition:
        print('FAILED:', name, evidence, flush=True)

meshes, stats = {}, {}
for name in jobs:
    m = trimesh.load_mesh(ROOT / 'stl' / (name + '.stl'), process=True)
    meshes[name] = m
    count = len(m.split())
    stats[name] = dict(bounds_mm=m.bounds.round(5).tolist(),
                       dimensions_mm=m.extents.round(5).tolist(),
                       volume_mm3=round(float(m.volume), 4),
                       watertight=bool(m.is_watertight), parts=count,
                       triangles=len(m.faces))
    check(name + ' solid', m.is_watertight and m.is_winding_consistent and
          m.volume > 0 and count == 1, **stats[name])
    check(name + ' printable placement on Z=0',abs(m.bounds[0,2])<.002,
          min_z_mm=float(m.bounds[0,2]))
    check(name + ' nonnegative print XY bounds',bool(np.all(m.bounds[0,:2]>=-.002)),
          xy_bounds_mm=m.bounds[:,:2].round(5).tolist())
    # 5 mm brim all round on nominal 220x220; maximum height 250.
    dims = m.extents
    check(name + ' nominal printer envelope with brim',
          dims[0]+10 <= 220 and dims[1]+10 <= 220 and dims[2] <= 250)

# Simple brute-force ray/triangle intersections avoids optional rtree dependency.
def hit(mesh, origin, direction):
    t = mesh.triangles
    e1, e2 = t[:, 1]-t[:, 0], t[:, 2]-t[:, 0]
    p = np.cross(np.tile(direction, (len(t), 1)), e2)
    a = (e1*p).sum(axis=1)
    valid = np.abs(a) > 1e-9
    inv = np.zeros(len(a)); inv[valid] = 1/a[valid]
    s = origin-t[:, 0]
    u = inv*(s*p).sum(axis=1)
    q = np.cross(s, e1)
    v = inv*(q*np.asarray(direction)).sum(axis=1)
    dist = inv*(e2*q).sum(axis=1)
    valid &= (u >= -1e-7) & (v >= -1e-7) & (u+v <= 1+1e-7) & (dist > 1e-7)
    return float(dist[valid].min()) if valid.any() else float('inf')

assemblies = {}
dimensions = {}
for name, (nx, nz) in SIZES.items():
    w, h = nx*26-2, nz*22-2
    b = meshes['body_' + name]
    l = translated(meshes['lid_' + str(nx)], [0, 0, h-3.2])
    assemblies[name] = [b, l]
    check(name + ' actual outer dimensions', np.allclose(b.extents, [w,100,h], atol=.002))
    vol = overlap(b, l)
    check(name + ' closed lid-body collision', vol < 1e-4, intersection_mm3=vol)
    # Convex swept envelope from actual STL vertices fills recesses/holes too:
    # a conservative continuous test of the ENTIRE withdrawal path, no sampling gaps.
    swept_points = np.vstack([l.vertices, l.vertices+[0, -100, 0]])
    swept = md.Manifold.hull_points(swept_points)
    vol = abs((manifold(b) ^ swept).volume())
    check(name + ' continuous lid withdrawal clearance', vol < 1e-4, intersection_mm3=vol)
    # Rear stop must actually collide when the slider is forced 1mm past closed.
    vol = overlap(b, translated(l, [0, 1, 0]))
    check(name + ' geometric rear stop', vol > 1, intersection_mm3=vol)
    # Cannot lift dovetail straight up: geometric retention, not a friction assertion.
    vol = overlap(b, translated(l, [0, 0, 1]))
    check(name + ' dovetail lift capture', vol > 1, intersection_mm3=vol)
    # Actual rays verify cavity side walls, front/rear walls, floor and lid.
    origin = np.array([w/2, 50, 5])
    whole = trimesh.util.concatenate([b,l])
    spans = []
    for axis in range(3):
        d = np.eye(3)[axis]
        spans.append(hit(whole, origin, d)+hit(whole, origin, -d))
    check(name + ' measured cavity walls', np.allclose(spans[:2], [w-4,93.2], atol=.002)
          and abs(spans[2]-(h-5.2))<.002, measured_center_spans_mm=spans)
    # Guaranteed unobstructed rectangular loading envelope, including rear lip.
    lo, hi = [2.001,4.801,2.001], [w-2.001,97.999,h-3.201]
    vol = overlap(whole, box([lo,hi]))
    check(name + ' full rectangular cavity', vol < 1e-4, intersection_mm3=vol)
    check(name + ' open cavity has no membrane', np.isinf(hit(b,origin,[0,0,1])))
    # Back stop distance derived by ray through actual lid rear face and body rear wall.
    stop_gap = hit(b, np.array([w/2,97.4,h-2.4]), [0,1,0])
    check(name + ' measured lid rear gap', abs(stop_gap-.4)<.002, rear_gap_mm=stop_gap)
    # M2 head envelope <=4 x1.4 fits within H with 0.2mm nominal overhead margin.
    head = trimesh.creation.cylinder(radius=2, height=1.4, sections=32)
    head.apply_translation([w/2,2.4,h-.9])
    assemblies[name].append(head)
    check(name + ' keeper head envelope', head.bounds[1,2] < h and
          overlap(head,b)<1e-4 and overlap(head,l)<1e-4)
    dimensions[name] = dict(outer_mm=[w,100,h], rectangular_cavity_mm=[w-4,93.2,h-5.2],
        recommended_max_loaded_envelope_mm=[w-7,92.2,h-6.2],
        lid_mm=meshes['lid_'+str(nx)].extents.round(5).tolist(),
        label_mm=[w-6,7], measured_center_cavity_spans_mm=spans)

# Rail normal clearance measured on mesh sections at y=50, away from features.
for name,(nx,nz) in SIZES.items():
    b=meshes['body_'+name]; l=assemblies[name][1]
    section=trimesh.intersections.mesh_plane(b,[0,1,0],[0,50,0])
    # Left sloping channel face: z-x constant, at z near lid height.
    candidates=[]
    for seg in section:
        dx,dz=seg[1,0]-seg[0,0],seg[1,2]-seg[0,2]
        if abs(dx)>.1 and abs(abs(dx)-abs(dz))<.002 and seg[:,0].max()<4 and seg[:,2].min()>nz*22-7:
            candidates.append(seg)
    check(name+' exported 45 degree rail found', len(candidates)>0)
    if candidates:
        constants=np.array([np.mean(seg[:,2]-seg[:,0]) for seg in candidates])
        lid_constant=(nz*22-2)-3.2-1.4
        c=float(np.min(abs(constants-lid_constant))/np.sqrt(2))
        check(name+' measured normal rail clearance',abs(c-.3)<.003, per_face_mm=c)
    (ROOT/'reports'/('section_'+name+'.json')).write_text(json.dumps(section.round(5).tolist(),indent=2),encoding='utf-8',newline='\n')

rack_report={}
for name,(cols,rows,bx,bz) in RACKS.items():
    printed=meshes['rack_'+name]
    pw,ph,pd=printed.extents
    # Anchored to BED coordinates, independent of the use/print inverse.
    # Interior epsilon avoids coincident-face numerical noise at exact slab edges.
    back_slab=box([[.001,.001,.001],[pw-.001,ph-.001,1.999]])
    required_back=float(back_slab.volume)
    missing=required_back-overlap(printed,back_slab)
    check(name+' full solid back in first 2 mm above bed',abs(missing)<.01,
          tested_back_slab_mm=[[.001,.001,.001],[pw-.001,ph-.001,1.999]],
          missing_back_mm3=float(missing))
    bay_voids=[]
    upward_distances=[]
    for i in range(cols//bx):
        for j in range(rows//bz):
            x,y=2+i*bx*26,2+j*bz*22
            # Extends ABOVE the mesh: any roof/back across a bay fails this test.
            bay_voids.append(box([[x+.001,y+.001,2.001],
                [x+bx*26-1.201,y+bz*22-1.201,103.4]]))
            upward_distances.append(hit(printed,
                np.array([x+(bx*26-1.2)/2,y+(bz*22-1.2)/2,2.001]),[0,0,1]))
    max_roof=max(overlap(printed,void) for void in bay_voids)
    check(name+' every bay clear upward with no bridging roof',max_roof<1e-4,
          tested_bays=len(bay_voids),max_bay_obstruction_mm3=max_roof)
    check(name+' upward rays escape every bay',all(np.isinf(d) for d in upward_distances),
          unobstructed_upward_rays=sum(np.isinf(d) for d in upward_distances).item())
    # Regression control: invert a correct mesh then put it on the bed. Extents
    # still look right, but its full back is on top and these mesh gates reject it.
    inverted=printed.copy()
    inverted.apply_transform(trimesh.transformations.rotation_matrix(np.pi,[1,0,0]))
    inverted.apply_translation([0,ph,pd])
    inverted_missing=required_back-overlap(inverted,back_slab)
    inverted_roof=max(overlap(inverted,void) for void in bay_voids)
    check(name+' regression rejects normalized back-on-top rack',
          inverted_missing>1 and inverted_roof>1,
          inverted_missing_back_mm3=float(inverted_missing),
          inverted_roof_obstruction_mm3=float(inverted_roof))
    r=printed.copy()
    # Invert the documented back-down print transform into upright use coordinates.
    transform=trimesh.transformations.rotation_matrix(np.pi/2,[1,0,0])
    r.apply_translation([0,0,-102.4]); r.apply_transform(transform)
    check(name+' inverse gives upright rack at origin',np.allclose(r.bounds,
          [[0,0,0],[cols*26+2.8,102.4,rows*22+2.8]],atol=.002),
          use_bounds_mm=r.bounds.round(5).tolist())
    typ={(1,1):'1x1',(2,1):'2x1',(2,2):'2x2',(3,3):'3x3'}[(bx,bz)]
    unit=trimesh.util.concatenate(assemblies[typ])
    worst=0; min_neighbor=None; instances=[]
    for i in range(cols//bx):
        for j in range(rows//bz):
            loc=[2.4+i*bx*26,0,2.4+j*bz*22]
            instance=translated(unit,loc)
            worst=max(worst,overlap(r,instance))
            # The convex sweep contains body, lid, screw head for continuous insertion.
            hull=md.Manifold.hull_points(np.vstack([instance.vertices,instance.vertices+[0,-101,0]]))
            worst=max(worst,abs((manifold(r)^hull).volume()))
            instances.append(instance)
    check(name+' all closed cases and insertion sweeps clear rack',worst<1e-4,
          cases=len(instances), max_intersection_mm3=worst)
    resting=translated(instances[0],[0,0,-.4])
    vol=overlap(r,resting)
    check(name+' case resting on shelf clears rack',vol<1e-4,intersection_mm3=vol)
    # AABB separation proves no case-to-case collision, including recessed grips/keeper.
    separation=[]
    for i,a in enumerate(instances):
        for b in instances[i+1:]:
            gaps=np.maximum(a.bounds[0]-b.bounds[1],b.bounds[0]-a.bounds[1])
            separation.append(float(gaps.max()))
    check(name+' adjacent assembled cases do not collide',min(separation)>0,
          minimum_axis_separation_mm=min(separation))
    rack_report[name]=dict(use_outer_mm=r.extents.round(5).tolist(),
        print_outer_mm=meshes['rack_'+name].extents.round(5).tolist(), cases=len(instances),
        print_bounds_mm=printed.bounds.round(5).tolist(),
        back_print_z_mm=[0,2],openings_print_direction='+Z',
        bay_opening_mm=[bx*26-1.2,100.4,bz*22-1.2], nominal_side_clearance_mm=.4)

if args.regenerate:
    for name, original in meshes.items():
        regenerated = trimesh.load_mesh(EXPORT_ROOT / (name + '.stl'), process=True)
        a, b = manifold(original), manifold(regenerated)
        difference = abs((a-b).volume()) + abs((b-a).volume())
        check(name + ' regenerated solid equivalence',
              regenerated.is_watertight and difference < .02 and
              np.allclose(original.bounds, regenerated.bounds, atol=.002),
              symmetric_difference_mm3=difference)
temp_exports.cleanup()
report=dict(version='v1.0.0', intended_printer='Ender-3 V3 SE; nominal 220x220x250 mm',
    physical_status='Physical fit, capacity, warping and load untested',
    clearance_definition='0.30 mm normal to each rail mating face, parametric',
    source_regeneration_tested=args.regenerate,
    dimensions=dimensions,racks=rack_report,mesh_statistics=stats,checks=checks,
    passed=sum(c['passed'] for c in checks),total=len(checks))
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports/geometry-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print('CHECKS:',report['passed'],'/',report['total'],flush=True)
if report['passed'] != report['total']:
    sys.exit(1)

# Section plot from actual mesh triangles; 3D images use OpenSCAD's depth renderer.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

fig,(ax,bx)=plt.subplots(1,2,figsize=(12,5))
for mesh,col in [(meshes['body_1x1'],'#98743f'),(assemblies['1x1'][1],'#28708f')]:
    section=trimesh.intersections.mesh_plane(mesh,[0,1,0],[0,50,0])
    for segment in section:
        ax.plot(segment[:,0],segment[:,2],color=col,lw=2)
ax.set_xlim(0,6);ax.set_ylim(14,21);ax.set_aspect('equal');ax.grid(alpha=.2)
ax.set_xlabel('X / mm');ax.set_ylabel('Z / mm')
ax.set_title('Actual STL rail section at Y=50 mm\n0.30 mm normal gap per face; 45 degree faces')
ax.annotate('Body retaining lip',xy=(2.5,18.9),xytext=(.4,20.1),arrowprops=dict(arrowstyle='->'))
ax.annotate('Lid',xy=(4.8,17.5),xytext=(4.2,15),arrowprops=dict(arrowstyle='->'))
table=[['1x1','24 x 100 x 20','20 x 93.2 x 14.8'],
       ['2x1','50 x 100 x 20','46 x 93.2 x 14.8'],
       ['2x2','50 x 100 x 42','46 x 93.2 x 36.8'],
       ['3x3','76 x 100 x 64','72 x 93.2 x 58.8']]
bx.axis('off'); bx.table(cellText=table,colLabels=['Case','Outer W x L x H','Clear rectangular cavity'],
                       loc='center',cellLoc='center',colWidths=[.14,.4,.46]).scale(1,2)
bx.set_title('Mesh-verified default dimensions / mm\nAllow 0.5 mm per face; also check narrower top opening')
fig.tight_layout();fig.savefig(ROOT/'previews/rail-section-and-dimensions.png',dpi=170);plt.close(fig)
