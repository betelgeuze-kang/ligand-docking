# CASP17 QC overlay: soft close-contact and low-confidence residue markers.
# Visualization of internal predicted coordinates only; not official CASP accuracy evidence.
reinitialize
set quiet, 1
set internal_gui, 0
viewport 1800, 1200
load "runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current/H1335TS.pdb", casp17_H1335_qc
hide everything, casp17_H1335_qc
remove casp17_H1335_qc and elem H
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
show cartoon, casp17_H1335_qc
show sticks, casp17_H1335_qc and not name N+C+O+CA
show spheres, casp17_H1335_qc and name CA
set cartoon_transparency, 0.22, casp17_H1335_qc
set stick_transparency, 0.18, casp17_H1335_qc and not name N+C+O+CA
set_color casp17_qc_soft, [1.0, 0.20, 0.12]
set_color casp17_qc_low, [1.0, 0.70, 0.12]
set_color casp17_qc_dual, [0.82, 0.22, 1.0]
set_color casp17_qc_base, [0.55, 0.65, 0.78]
color casp17_qc_base, casp17_H1335_qc
set_color casp17_qc_chain_0, [0.3294, 0.4941, 0.8392]
color casp17_qc_chain_0, casp17_H1335_qc and chain A
set_color casp17_qc_chain_1, [0.7451, 0.3529, 0.3882]
color casp17_qc_chain_1, casp17_H1335_qc and chain B
set_color casp17_qc_chain_2, [0.2549, 0.6078, 0.5412]
color casp17_qc_chain_2, casp17_H1335_qc and chain C
set_color casp17_qc_chain_3, [0.7373, 0.5373, 0.3176]
color casp17_qc_chain_3, casp17_H1335_qc and chain D
set_color casp17_qc_chain_4, [0.5255, 0.4, 0.8431]
color casp17_qc_chain_4, casp17_H1335_qc and chain E
select qc_hotspot_1, (casp17_H1335_qc and chain A and resi 10)
color casp17_qc_soft, qc_hotspot_1
show sticks, qc_hotspot_1
show spheres, qc_hotspot_1 and name CA
set sphere_scale, 0.48, qc_hotspot_1 and name CA
label qc_hotspot_1 and name CA, "A:10"
select qc_hotspot_2, (casp17_H1335_qc and chain A and resi 220)
color casp17_qc_soft, qc_hotspot_2
show sticks, qc_hotspot_2
show spheres, qc_hotspot_2 and name CA
set sphere_scale, 0.48, qc_hotspot_2 and name CA
label qc_hotspot_2 and name CA, "A:220"
select qc_hotspot_3, (casp17_H1335_qc and chain A and resi 228)
color casp17_qc_soft, qc_hotspot_3
show sticks, qc_hotspot_3
show spheres, qc_hotspot_3 and name CA
set sphere_scale, 0.48, qc_hotspot_3 and name CA
label qc_hotspot_3 and name CA, "A:228"
select qc_hotspot_4, (casp17_H1335_qc and chain A and resi 181)
color casp17_qc_soft, qc_hotspot_4
show sticks, qc_hotspot_4
show spheres, qc_hotspot_4 and name CA
set sphere_scale, 0.48, qc_hotspot_4 and name CA
label qc_hotspot_4 and name CA, "A:181"
select qc_hotspot_5, (casp17_H1335_qc and chain A and resi 231)
color casp17_qc_soft, qc_hotspot_5
show sticks, qc_hotspot_5
show spheres, qc_hotspot_5 and name CA
set sphere_scale, 0.48, qc_hotspot_5 and name CA
label qc_hotspot_5 and name CA, "A:231"
select qc_hotspot_6, (casp17_H1335_qc and chain A and resi 256)
color casp17_qc_soft, qc_hotspot_6
show sticks, qc_hotspot_6
show spheres, qc_hotspot_6 and name CA
set sphere_scale, 0.48, qc_hotspot_6 and name CA
label qc_hotspot_6 and name CA, "A:256"
select qc_hotspot_7, (casp17_H1335_qc and chain A and resi 324)
color casp17_qc_soft, qc_hotspot_7
show sticks, qc_hotspot_7
show spheres, qc_hotspot_7 and name CA
set sphere_scale, 0.48, qc_hotspot_7 and name CA
label qc_hotspot_7 and name CA, "A:324"
select qc_hotspot_8, (casp17_H1335_qc and chain A and resi 36)
color casp17_qc_soft, qc_hotspot_8
show sticks, qc_hotspot_8
show spheres, qc_hotspot_8 and name CA
set sphere_scale, 0.48, qc_hotspot_8 and name CA
label qc_hotspot_8 and name CA, "A:36"
select qc_hotspot_9, (casp17_H1335_qc and chain A and resi 56)
color casp17_qc_soft, qc_hotspot_9
show sticks, qc_hotspot_9
show spheres, qc_hotspot_9 and name CA
set sphere_scale, 0.48, qc_hotspot_9 and name CA
label qc_hotspot_9 and name CA, "A:56"
select qc_hotspot_10, (casp17_H1335_qc and chain A and resi 115)
color casp17_qc_soft, qc_hotspot_10
show sticks, qc_hotspot_10
show spheres, qc_hotspot_10 and name CA
set sphere_scale, 0.48, qc_hotspot_10 and name CA
label qc_hotspot_10 and name CA, "A:115"
select qc_hotspot_11, (casp17_H1335_qc and chain A and resi 136)
color casp17_qc_soft, qc_hotspot_11
show sticks, qc_hotspot_11
show spheres, qc_hotspot_11 and name CA
set sphere_scale, 0.48, qc_hotspot_11 and name CA
select qc_hotspot_12, (casp17_H1335_qc and chain A and resi 227)
color casp17_qc_soft, qc_hotspot_12
show sticks, qc_hotspot_12
show spheres, qc_hotspot_12 and name CA
set sphere_scale, 0.48, qc_hotspot_12 and name CA
select qc_hotspot_13, (casp17_H1335_qc and chain A and resi 306)
color casp17_qc_soft, qc_hotspot_13
show sticks, qc_hotspot_13
show spheres, qc_hotspot_13 and name CA
set sphere_scale, 0.48, qc_hotspot_13 and name CA
select qc_hotspot_14, (casp17_H1335_qc and chain A and resi 325)
color casp17_qc_soft, qc_hotspot_14
show sticks, qc_hotspot_14
show spheres, qc_hotspot_14 and name CA
set sphere_scale, 0.48, qc_hotspot_14 and name CA
select qc_hotspot_15, (casp17_H1335_qc and chain A and resi 406)
color casp17_qc_soft, qc_hotspot_15
show sticks, qc_hotspot_15
show spheres, qc_hotspot_15 and name CA
set sphere_scale, 0.48, qc_hotspot_15 and name CA
select qc_hotspot_16, (casp17_H1335_qc and chain A and resi 31)
color casp17_qc_dual, qc_hotspot_16
show sticks, qc_hotspot_16
show spheres, qc_hotspot_16 and name CA
set sphere_scale, 0.48, qc_hotspot_16 and name CA
select qc_hotspot_17, (casp17_H1335_qc and chain A and resi 11)
color casp17_qc_soft, qc_hotspot_17
show sticks, qc_hotspot_17
show spheres, qc_hotspot_17 and name CA
set sphere_scale, 0.48, qc_hotspot_17 and name CA
select qc_hotspot_18, (casp17_H1335_qc and chain A and resi 103)
color casp17_qc_soft, qc_hotspot_18
show sticks, qc_hotspot_18
show spheres, qc_hotspot_18 and name CA
set sphere_scale, 0.48, qc_hotspot_18 and name CA
select qc_hotspot_19, (casp17_H1335_qc and chain A and resi 165)
color casp17_qc_soft, qc_hotspot_19
show sticks, qc_hotspot_19
show spheres, qc_hotspot_19 and name CA
set sphere_scale, 0.48, qc_hotspot_19 and name CA
select qc_hotspot_20, (casp17_H1335_qc and chain A and resi 221)
color casp17_qc_soft, qc_hotspot_20
show sticks, qc_hotspot_20
show spheres, qc_hotspot_20 and name CA
set sphere_scale, 0.48, qc_hotspot_20 and name CA
select qc_hotspot_21, (casp17_H1335_qc and chain A and resi 234)
color casp17_qc_soft, qc_hotspot_21
show sticks, qc_hotspot_21
show spheres, qc_hotspot_21 and name CA
set sphere_scale, 0.48, qc_hotspot_21 and name CA
select qc_hotspot_22, (casp17_H1335_qc and chain A and resi 425)
color casp17_qc_dual, qc_hotspot_22
show sticks, qc_hotspot_22
show spheres, qc_hotspot_22 and name CA
set sphere_scale, 0.48, qc_hotspot_22 and name CA
select qc_hotspot_23, (casp17_H1335_qc and chain A and resi 20)
color casp17_qc_dual, qc_hotspot_23
show sticks, qc_hotspot_23
show spheres, qc_hotspot_23 and name CA
set sphere_scale, 0.48, qc_hotspot_23 and name CA
select qc_hotspot_24, (casp17_H1335_qc and chain A and resi 104)
color casp17_qc_soft, qc_hotspot_24
show sticks, qc_hotspot_24
show spheres, qc_hotspot_24 and name CA
set sphere_scale, 0.48, qc_hotspot_24 and name CA
select qc_hotspot_25, (casp17_H1335_qc and chain A and resi 113)
color casp17_qc_soft, qc_hotspot_25
show sticks, qc_hotspot_25
show spheres, qc_hotspot_25 and name CA
set sphere_scale, 0.48, qc_hotspot_25 and name CA
select qc_hotspot_26, (casp17_H1335_qc and chain A and resi 116)
color casp17_qc_soft, qc_hotspot_26
show sticks, qc_hotspot_26
show spheres, qc_hotspot_26 and name CA
set sphere_scale, 0.48, qc_hotspot_26 and name CA
select qc_hotspot_27, (casp17_H1335_qc and chain A and resi 129)
color casp17_qc_soft, qc_hotspot_27
show sticks, qc_hotspot_27
show spheres, qc_hotspot_27 and name CA
set sphere_scale, 0.48, qc_hotspot_27 and name CA
select qc_hotspot_28, (casp17_H1335_qc and chain A and resi 137)
color casp17_qc_soft, qc_hotspot_28
show sticks, qc_hotspot_28
show spheres, qc_hotspot_28 and name CA
set sphere_scale, 0.48, qc_hotspot_28 and name CA
select qc_hotspot_29, (casp17_H1335_qc and chain A and resi 183)
color casp17_qc_soft, qc_hotspot_29
show sticks, qc_hotspot_29
show spheres, qc_hotspot_29 and name CA
set sphere_scale, 0.48, qc_hotspot_29 and name CA
select qc_hotspot_30, (casp17_H1335_qc and chain A and resi 217)
color casp17_qc_soft, qc_hotspot_30
show sticks, qc_hotspot_30
show spheres, qc_hotspot_30 and name CA
set sphere_scale, 0.48, qc_hotspot_30 and name CA
select qc_hotspot_31, (casp17_H1335_qc and chain A and resi 229)
color casp17_qc_soft, qc_hotspot_31
show sticks, qc_hotspot_31
show spheres, qc_hotspot_31 and name CA
set sphere_scale, 0.48, qc_hotspot_31 and name CA
select qc_hotspot_32, (casp17_H1335_qc and chain A and resi 235)
color casp17_qc_soft, qc_hotspot_32
show sticks, qc_hotspot_32
show spheres, qc_hotspot_32 and name CA
set sphere_scale, 0.48, qc_hotspot_32 and name CA
select qc_hotspot_33, (casp17_H1335_qc and chain A and resi 268)
color casp17_qc_soft, qc_hotspot_33
show sticks, qc_hotspot_33
show spheres, qc_hotspot_33 and name CA
set sphere_scale, 0.48, qc_hotspot_33 and name CA
select qc_hotspot_34, (casp17_H1335_qc and chain A and resi 269)
color casp17_qc_soft, qc_hotspot_34
show sticks, qc_hotspot_34
show spheres, qc_hotspot_34 and name CA
set sphere_scale, 0.48, qc_hotspot_34 and name CA
select qc_hotspot_35, (casp17_H1335_qc and chain A and resi 276)
color casp17_qc_soft, qc_hotspot_35
show sticks, qc_hotspot_35
show spheres, qc_hotspot_35 and name CA
set sphere_scale, 0.48, qc_hotspot_35 and name CA
select qc_hotspot_36, (casp17_H1335_qc and chain A and resi 280)
color casp17_qc_soft, qc_hotspot_36
show sticks, qc_hotspot_36
show spheres, qc_hotspot_36 and name CA
set sphere_scale, 0.48, qc_hotspot_36 and name CA
set label_color, white
set label_size, 14
orient casp17_H1335_qc
zoom casp17_H1335_qc, 1.08
rotate x, 8
rotate y, -10
ray 1800, 1200
png runs/casp17_structure_renders_model_selected_shape_guarded_current/H1335_structure_qc_pymol.png, dpi=240
quit
