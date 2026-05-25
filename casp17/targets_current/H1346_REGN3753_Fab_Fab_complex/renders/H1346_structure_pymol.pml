reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current/H1346TS.pdb", casp17_H1346
hide everything, casp17_H1346
remove casp17_H1346 and elem H
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
show cartoon, casp17_H1346
show sticks, casp17_H1346 and not name N+C+O+CA
show spheres, casp17_H1346 and name CA
set_color casp17_chain_0, [0.1451, 0.3882, 0.9216]
color casp17_chain_0, casp17_H1346 and chain A
set_color casp17_chain_1, [0.8627, 0.149, 0.149]
color casp17_chain_1, casp17_H1346 and chain B
set_color casp17_chain_2, [0.0196, 0.5882, 0.4118]
color casp17_chain_2, casp17_H1346 and chain C
set_color casp17_chain_3, [0.851, 0.4667, 0.0235]
color casp17_chain_3, casp17_H1346 and chain D
orient casp17_H1346
zoom casp17_H1346, 1.10
rotate x, 8
rotate y, -10
ray 1800, 1200
png runs/casp17_structure_renders_model_selected_shape_guarded_current/H1346_structure_pymol.png, dpi=240
quit
