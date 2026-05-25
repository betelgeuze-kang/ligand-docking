# CASP17 molecular inspection render: transparent surface plus cartoon/CA context.
# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.
reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current/T1331TS.pdb", casp17_T1331_surface
hide everything, casp17_T1331_surface
remove casp17_T1331_surface and elem H
bg_color 0x06101f
set ray_opaque_background, on
set antialias, 2
set ambient, 0.30
set direct, 0.76
set reflect, 0.28
set spec_reflect, 0.22
set spec_power, 160
set ray_shadow, 1
set depth_cue, 1
set fog_start, 0.33
set fog_end, 1.0
set two_sided_lighting, on
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set cartoon_sampling, 16
set cartoon_quality, 28
set sphere_quality, 3
set sphere_scale, 0.20
set surface_quality, 0
show surface, casp17_T1331_surface
show cartoon, casp17_T1331_surface
show spheres, casp17_T1331_surface and name CA
set transparency, 0.46, casp17_T1331_surface
set cartoon_transparency, 0.08, casp17_T1331_surface
set_color casp17_surface_base, [0.60, 0.68, 0.80]
color casp17_surface_base, casp17_T1331_surface
set_color casp17_surface_chain_0, [0.3686, 0.5451, 0.9255]
color casp17_surface_chain_0, casp17_T1331_surface and chain A
orient casp17_T1331_surface
zoom casp17_T1331_surface, 1.06
rotate x, 12
rotate y, -18
ray 1800, 1200
png runs/casp17_structure_renders_model_selected_shape_guarded_current/T1331_structure_surface_pymol.png, dpi=240
quit
