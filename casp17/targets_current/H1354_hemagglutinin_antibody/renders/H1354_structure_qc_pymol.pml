# CASP17 QC overlay: soft close-contact and low-confidence residue markers.
# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.
reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_statistical_rotamer_current/H1354TS.pdb", casp17_H1354_qc
hide everything, casp17_H1354_qc
remove casp17_H1354_qc and elem H
bg_color 0x08111f
set ray_opaque_background, on
set antialias, 2
set ambient, 0.38
set direct, 0.68
set spec_reflect, 0.26
set spec_power, 150
set ray_shadow, 1
set depth_cue, 1
set fog_start, 0.34
set fog_end, 1.0
set cartoon_fancy_helices, 1
set cartoon_smooth_loops, 1
set cartoon_sampling, 14
set cartoon_quality, 24
set stick_quality, 20
set sphere_quality, 3
set stick_radius, 0.10
set stick_ball, on
set stick_ball_ratio, 1.22
set sphere_scale, 0.24
show cartoon, casp17_H1354_qc
show sticks, casp17_H1354_qc and not name N+C+O+CA
show spheres, casp17_H1354_qc and name CA
set cartoon_transparency, 0.22, casp17_H1354_qc
set stick_transparency, 0.18, casp17_H1354_qc and not name N+C+O+CA
set_color casp17_qc_soft, [1.0, 0.20, 0.12]
set_color casp17_qc_low, [1.0, 0.70, 0.12]
set_color casp17_qc_dual, [0.82, 0.22, 1.0]
set_color casp17_qc_base, [0.55, 0.65, 0.78]
color casp17_qc_base, casp17_H1354_qc
set_color casp17_qc_chain_0, [0.3294, 0.4941, 0.8392]
color casp17_qc_chain_0, casp17_H1354_qc and chain A
set_color casp17_qc_chain_1, [0.7451, 0.3529, 0.3882]
color casp17_qc_chain_1, casp17_H1354_qc and chain B
set_color casp17_qc_chain_2, [0.2549, 0.6078, 0.5412]
color casp17_qc_chain_2, casp17_H1354_qc and chain C
select qc_hotspot_1, (casp17_H1354_qc and chain B and resi 120)
color casp17_qc_low, qc_hotspot_1
show sticks, qc_hotspot_1
show spheres, qc_hotspot_1 and name CA
set sphere_scale, 0.48, qc_hotspot_1 and name CA
label qc_hotspot_1 and name CA, "B:120"
select qc_hotspot_2, (casp17_H1354_qc and chain B and resi 118)
color casp17_qc_low, qc_hotspot_2
show sticks, qc_hotspot_2
show spheres, qc_hotspot_2 and name CA
set sphere_scale, 0.48, qc_hotspot_2 and name CA
label qc_hotspot_2 and name CA, "B:118"
select qc_hotspot_3, (casp17_H1354_qc and chain C and resi 107)
color casp17_qc_low, qc_hotspot_3
show sticks, qc_hotspot_3
show spheres, qc_hotspot_3 and name CA
set sphere_scale, 0.48, qc_hotspot_3 and name CA
label qc_hotspot_3 and name CA, "C:107"
select qc_hotspot_4, (casp17_H1354_qc and chain C and resi 1)
color casp17_qc_low, qc_hotspot_4
show sticks, qc_hotspot_4
show spheres, qc_hotspot_4 and name CA
set sphere_scale, 0.48, qc_hotspot_4 and name CA
label qc_hotspot_4 and name CA, "C:1"
select qc_hotspot_5, (casp17_H1354_qc and chain A and resi 25)
color casp17_qc_low, qc_hotspot_5
show sticks, qc_hotspot_5
show spheres, qc_hotspot_5 and name CA
set sphere_scale, 0.48, qc_hotspot_5 and name CA
label qc_hotspot_5 and name CA, "A:25"
select qc_hotspot_6, (casp17_H1354_qc and chain C and resi 106)
color casp17_qc_low, qc_hotspot_6
show sticks, qc_hotspot_6
show spheres, qc_hotspot_6 and name CA
set sphere_scale, 0.48, qc_hotspot_6 and name CA
label qc_hotspot_6 and name CA, "C:106"
select qc_hotspot_7, (casp17_H1354_qc and chain A and resi 1)
color casp17_qc_low, qc_hotspot_7
show sticks, qc_hotspot_7
show spheres, qc_hotspot_7 and name CA
set sphere_scale, 0.48, qc_hotspot_7 and name CA
label qc_hotspot_7 and name CA, "A:1"
select qc_hotspot_8, (casp17_H1354_qc and chain C and resi 108)
color casp17_qc_low, qc_hotspot_8
show sticks, qc_hotspot_8
show spheres, qc_hotspot_8 and name CA
set sphere_scale, 0.48, qc_hotspot_8 and name CA
label qc_hotspot_8 and name CA, "C:108"
select qc_hotspot_9, (casp17_H1354_qc and chain B and resi 111)
color casp17_qc_low, qc_hotspot_9
show sticks, qc_hotspot_9
show spheres, qc_hotspot_9 and name CA
set sphere_scale, 0.48, qc_hotspot_9 and name CA
label qc_hotspot_9 and name CA, "B:111"
select qc_hotspot_10, (casp17_H1354_qc and chain B and resi 117)
color casp17_qc_low, qc_hotspot_10
show sticks, qc_hotspot_10
show spheres, qc_hotspot_10 and name CA
set sphere_scale, 0.48, qc_hotspot_10 and name CA
label qc_hotspot_10 and name CA, "B:117"
select qc_hotspot_11, (casp17_H1354_qc and chain A and resi 6)
color casp17_qc_low, qc_hotspot_11
show sticks, qc_hotspot_11
show spheres, qc_hotspot_11 and name CA
set sphere_scale, 0.48, qc_hotspot_11 and name CA
select qc_hotspot_12, (casp17_H1354_qc and chain C and resi 105)
color casp17_qc_low, qc_hotspot_12
show sticks, qc_hotspot_12
show spheres, qc_hotspot_12 and name CA
set sphere_scale, 0.48, qc_hotspot_12 and name CA
select qc_hotspot_13, (casp17_H1354_qc and chain A and resi 27)
color casp17_qc_low, qc_hotspot_13
show sticks, qc_hotspot_13
show spheres, qc_hotspot_13 and name CA
set sphere_scale, 0.48, qc_hotspot_13 and name CA
select qc_hotspot_14, (casp17_H1354_qc and chain A and resi 475)
color casp17_qc_low, qc_hotspot_14
show sticks, qc_hotspot_14
show spheres, qc_hotspot_14 and name CA
set sphere_scale, 0.48, qc_hotspot_14 and name CA
select qc_hotspot_15, (casp17_H1354_qc and chain C and resi 6)
color casp17_qc_low, qc_hotspot_15
show sticks, qc_hotspot_15
show spheres, qc_hotspot_15 and name CA
set sphere_scale, 0.48, qc_hotspot_15 and name CA
select qc_hotspot_16, (casp17_H1354_qc and chain A and resi 466)
color casp17_qc_low, qc_hotspot_16
show sticks, qc_hotspot_16
show spheres, qc_hotspot_16 and name CA
set sphere_scale, 0.48, qc_hotspot_16 and name CA
select qc_hotspot_17, (casp17_H1354_qc and chain A and resi 23)
color casp17_qc_low, qc_hotspot_17
show sticks, qc_hotspot_17
show spheres, qc_hotspot_17 and name CA
set sphere_scale, 0.48, qc_hotspot_17 and name CA
select qc_hotspot_18, (casp17_H1354_qc and chain A and resi 28)
color casp17_qc_low, qc_hotspot_18
show sticks, qc_hotspot_18
show spheres, qc_hotspot_18 and name CA
set sphere_scale, 0.48, qc_hotspot_18 and name CA
select qc_hotspot_19, (casp17_H1354_qc and chain A and resi 465)
color casp17_qc_low, qc_hotspot_19
show sticks, qc_hotspot_19
show spheres, qc_hotspot_19 and name CA
set sphere_scale, 0.48, qc_hotspot_19 and name CA
select qc_hotspot_20, (casp17_H1354_qc and chain A and resi 22)
color casp17_qc_low, qc_hotspot_20
show sticks, qc_hotspot_20
show spheres, qc_hotspot_20 and name CA
set sphere_scale, 0.48, qc_hotspot_20 and name CA
select qc_hotspot_21, (casp17_H1354_qc and chain A and resi 29)
color casp17_qc_low, qc_hotspot_21
show sticks, qc_hotspot_21
show spheres, qc_hotspot_21 and name CA
set sphere_scale, 0.48, qc_hotspot_21 and name CA
select qc_hotspot_22, (casp17_H1354_qc and chain A and resi 456)
color casp17_qc_low, qc_hotspot_22
show sticks, qc_hotspot_22
show spheres, qc_hotspot_22 and name CA
set sphere_scale, 0.48, qc_hotspot_22 and name CA
select qc_hotspot_23, (casp17_H1354_qc and chain B and resi 119)
color casp17_qc_low, qc_hotspot_23
show sticks, qc_hotspot_23
show spheres, qc_hotspot_23 and name CA
set sphere_scale, 0.48, qc_hotspot_23 and name CA
select qc_hotspot_24, (casp17_H1354_qc and chain A and resi 471)
color casp17_qc_low, qc_hotspot_24
show sticks, qc_hotspot_24
show spheres, qc_hotspot_24 and name CA
set sphere_scale, 0.48, qc_hotspot_24 and name CA
select qc_hotspot_25, (casp17_H1354_qc and chain B and resi 109)
color casp17_qc_low, qc_hotspot_25
show sticks, qc_hotspot_25
show spheres, qc_hotspot_25 and name CA
set sphere_scale, 0.48, qc_hotspot_25 and name CA
select qc_hotspot_26, (casp17_H1354_qc and chain C and resi 4)
color casp17_qc_low, qc_hotspot_26
show sticks, qc_hotspot_26
show spheres, qc_hotspot_26 and name CA
set sphere_scale, 0.48, qc_hotspot_26 and name CA
select qc_hotspot_27, (casp17_H1354_qc and chain A and resi 24)
color casp17_qc_low, qc_hotspot_27
show sticks, qc_hotspot_27
show spheres, qc_hotspot_27 and name CA
set sphere_scale, 0.48, qc_hotspot_27 and name CA
select qc_hotspot_28, (casp17_H1354_qc and chain A and resi 26)
color casp17_qc_low, qc_hotspot_28
show sticks, qc_hotspot_28
show spheres, qc_hotspot_28 and name CA
set sphere_scale, 0.48, qc_hotspot_28 and name CA
select qc_hotspot_29, (casp17_H1354_qc and chain A and resi 18)
color casp17_qc_low, qc_hotspot_29
show sticks, qc_hotspot_29
show spheres, qc_hotspot_29 and name CA
set sphere_scale, 0.48, qc_hotspot_29 and name CA
select qc_hotspot_30, (casp17_H1354_qc and chain A and resi 494)
color casp17_qc_low, qc_hotspot_30
show sticks, qc_hotspot_30
show spheres, qc_hotspot_30 and name CA
set sphere_scale, 0.48, qc_hotspot_30 and name CA
select qc_hotspot_31, (casp17_H1354_qc and chain A and resi 63)
color casp17_qc_low, qc_hotspot_31
show sticks, qc_hotspot_31
show spheres, qc_hotspot_31 and name CA
set sphere_scale, 0.48, qc_hotspot_31 and name CA
select qc_hotspot_32, (casp17_H1354_qc and chain B and resi 112)
color casp17_qc_low, qc_hotspot_32
show sticks, qc_hotspot_32
show spheres, qc_hotspot_32 and name CA
set sphere_scale, 0.48, qc_hotspot_32 and name CA
select qc_hotspot_33, (casp17_H1354_qc and chain A and resi 474)
color casp17_qc_low, qc_hotspot_33
show sticks, qc_hotspot_33
show spheres, qc_hotspot_33 and name CA
set sphere_scale, 0.48, qc_hotspot_33 and name CA
select qc_hotspot_34, (casp17_H1354_qc and chain A and resi 468)
color casp17_qc_low, qc_hotspot_34
show sticks, qc_hotspot_34
show spheres, qc_hotspot_34 and name CA
set sphere_scale, 0.48, qc_hotspot_34 and name CA
select qc_hotspot_35, (casp17_H1354_qc and chain B and resi 115)
color casp17_qc_low, qc_hotspot_35
show sticks, qc_hotspot_35
show spheres, qc_hotspot_35 and name CA
set sphere_scale, 0.48, qc_hotspot_35 and name CA
select qc_hotspot_36, (casp17_H1354_qc and chain A and resi 464)
color casp17_qc_low, qc_hotspot_36
show sticks, qc_hotspot_36
show spheres, qc_hotspot_36 and name CA
set sphere_scale, 0.48, qc_hotspot_36 and name CA
set label_color, white
set label_size, 14
orient casp17_H1354_qc
zoom casp17_H1354_qc, 1.08
rotate x, 8
rotate y, -10
ray 1800, 1200
png runs/casp17_structure_renders_current/H1354_structure_qc_pymol.png, dpi=240
quit
