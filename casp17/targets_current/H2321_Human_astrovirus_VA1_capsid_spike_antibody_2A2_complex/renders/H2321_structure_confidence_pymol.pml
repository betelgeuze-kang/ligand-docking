# CASP17 confidence render: PDB B-factor/pLDDT-style confidence coloring.
# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.
reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_statistical_rotamer_current/H2321TS.pdb", casp17_H2321_confidence
hide everything, casp17_H2321_confidence
remove casp17_H2321_confidence and elem H
bg_color 0x08111f
set ray_opaque_background, on
set antialias, 2
set ambient, 0.36
set direct, 0.70
set spec_reflect, 0.30
set spec_power, 170
set ray_shadow, 1
set depth_cue, 1
set fog_start, 0.36
set fog_end, 1.0
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set cartoon_sampling, 16
set cartoon_quality, 28
set stick_quality, 20
set sphere_quality, 3
set stick_radius, 0.11
set sphere_scale, 0.22
show cartoon, casp17_H2321_confidence
show sticks, casp17_H2321_confidence and not name N+C+O+CA
show spheres, casp17_H2321_confidence and name CA
set_color casp17_conf_very_low, [0.8627, 0.149, 0.149]
color casp17_conf_very_low, casp17_H2321_confidence and b >= 38.889 and b < 56.569
set_color casp17_conf_low, [0.851, 0.4667, 0.0235]
color casp17_conf_low, casp17_H2321_confidence and b >= 56.569 and b < 66.671
set_color casp17_conf_medium, [0.0196, 0.5882, 0.4118]
color casp17_conf_medium, casp17_H2321_confidence and b >= 66.671 and b < 78.288
set_color casp17_conf_high, [0.1451, 0.3882, 0.9216]
color casp17_conf_high, casp17_H2321_confidence and b >= 78.288 and b < 89.401
show cartoon, casp17_H2321_confidence and chain A
show cartoon, casp17_H2321_confidence and chain B
show cartoon, casp17_H2321_confidence and chain C
orient casp17_H2321_confidence
zoom casp17_H2321_confidence, 1.08
rotate x, 8
rotate y, -12
ray 1800, 1200
png runs/casp17_structure_renders_current/H2321_structure_confidence_pymol.png, dpi=240
quit
