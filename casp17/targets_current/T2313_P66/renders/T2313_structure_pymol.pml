reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_statistical_rotamer_current/T2313TS.pdb", casp17_T2313
hide everything, casp17_T2313
remove casp17_T2313 and elem H
bg_color 0x08111f
set ray_opaque_background, on
set antialias, 2
set ambient, 0.34
set direct, 0.72
set spec_reflect, 0.32
set spec_power, 180
set ray_shadow, 1
set depth_cue, 1
set fog_start, 0.38
set fog_end, 1.0
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set cartoon_sampling, 14
set cartoon_quality, 24
set stick_quality, 18
set sphere_quality, 2
set stick_radius, 0.115
set stick_ball, on
set stick_ball_ratio, 1.25
set sphere_scale, 0.22
show cartoon, casp17_T2313
show sticks, casp17_T2313 and not name N+C+O+CA
show spheres, casp17_T2313 and name CA
set_color casp17_chain_0, [0.1451, 0.3882, 0.9216]
color casp17_chain_0, casp17_T2313 and chain A
orient casp17_T2313
zoom casp17_T2313, 1.10
rotate x, 8
rotate y, -10
ray 1800, 1200
png runs/casp17_structure_renders_current/T2313_structure_pymol.png, dpi=240
quit
