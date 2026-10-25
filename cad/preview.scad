// Actual exported STL scene; build meshes before rendering this file.
view = "cases";
module body_mesh(name) { color("#d2b56d") import(str("../stl/body_",name,".stl")); }
module lid_mesh(nx,h) { color("#447e99") translate([0,0,h-3.2]) import(str("../stl/lid_",nx,".stl")); }
module unit(name,nx,h) { body_mesh(name); lid_mesh(nx,h); }
module rack(name) {
    color("#9aa9b7") rotate([90,0,0]) translate([0,0,-102.4])
        import(str("../stl/rack_",name,".stl"));
}
if(view=="cases") {
    unit("1x1",1,20);
    translate([40,0,0]) unit("2x1",2,20);
    translate([108,0,0]) unit("2x2",2,42);
    translate([178,0,0]) unit("3x3",3,64);
    translate([278,0,0]) {
        body_mesh("1x1");
        translate([0,-45,35]) lid_mesh(1,20);
    }
} else if(view=="racks") {
    rack("narrow_36");
    translate([2.4,-16,2.4]) unit("1x1",1,20);
    translate([180,0,0]) {
        rack("medium_9");
        translate([2.4,-16,2.4]) unit("2x2",2,42);
    }
    translate([360,0,0]) {
        rack("large_4");
        translate([2.4,-16,2.4]) unit("3x3",3,64);
    }
} else if(view=="print") {
    // Visual bed reference only; not part of any printable STL.
    color("#d8d8d8") translate([-5,-5,-0.4]) cube([168.8,144.8,0.4]);
    color("#9aa9b7") import("../stl/rack_narrow_36.stl");
}
