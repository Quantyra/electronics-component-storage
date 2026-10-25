// Quantyra electronics component storage. Original geometry, millimetres.
// Copyright Daniel Eric Fredriksen / Quantyra. CERN-OHL-S-2.0.
// Source Location: https://github.com/Quantyra/electronics-component-storage
part = "body"; // body, lid, rack, assembly, exploded, rack_use, keeper
span_x = 1;
span_z = 1;
clearance = 0.30; // NORMAL offset of each mating rail face, not diametral
cols = 6;
rows = 6;
bay_x = 1;
bay_z = 1;
pitch_x = 26;
pitch_z = 22;
case_length = 100;
wall = 2;
floor_t = 2;
front_t = 4.8; // room for M2 pilot plus label recess without a thin wall
rail_wall = 1.2;
eps = 0.01;
$fn = 32;
function width(n) = pitch_x*n-2;
function height(n) = pitch_z*n-2;
function rack_w() = 4 + cols*pitch_x-rail_wall;
function rack_h() = 4 + rows*pitch_z-rail_wall;
function rack_depth() = case_length+2.4;
assert(span_x>=1 && span_z>=1 && clearance>=0.15 && clearance<=0.45);
assert(wall==2 && floor_t>=2 && case_length>=30,
       "Rail design requires 2 mm side walls; change profile too when changing wall.");
module prism_y(length) {
    translate([0,length,0]) rotate([90,0,0]) linear_extrude(length) children();
}
module rail_section(w) {
    polygon([[1.4,0],[w-1.4,0],[w-3,1.6],[3,1.6]]);
}
module relieved_block(w,l,h) {
    // 0.3 x 0.3 first-layer relief on every exterior floor edge.
    hull() {
        translate([0.3,0.3,0]) cube([w-0.6,l-0.6,0.01]);
        translate([0,0,0.3]) cube([w,l,h-0.3]);
    }
}
module body(nx=span_x,nz=span_z,c=clearance,l=case_length,details=true) {
    w=width(nx); h=height(nz);
    difference() {
        relieved_block(w,l,h);
        // Smooth cavity: no internal dividers, slots or keeper protrusions.
        translate([wall,front_t,floor_t]) cube([w-2*wall,l-front_t-wall,h-5.2]);
        translate([0,-eps,h-3.2]) prism_y(l-2.2+eps)
            offset(delta=c, chamfer=true) rail_section(w);
        translate([3,-eps,h-1.6]) cube([w-6,l-2.2+eps,3]);
        if(details) {
            // Replaceable label pocket; grip below it, independent of lid.
            translate([3,-eps,6]) cube([w-6,0.41,7]);
            translate([w/2-4,-eps,2.6]) cube([8,0.81,2.6]);
            // M2 removable keeper pilot, only in the front wall.
            translate([w/2,front_t/2,h-9]) cylinder(h=10,d=1.6);
        }
    }
}
module lid(nx=span_x,l=case_length,details=true) {
    w=width(nx);
    difference() {
        prism_y(l-2.6) rail_section(w);
        if(details) {
            translate([w/2,front_t/2,-eps]) cylinder(h=2,d=2.4);
            // Recessed fingertip drag pocket: no handle above or outside case.
            translate([w/2-5,7,1.1]) cube([10,8,1]);
        }
    }
}
module keeper(nx=span_x,nz=span_z) {
    // Reference envelope only: externally sourced M2x6, head <=4 x 1.4.
    translate([width(nx)/2,front_t/2,height(nz)-1.6]) {
        cylinder(h=1.4,d=4);
        translate([0,0,-6]) cylinder(h=6,d=2);
    }
}
module closed_case(nx=span_x,nz=span_z,explode=0) {
    color("#d2b56d") body(nx,nz);
    color("#447e99") translate([0,-explode,height(nz)-3.2+explode]) lid(nx);
    color("#60666a") translate([0,0,explode*2]) keeper(nx,nz);
}
module rack_use() {
    assert(cols%bay_x==0 && rows%bay_z==0);
    difference() {
        cube([rack_w(),rack_depth(),rack_h()]);
        for(i=[0:cols/bay_x-1], j=[0:rows/bay_z-1])
            translate([2+i*bay_x*pitch_x,-eps,2+j*bay_z*pitch_z])
                cube([bay_x*pitch_x-rail_wall,case_length+0.4+eps,
                      bay_z*pitch_z-rail_wall]);
    }
}
module rack_print() {
    // Back on bed, openings up. Use axes X / depth Y / height Z.
    // (X,Y,Z) use -> (X,Z,depth-Y) print: back is Z=0..2, bays above.
    translate([0,0,rack_depth()]) rotate([-90,0,0]) rack_use();
}
if(part=="body") body();
else if(part=="lid") lid();
else if(part=="rack") rack_print();
else if(part=="assembly") closed_case();
else if(part=="exploded") closed_case(explode=18);
else if(part=="rack_use") rack_use(); // validation export
else if(part=="keeper") keeper(); // validation envelope, do not print
else assert(false,"Unknown part");
