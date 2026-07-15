# Independent Engine v2 독립 상용화 장기 로드맵

기준일: 2026-07-15

문서 상태: 장기 개발 참고 기준선·비실행 문서·비주장 문서

현재 구현 단계: V2-0 독립 CPU 스캐폴드 완료, V2-1 strict canonical-ingest와
정확히 표현 가능한 parser-owned SDF V2000과 별도 opt-in simple named
opaque data-field envelope 1.0 및 bondless·no-altloc·
optional-exact-`CRYST1`·single-model-ID1 source-reported `REMARK 465/470`
semantic-profile PDB와 별도 opt-in ordered `CONECT` source-declaration
envelope 1.0, single-model-ID1·exact-core11·
independently-appended formal-charge/insertion-code/uncertainty-free occupancy
core12·formal-charge-then-insertion-code 또는 uncertainty-free
occupancy-then-B-factor core13 `_atom_site`-only 여섯 profile과 exact
`_entity`·`_struct_asym`·official-order common-core21 label/auth/entity identity
profile의 single-model-ID1 mmCIF 1.5와 base 버전을 바꾸지 않는 별도
opt-in exact common-core21 explicit-altloc-selection envelope 1.0, 그리고 별도
opt-in `_pdbx_entity_nonpoly`·`_pdbx_nonpoly_scheme` source identity envelope
1.0과, 그 변경 없는 carrier에 exact 3-field `_chem_comp`·7-field
`_chem_comp_atom`·7-field `_chem_comp_bond`를 결합해 source-reported organic-subset
비중합체 component template을 instance별 canonical charge·bond state로
물질화하는 별도 opt-in nonpoly component topology envelope 1.0, 그 exact
carrier에 official-order 23-field `_struct_conn`을 추가해 identity-symmetry
`covale` nonpoly inter-residue bond만 물질화하는 별도 opt-in
nonpoly covalent struct-conn topology envelope 1.0, 그리고
exact `_entity_poly_seq(entity_id,num,mon_id,hetero)`를 보존하는 별도
opt-in polymer sequence membership envelope 1.0, 그 변경 없는 child에 exact
`_chem_comp`·`_chem_comp_atom`·`_chem_comp_bond`를 결합해 모든
asym×sequence residue의 coordinate/template atom coverage를 요구하고
H/C/N/O/S·atom N/R/S·bond `SING/DOUB/TRIP/AROM`만 source-reported
intra-residue topology로 물질화하는 별도 exact 7-category fully-observed
polymer component-topology envelope 1.0, 그리고 exact 5-category
`_entity`·`_entity_poly`·`_struct_asym`·`_entity_poly_seq`·`_atom_site`와
`_entity_poly(entity_id,type,nstd_chirality,nstd_linkage,nstd_monomer)`의
`polypeptide(L),no,no,no`만 받아 pinned offline ALA/GLY heavy role·intra-residue
rule·same-asym n-1 C--N path를 sequence-implied reference topology로
물질화하는 archive-standard ALA/GLY envelope 1.0, fully-observed child를
변경하지 않고 exact
11-field `_chem_comp_atom`의 source-reported leaving/backbone/N-terminal/
C-terminal flag와 asym별 sequence-boundary role만 보존하는 별도
polymer terminal/leaving annotation inventory envelope 1.0, 그 두 child를 exact
    8-category raw source에서 독립 재투영한 뒤 source-explicit ALA/GLY
    CCD-neutral role atom 삭제·same-asym C--N bond·prepared heavy crosscheck를
    적용하는 non-writer profile-local preparation transform 1.0, exact 5-category
    archive-heavy source의 binary64 heavy 좌표를 유지하면서 N--CA--C frame과
    pinned CCD ideal parent vector로 role-specific H를 생성하고 fixed-neutral
    microstate를 배정하는 별도 non-writer heavy-completion transform 1.0, 그리고 exact 6-category
polymer-sequence+nonpoly-identity child와 exact 8-category nonpoly
component-topology child를 source split 후 공통 carrier와 canonical loop로
교차 결속하는 별도 strict 9-category polymer-sequence+nonpoly
component-topology composition envelope 1.0, 기존 polymer-sequence carrier에
exact official-order
`_pdbx_unobs_or_zero_occ_residues` residue loop를 결합하는 source-reported
unobserved-residue envelope 1.0과, 같은 carrier의 좌표에 부모 residue가
존재하고 선택 atom만 없는 경우를 보존하는 exact official-order
`_pdbx_unobs_or_zero_occ_atoms` source-reported unobserved-atom envelope 1.0, 그리고
같은 exact carrier에 `occupancy_flag=0` declaration과 selected model-1
`_atom_site`의 모든 matching occupancy가 정확한 numeric zero임을 함께 결속하는
별도 additive zero-occupancy-residue·zero-occupancy-atom envelope 1.0, 그리고
1–256개 ordered component·
global cycle rank 0/1·at-most-one simple non-aromatic 3–8-member 또는
fully-aromatic 5/6-member `B C N O P S` ring·selected unit-charge/bracket-H·
bounded-parser-observed-state organic-subset graph SMILES 1.8과 bounded
parser-typed E/Z direction-carrier 및 tetrahedral R/S local-parity projection
writer·source-format round-trip projection 계약, source-observed explicit-H
neutral unsubstituted monocyclic cycloalkane C3–C8 graph-local profile·고정
positive/failure corpus 계약과 source-observed explicit-H neutral unbranched
terminal monoalkene C2–C8 graph-local bond-order/valence-ledger profile·고정
positive/failure corpus 계약과 source-observed explicit-H neutral exact H2O
graph-local bond-order/valence-ledger profile·고정 positive/failure corpus 계약,
V2-2 bounded C1–C4 topology·비물리 full parameter
assignment·direct-uncut method binding·snapshot-bound schema-owned scalar-energy
진단 계약, SPICE 2.0.1 C1–C4 200행 quantum-reference observation evidence와
비승격 source-authentication/license-review 입력 패킷,
source-bound pair-relative-energy·negative-gradient target view, fit-only
bonded-basis conditional-observability 감사 및 exact-methane 수치 진단 비승격
스캐폴드 진행 중

적용 범위: 단백질·리간드 구조분석, 도킹, 분자동역학, AI 보정, ROCm/HIP, 로컬 제품화

이 문서는 현재 구현을 상용 제품으로 선언하는 자료가 아니다. 앞으로 무엇을
어떤 순서로 구현하고, 어떤 증거를 확보해야 독립 기능을 하나씩 출시할 수
있는지를 정하는 참고 로드맵이다. 실제 capability 상태와 출시 가능 여부는
[`../config/independent_engine_v2_capabilities.yaml`](../config/independent_engine_v2_capabilities.yaml)의
fail-closed 정책을 따른다.

이번 문서 변경은 개발 지시 실행이나 capability 승격을 의미하지 않는다.
소스코드, 외부 실행 상태와 과학·제품 claim은 변경하지 않는다. 문서와 실제
상태가 충돌하면 다음 우선순위를 적용한다.

1. 실행 코드와 검증 테스트
2. machine-readable capability blocker
3. non-empty row-level benchmark·release evidence
4. 이 로드맵과 기타 narrative 문서

기존 `product_full_implementation_plan.md`와 `PRODUCT_VISION_CURRENT.md`는
legacy/restricted 제품 운영 lane을 설명한다. 해당 lane의 green 상태를 독립
V2 과학 엔진의 완료로 합산하지 않는다. 이 문서는 V2 장기 전략, 단계 의존성과
capability 승격 기준을 정리하는 canonical reference다.

## 1. 최종 목표

최종 목표는 고객 실행 경로에서 외부 분자 솔버를 호출하지 않는 완전한 로컬·
오프라인 단백질·분자구조 분석 프로그램을 구축하는 것이다.

완성 제품이 독립적으로 제공해야 할 기능은 다음과 같다.

- 단백질·리간드 all-atom 입력, 정규화, 전처리 및 화학 적용범위 판정
- 구조 품질, 결합 포켓, 인터페이스, 상호작용, 변이 영향 분석
- 독립 힘장, 에너지·힘 계산, 구조 최소화 및 국소 refinement
- torsion-aware ligand docking, 다양한 top-k pose와 재점수화
- PBC, 명시적 용매·이온, 장거리 정전기와 NVE/NVT/NPT 분자동역학
- 물리 기반 에너지에 결합되는 독자 residual-energy AI
- 불확실성 보정, 적용범위 판정과 OOD 입력 거부
- capability별 재현 가능한 benchmark와 signed evidence
- AMD ROCm/HIP 가속과 CPU 기준 구현의 수치적 동등성
- 설치, 업데이트, 작업 재개, 3D 시각화, 보고서와 데이터 격리를 포함한 제품 기능

Vina, GNINA, Smina, OpenMM, AMBER, GROMACS 또는 다른 분자 솔버는 개발 중
offline reference oracle과 비교 실험에만 사용할 수 있다. 이 도구의 계산을
v2 결과로 표시하거나 고객 실행의 숨은 의존성으로 사용할 수 없다. PyTorch,
Rust, ROCm과 일반 파일·UI·보안 라이브러리는 구현 인프라로 사용할 수 있지만,
과학적 에너지·힘·도킹·MD 판단은 v2가 소유하고 검증해야 한다.

RDKit과 같은 cheminformatics 라이브러리는 파일 ingest·개발 비교용 adapter로
사용할 수 있지만, canonical molecular state와 지원 chemistry 판정은 v2
contract가 다시 검증해야 한다. 독립 엔진 코드, 독립 parameter, 학습 dataset,
model IP와 각 artifact의 license는 서로 별개의 증거 트랙으로 관리한다.

## 2. 현재 기준점과 완료되지 않은 영역

V2-0은 완성된 분자구조 해석 제품이 아니라 독립 엔진을 만들기 위한 실행
가능한 CPU 기준선이다. 그 위에 V2-1과 V2-2의 좁은 계약·검증 조각이 추가됐지만
어느 단계도 종료 기준을 충족하거나 제품 실행 권한을 얻지는 않았다.

| 구분 | 현재 확보한 기반 | 현재 차단된 주장 또는 기능 |
| --- | --- | --- |
| 계약 | 버전형 all-atom 상태, 결합, isotope, R/S·E/Z, provenance, legacy adapter, strict PDB/mmCIF/SDF/SMILES canonical projection과 고정 ingest/failure corpus, 정확히 표현 가능한 parser-owned 단일-record SDF V2000과 별도 opt-in simple named opaque data-field envelope 1.0, bondless·no-altloc·optional-exact-`CRYST1` PDB와 single-model-ID1 source-reported `REMARK 465/470` semantic round-trip profile 및 별도 opt-in ordered `CONECT` source-declaration envelope 1.0, single-model-ID1 여섯 `_atom_site`-only profile과 exact `_entity`·`_struct_asym`·official-order common-core21 label/auth/entity identity mmCIF 및 별도 opt-in explicit biological assembly envelope 1.0.0, source-reported nonpoly identity envelope 1.0, exact 8-category nonpoly component topology envelope 1.0, exact 9-category identity-symmetry `covale` nonpoly struct-conn topology envelope 1.0, polymer sequence membership envelope 1.0, exact 7-category fully-observed polymer component topology envelope 1.0, exact 5-category archive-standard ALA/GLY sequence-implied heavy reference-topology envelope 1.0, exact 11-field polymer terminal/leaving annotation inventory envelope 1.0, exact 8-category ALA/GLY source-explicit CCD-neutral profile-local preparation transform 1.0, exact 9-category polymer-sequence+nonpoly component-topology composition envelope 1.0, source-reported unobserved-residue envelope 1.0, source-reported unobserved-atom envelope 1.0, 그리고 1–256개 ordered organic-subset component에서 global cycle rank 0/1·at-most-one simple non-aromatic 3–8-member ring 또는 fully-aromatic 5/6-member `B C N O P S` ring·선택 unit-charge/bracket-H token·bounded parser-typed E/Z·tetrahedral R/S를 직렬화하는 SMILES writer 1.8 및 각 선언 projection round-trip evidence | 선택 envelope 밖 `CONECT`와 모든 bond-kind/order·covalence·coordination·chemistry 의미론, altloc·general missingness·비표현 `CRYST1`·symmetry/PBC 의미론을 포함한 general PDB, exact common-core21·선택 assembly·nonpoly identity·nonpoly component topology·선택 nonpoly covalent struct-conn topology·polymer sequence membership·선택 fully-observed polymer component topology·선택 archive-standard ALA/GLY heavy reference topology·선택 polymer terminal/leaving annotation inventory·선택 ALA/GLY neutral preparation transform 밖의 general preparation·선택 polymer-sequence+nonpoly component-topology composition·residue/atom-level source-reported unobserved envelope 밖 categories·auth/entity·optional fields·altloc·assembly declaration/operator form·선택 atom envelope 밖 atom-level missingness·zero-occupancy semantics·cell·multimodel을 포함한 general mmCIF, general `_struct_conn`의 disulf/hydrog/metalc/salt·quad/default order·nonidentity symmetry·coordination·polymer endpoint, fragment role·salt·mixture chemistry·선택 ring 밖의 general rings·fused/polycyclic aromaticity·두 번째 ring double·ring triple·multiple-bond closure를 포함한 일반 multiple-bond chemistry·일반 charge/charge assignment·isotope·nonpositive/duplicate map·bounded tetrahedral R/S 밖 atom stereo·unknown bond stereo·bounded profile 밖 E/Z·source H·선택 aromatic/tetrahedral 상태 밖 bracket H를 포함한 general SMILES, simple named envelope 밖의 arbitrary `M` property record·rich data header·multi-record·V3000·stereo를 포함한 general SDF와 완전한 parser·preparation·지원 chemistry coverage |
| V2-1 PDB ordered `CONECT` source-declaration envelope | single-model-ID1의 trailing contiguous fixed-column `CONECT` row와 directed source serial·ordered target slot·duplicate slot·directional asymmetry projection, canonical 80-column re-emission 및 고정 positive/failure corpus | canonical `Bond`·bond kind/order·covalence·coordination·chemistry 해석, bare `.system` 보존, altloc·multimodel·일반 `CONECT`, preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general PDB round-trip |
| V2-1 mmCIF explicit biological assembly envelope | exact common-core21 ASU와 단일 assembly definition, official-order generator/operator loop, explicit `assembly_id`, right-to-left rigid transform, ASU 재출력과 bitwise expanded coordinate·topology·atom/chain instance order projection, stable re-emission 및 고정 positive/failure corpus | source authentication·biological correctness, 다른 assembly category/header/operator form, numeric uncertainty, altloc·multimodel·cell/symmetry/PBC, bond·chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF nonpoly identity envelope | exact `_entity`·`_struct_asym`·common-core21 `_atom_site`와 선택 `_pdbx_entity_nonpoly`·official-order `_pdbx_nonpoly_scheme`의 source identity·instance nomenclature alias projection 및 canonical five-category re-emission | role·chemistry·topology·bond/order·coordination·charge·protonation·preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF nonpoly component topology envelope | unchanged five-category nonpoly carrier에 exact `_chem_comp(id,type,pdbx_formal_charge)`·official-order 7-field `_chem_comp_atom`·7-field `_chem_comp_bond`를 결합한 8-category profile, instance별 complete template atom-set join, source charge fill/crosscheck, `SING/DOUB/TRIP/AROM`의 canonical `Bond` 물질화, exact reparse·stable emission·bounded artifact evidence, exact envelope parser pedigree·최종 augmented observation/topology digest refresh, 기존 acyclic saturated hydrocarbon canonical-ingest/profile-local gate의 single-methane positive evidence | source authentication·independent/general chemistry/valence/aromaticity/stereo, 이 8-category envelope 내 `_struct_conn`·inter-residue/cross-component link·coordination·metal, stereo `N` 이외·기타 bond order, altloc·assembly·missingness·cell·multimodel 조합, generic/global preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF nonpoly covalent struct-conn topology envelope | unchanged exact 8-category component carrier와 official-order 23-field `_struct_conn`의 9-category profile, `covale`·explicit lowercase `sing/doub/trip`·양쪽 `1_555`, exact label+auth atom identity join, 서로 다른 non-polymer/water residue endpoint, canonical inter-residue `Bond` 물질화, 최종 topology/observation digest refresh·factory artifact chain·exact reparse·stable emission, 기존 hydrocarbon canonical-ingest/profile-local gate의 exact `split_ethane_sing` positive evidence, 3개 round-trip·15개 typed-failure 고정 corpus와 payload SHA-256 `2a8a2428ff39646f964af01773bc69b3f71cb03cfaba78b7ebb30ef2ba2d2704` | general `_struct_conn`, disulf/hydrog/metalc/salt·quad/default order·nonidentity symmetry·coordination·polymer endpoint, altloc·assembly·missingness·cell·multimodel 조합, source authentication·independent chemistry/valence/bond-order, generic/global preparation·parameterability·physics·runtime·simulation·execution·claim 권한, general mmCIF과 V2-1 완료 |
| V2-1 mmCIF polymer sequence membership envelope | exact common-core21 또는 기존 nonpoly identity carrier와 official-order `_entity_poly_seq`의 source-reported polymer entity·sequence number·opaque monomer-code membership, atom-site label tuple presence join 및 canonical four/six-category re-emission | reference sequence 동일성·완전성, coordinate observation completeness, missing-residue fact, auth alignment, modified-residue identity, general microheterogeneity·chemistry, preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF fully-observed polymer component-topology envelope | unchanged exact 4-category polymer-sequence child에 exact 3/7/7-field `_chem_comp`·`_chem_comp_atom`·`_chem_comp_bond`를 결합한 exact 7-category profile, 모든 entity의 every-asym×sequence residue 인스턴스와 component template atom-set의 exact 전체 coverage, quoted `L-peptide linking`, H/C/N/O/S, atom N/R/S·bond N, source charge fill/crosscheck, `SING/DOUB/TRIP/AROM`의 canonical 1.0/2.0/3.0/1.5 intra-residue `Bond`, 신규 parser pedigree·최종 topology/observation digest refresh·exact reparse·stable second emission·bounded factory artifact evidence | CCD/reference authentication·general completeness, 독립 CIP/chemistry/valence/aromaticity/stereo 판정, peptide·inter-residue·cross-component bond, modified/terminal residue 밖 general template·D-peptide·nucleic acid·saccharide, completion·preparation·parameterability·physics·runtime·simulation·execution·claim 권한, general mmCIF과 V2-1 완료 |
| V2-1 mmCIF archive-standard ALA/GLY heavy reference-topology envelope | exact 5-category `_entity`, `_entity_poly`, `_struct_asym`, `_entity_poly_seq`, `_atom_site`와 exact `_entity_poly(entity_id,type,nstd_chirality,nstd_linkage,nstd_monomer)=polypeptide(L),no,no,no`, unchanged polymer-sequence carrier, pinned offline engine-owned manifest SHA-256 `4d941815d26431a5de9bd74b4860f84ce39232e7123ee87b3b61a104457eb244`, GLY N/CA/C/O 및 ALA N/CA/C/O/CB, C-boundary·singleton OXT와 outgoing-linked OXT 금지, pinned intra-residue bond 및 same-asym exact n-1 C--N path, no cross-asym·no coordinate-distance/auth-alias selection, parser pedigree·최종 topology/observation digest refresh·factory artifact cross-binding·stable round-trip, semantic preparation commitment 재계산, 5-positive/24-failure corpus payload SHA-256 `58377d1b60a493e62a53af8250c912b49b7475e76d41316ee8d2380ffaf967de`; 고정 5 positives 모두 recognized/self-consistent지만 canonical ingest `unsupported`, preparation `incomplete` | CCD file hash를 source authentication으로 보는 것, source-observed covalence·coordinate peptide geometry·chain-break 탐지/배제, formal charge·H·protonation·stereo 할당, modified/nonstandard monomer, generic chemistry·preparation·parameterability, physics·runtime·simulation·execution·claim 권한, general mmCIF/all-format readiness와 V2-1 완료 |
| V2-1 mmCIF polymer terminal/leaving annotation inventory envelope | exact 11-field `_chem_comp_atom`에서 선택 column 순서와 token 값을 보존해 unchanged exact 7-category polymer component-topology child를 투영하고, source Y/N leaving/backbone/N-terminal/C-terminal flag와 asym별 `singleton`/`n_sequence_boundary`/`internal`/`c_sequence_boundary` 위치 role을 factory-only evidence로 보존한다. 각 stage에서 child `AllAtomSystem`, parser pedigree, topology/observation digest, preparation-inventory commitment와 canonical 7-field child emission은 같은 stage의 독립 projected child와 일치하며, exact reparse·stable second emission과 고정 corpus를 갖는다. | chemical terminal state·terminal chemistry, leaving-atom policy 적용·원자 삭제, atom-name/geometry 기반 C–N 추론, peptide·inter-residue bond 물질화, source/CCD authentication, generic chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한, general mmCIF과 V2-1 완료 |
| V2-1 exact ALA/GLY source-explicit neutral-linkage preparation transform | exact 8-category source를 terminal/leaving 7-category child와 archive-heavy 5-category child로 독립 투영한 뒤, pinned manifest SHA-256 `daa2beb6648d2749204093bfd0db5dd316cb38557b29890054ddc54c73193d7f`의 ALA 13-atom/12-bond·GLY 10-atom/9-bond known-zero-charge source-explicit microstate만 적용한다. role별 H2/OXT/HXT만 삭제하고 same-asym consecutive C--N bond만 추가하며 `L` links에 대해 `3L` atom·`3L` source-bond 삭제, `L` bond 추가, final source-bond-minus-`2L`을 강제한다. source coordinate를 유지하고 H를 생성하지 않으며 prepared heavy graph를 archive child와 교차 검증한다. 4-positive/16-failure corpus payload SHA-256 `c5c0ab935305c8d15fb2868c8327d38622de85fe84b8426e32d14be88ff3c20d`를 결속하고 profile-local preparation readiness만 true이다. | outer writer·canonical source round-trip, environmental pH/protonation correctness, generic H completion·generic/global preparation, production parameter set·parameterability, physics·runtime·energy·force·minimization·simulation·execution·claim 권한, general mmCIF/all-format readiness와 V2-1 완료 |
| V2-1 exact ALA/GLY heavy-to-fixed-neutral all-atom completion transform | exact 5-category archive-heavy child를 독립 수용하고 manifest SHA-256 `eed2b432c6a4b916370e14d922830a5eeb9f531acc579c94b7e823b8949810c6`의 CCD ideal coordinate·H parent·role inventory를 적용한다. source heavy coordinate는 binary64 bit-exact로 유지한다. heavy bond ideal ±0.20 Å, same-asym C--N 1.15–1.55 Å, N--CA--C frame sine ≥0.05, ALA positive N/C/CB orientation을 profile admission으로 검사한 뒤 parent-relative ideal vector를 source frame으로 회전해 role-specific H를 생성하고 known-zero formal charge를 배정한다. source-retained/profile-generated mapping, deterministic atom/bond order, raw-source replay, exact-instance parameter inventory와 4-positive/13-failure corpus payload SHA-256 `7fed000628174709fb5cd30955239f65e9395e981d3a34422fdcdb3a932bfb1f`를 결속한다. | outer writer·serialization round-trip, scientific geometry·angle·omega·clash 검증, environmental pH/protonation correctness, generic H completion·generic/global preparation, improper/CMAP·production parameter set·parameterability, physics·runtime·energy·force·minimization·simulation·execution·claim 권한, general mmCIF/all-format readiness와 V2-1 완료 |
| V2-1 mmCIF polymer-sequence+nonpoly component-topology composition envelope | exact 9-category `_entity`, `_struct_asym`, `_entity_poly_seq`, `_chem_comp`, `_chem_comp_atom`, `_chem_comp_bond`, `_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site`를 exact 8-category component child와 exact 6-category polymer child로 split해 각각 독립 수용시키고, shared nonpoly identity projection/record state·base topology/representable state·source ID·data block·공통 5개 canonical loop와 nonpoly writer payload를 교차 결속한다. component child만 detached component-carrier system pedigree를 소유하고 polymer sequence는 source evidence로만 남으며, exact reparse·stable second emission과 고정 2-positive/6-failure corpus를 갖는다. | polymer template·modified-residue chemistry, reference-sequence/coordinate completeness·missingness, `_struct_conn`, altloc·assembly·cell·multimodel 조합, generic/global preparation·parameterability·physics·runtime·simulation·execution·claim 권한, general mmCIF과 V2-1 완료 |
| V2-1 mmCIF source-reported unobserved-residue envelope | polymer sequence carrier 또는 기존 nonpoly identity와 조합된 carrier에 exact official-order residue missingness loop를 추가하고, label sequence join·selected coordinate absence·ordered source claim projection 및 canonical five/seven-category re-emission을 검증 | 실제 missing-residue fact, reference/sequence/coordinate completeness, auth-label equivalence, modeled/modified residue identity, atom-level missingness, zero-occupancy 의미론, chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF source-reported unobserved-atom envelope | 같은 carrier에 exact official-order 14-field atom missingness loop를 추가하고, label sequence join·selected coordinate parent-residue presence·exact atom absence·raw insertion/altloc marker·ordered source claim projection 및 canonical five/seven-category re-emission을 검증 | 실제 missing-atom fact, residue-template 또는 atom-name dictionary 검증, completion, reference/sequence/coordinate completeness, auth-label equivalence, zero-occupancy 의미론, chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한과 general mmCIF round-trip |
| V2-1 mmCIF source-reported zero-occupancy-residue envelope | unchanged polymer sequence carrier 또는 기존 nonpoly identity 조합 carrier에 exact official-order 11-field residue loop의 `occupancy_flag=0` branch를 추가하고, polymer sequence join·selected model-1 residue presence·모든 matching `_atom_site.occupancy`의 exact numeric-zero·base missing-claim 0 및 zero-row metadata·ordered declaration·stable re-emission을 검증 | zero occupancy에서 실제 missing-residue fact·population/weighting·completeness·refinement validity·altloc·chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한을 추론하거나 general mmCIF round-trip을 주장하는 것 |
| V2-1 mmCIF source-reported zero-occupancy-atom envelope | 같은 unchanged carrier에 exact official-order 14-field atom loop의 `occupancy_flag=0` branch를 추가하고, parent residue와 exact blank-altloc atom presence·모든 matching occupancy의 exact numeric-zero·base missing-claim 0 및 zero-row metadata·ordered declaration·stable re-emission을 검증 | zero occupancy에서 실제 missing-atom fact·atom completion·population/weighting·completeness·refinement validity·altloc·chemistry·preparation·parameterability·physics·runtime·simulation·execution·claim 권한을 추론하거나 general mmCIF round-trip을 주장하는 것 |
| V2-1 SMILES bounded parser-typed E/Z projection | writer 1.8이 유지하는 source-tree E/Z, selected simple-ring single-bond carrier, selected 8-member unique nonclosure ring E/Z, lexical orientation·reference parity·shared XOR constraint, exact reparse·stable re-emission 및 별도 고정 corpus | unknown bond stereo, bounded profile 밖 E/Z, 독립 CIP·stereo completeness·geometry·chemistry·preparation·parameterability·runtime·simulation·claim 권한과 general SMILES round-trip |
| V2-1 SMILES bounded parser-typed tetrahedral R/S projection | writer 1.8의 source-order DFS, parser-owned R/S와 exact RDKit CW/CCW, `@` trial→center별 `@@` 보정→final parse local parity, source graph당 최대 256 center·typed center가 있으면 source atom 최대 514개·selected ring·bounded E/Z coexistence·positive unique map·center당 zero/one bracket-H, exact reparse·stable re-emission 및 별도 14-positive corpus | 독립 CIP assignment, global stereo completeness·substituent equivalence·geometry, 256개 초과 center·typed center가 있는 514개 초과 source-atom graph·bounded profile 밖 atom stereo·nonpositive/duplicate map·선택 상태 밖 bracket H, chemistry·preparation·parameterability·runtime·simulation·claim 권한과 general SMILES round-trip |
| V2-1 graph-local profile | parser-owned SDF V2000의 source-observed explicit-H·known-zero-charge·nonaromatic single-bond unsubstituted monocyclic cycloalkane C3–C8에 대한 frozen rule, source-indexed graph projection, snapshot·topology·generic report·parser-observation digest binding, 전 positive 및 고정 failure corpus, audit-consumer allowlist | global molecular preparation, pH·protonation, ring strain·conformation·geometry, parameterability·force-field typing·charge·parameter, physics·runtime·energy·force·minimization·simulation·claim 권한 |
| V2-1 terminal monoalkene graph-local profile | parser-owned SDF V2000 parser 1.5의 source-observed explicit-H·known-zero-charge·C/H-only·unbranched terminal monoalkene C2–C8에 대한 frozen rule, exact source atom/bond metadata, source-indexed graph projection, CnH2n·carbon simple path·terminal C=C·C=4/H=1 integer bond-order ledger, snapshot·topology·generic report·parser-observation digest binding, 전 positive 및 고정 failure corpus, 단일 audit-consumer allowlist | generic chemistry·generic/global molecular preparation, pH·protonation·tautomer, E/Z·CIP, coordinate 직선성·conformation·geometry, 독립 bond-order·valence·unsaturation·electronic-structure 검증, parameterability·force-field typing·charge·parameter, physics·runtime·energy·force·minimization·simulation·claim 권한 |
| V2-1 exact H2O graph-local profile | parser-owned SDF V2000 parser 1.5의 source-observed explicit-H·원자별 atom-block known-zero-charge exact O1/H2 한 component에 대한 frozen rule, exact source atom/bond metadata와 `LIG/non_polymer`·`L/ligand` 합성 context, source-indexed graph projection, exact O–H single bond 2개·O=2/H=1 integer bond-order ledger, snapshot·topology·generic report·parser-observation digest binding, 고정 positive/failure corpus, 단일 audit-consumer allowlist | water entity marker·water/solvent/hydration role, generic chemistry·generic/global preparation, pH·protonation·autoionization·isotope speciation, bond length·angle·conformation·geometry, 독립 bond-order·valence·electronic-structure 검증, parameterability·typing·partial charge·parameter·water model·constraint, box·PBC·periodicity, physics·runtime·energy·force·minimization·simulation·claim 권한 |
| 기하 | bounded cell-list, sparse radius graph, 고정 capacity와 overflow 차단 | release-scale occupancy·memory evidence와 periodic AI gradient |
| AI | non-attention parity-aware local energy, exact force VJP, torsion·temporal GNN, PINN gate | 학습된 production checkpoint, calibration, OOD 및 공개 holdout evidence |
| 수학 | matrix-free 고정 rank 직교사영과 adjoint | 광범위한 constraint·coordinate-dependent basis 검증 |
| 힘장 위상·계약 | source-bound explicit-H 중립 선형 알케인 C1–C4 적용성, graph-only environment key, bond·angle·proper·모든 원자 쌍 분류, 비물리 full parameter protocol/artifact·snapshot-bound assignment, `N≤14` cell-free CPU float64 direct-uncut method/binding 계약과 별도의 binding-report-only schema-owned scalar-energy 진단, SPICE 2.0.1 C1–C4 200행 energy-gradient observation inventory·pair-preserving split·source-bound pair-relative-energy/negative-gradient target view·fit-only bonded-basis conditional-observability 감사, Zenodo/GitHub snapshot·전체 파일/추출 receipt 요구사항·license scope를 분리한 비승격 review 입력 패킷, 그리고 current overlap·계층 split·C5/C6 coverage 경계를 고정한 prospective graph/family preflight | 사람의 license/legal 승인, 전체 HDF5 local-stream integrity receipt와 강한 publisher authentication, admitted subset extraction receipt, 실제 versioned coverage expansion과 graph/family-disjoint reference/manifest/sealed blind evidence, 과학적으로 fitting·검증된 FF type·charge·bonded/LJ parameter, production evaluation method, 과학적으로 검증된 production runtime energy·force·virial kernel와 production 적용 범위 |
| 실행 | fail-closed 내부 CPU orchestrator, C1–C4 비물리 scalar-energy 계약 진단, exact-methane 파라미터·합성 fit 계약과 비실행 조화 energy·force·bonded virial·bounded-descent/restart 수치 진단 | 독립 힘장 runtime, 과학적으로 검증된 최소화, docking, 장거리 물리, MD와 고객 실행 route |
| 검증 | focused CPU tests, wheel, Python 3.10/3.11 CI, canonical hash·tamper·finite-difference·translation·proper-rotation·accepted-prefix restart 계약 검사 | 과학 benchmark, 실제 force-field reference, 실제 ROCm parity, 고객 shadow evidence |

위 `계약` 행의 `zero-occupancy semantics` blocker는 두 additive envelope가
결속하는 exact selected-coordinate numeric-zero crosscheck 밖의 일반 의미론을
뜻한다. 선택 declaration 보존은 missingness, population, completeness 또는
refinement 해석으로 승격되지 않는다.

따라서 현재 상태에서 허용되는 표현은 “V2-0 독립 엔진 스캐폴드와 비승격
V2-1/V2-2 계약 검증 진행”까지다. V2-1 canonical ingest 완료나 V2-2 독립 힘장
구현 완료를 주장해서는 안 된다.
독립 상용 솔버, 검증된 도킹 정확도, all-atom MD, GPU 가속, 단백질 구조 예측,
결합 자유에너지 또는 고객 사용 가능 상태라고 표현해서는 안 된다.

여기서 “구조분석”은 제공된 실험·예측 구조를 입력으로 quality, pocket,
interface, interaction과 mutation 영향을 분석하는 기능이다. sequence에서 3D
구조를 생성하는 de novo structure prediction은 별도의 대형 연구 lane이며
구조분석·도킹·MD 상용화의 필수 선행조건으로 두지 않는다.

## 3. 고정 설계 원칙

### 3.1 물리 엔진과 AI의 역할

독립 물리 엔진이 기준 에너지를 계산하고 AI는 제한된 residual energy를
보정한다.

`E_total = E_independent_physics + sum_i delta_e_i`

AI가 보존력을 직접 주장하는 force vector를 출력하지 않는다. 힘은 전체 scalar
energy의 정확한 역방향 미분으로 정의한다.

`F_i = -dE_total / dr_i`

AI 성능이 부족하거나 OOD가 감지되면 residual을 비활성화하거나 결과를
abstain한다. 독립 물리 기반이 없는 상태에서 AI만으로 상용 분자해석 엔진을
주장하지 않는다.

### 3.2 비어텐션·비트랜스포머 경계

v2 실행 경로에는 full attention, Transformer, dense `[N,N]` learned weight,
global pair tensor를 두지 않는다. 모든 메시지는 bounded sparse graph를 통해
전달한다. 이 선택은 속도만을 위한 것이 아니라 메모리 상한과 실패 동작을
명시하기 위한 제품 계약이다.

### 3.3 E(3), SE(3), parity와 chirality

계획 단계의 “E(3) GNN”은 Euclidean geometric message passing이라는 넓은
방향을 뜻한다. 실제 구현 계약은 다음과 같이 더 엄밀하게 표현한다.

- translation과 proper rotation에 대한 scalar energy invariance
- proper rotation에 대한 force equivariance
- 허용된 atom permutation에 대한 일관성
- R/S, E/Z와 pseudoscalar channel을 통한 명시적 parity·chirality 처리
- 거울상 분자를 동일하게 만드는 distance-only 표현의 금지

현재 parity-aware local-vector·signed-triple-product 구현을 완전한 모든 차수의
E(3) irreducible-representation stack이라고 과장하지 않는다.

### 3.4 T-GNN 명칭 분리

두 종류의 GNN은 목적과 복잡도 증거를 분리한다.

- `TorsionTopologyGNN`: 정적 bond/torsion tree에서 한 번의 topology 전파와
  forward kinematics·reverse adjoint를 수행한다.
- `TemporalStateGNN`: MD 또는 refinement step 사이에서 bounded recurrent
  state를 전달한다.

torsion마다 모든 자손 원자를 재탐색하는 구현은 최악의 경우 `O(N^2)`이므로
금지한다. Temporal full-history 학습은 `O(TN)`이며 고정 메모리 주장에 포함하지
않는다.

### 3.5 PINN의 위치

PINN은 수치 솔버가 아니라 학습 objective와 release gate다. 다음 항목을
검사할 수 있다.

- energy·force supervision과 finite-difference 일치
- 이동·회전·순열·parity 일관성
- net force·net torque residual
- bond·angle·virial·pressure residual
- short-rollout stability
- uncertainty calibration과 OOD abstention

PINN loss가 낮다는 사실만으로 force field, integrator, ensemble 또는 MD가
과학적으로 검증됐다고 판단하지 않는다.

### 3.6 직교사영 순전파·역전파

고정 rank basis `B`에 대해 다음 연산을 직접 적용한다.

`P(v) = B solve(B^T B, B^T v)`

`Q(v) = v - P(v)`

`D x D` projector를 만들지 않는다. rank는 현재 최대 16으로 고정하며 rank
부족과 ill-conditioning은 fail-closed 처리한다. 좌표 의존 basis의 정확한
gradient가 필요할 때 `B`를 detach하지 않으며 finite difference로 basis
gradient를 검증한다.

## 4. 조건부 O(N) 계약

단거리 forward와 reverse가 atom count `N`에 대해 `O(N)`이 되려면 다음
조건을 모두 만족해야 한다.

1. 물리 밀도와 cutoff가 고정돼 directed edge 수 `E <= K*N`을 유지한다.
2. `K`는 `N`과 독립이고 hard cap 256 이하이다.
3. cell occupancy는 hard cap 256 이하이며 overflow는 all-pairs fallback 대신
   실행 차단으로 처리한다.
4. layer 수는 최대 16, local hidden width는 최대 512이며 radial basis,
   channel, irrep order가 `N`과 함께 증가하지 않는다.
5. projection rank는 최대 16이고 dense projector를 만들지 않는다.
6. temporal window, docking candidate budget과 refinement step이 고정된다.
7. `torch.cdist`, dense adjacency, full attention, full Hessian·Jacobian,
   global QR/SVD를 제품 경로에서 사용하지 않는다.

이 조건에서는 sparse forward와 동일한 계산 graph를 역으로 순회하는 force
VJP가 모두 `O(N)`이다. 이는 알고리즘 계약이며 아직 실제 하드웨어 성능
주장이 아니다. 다음 작업은 별도로 정직하게 표기한다.

| 범위 | 복잡도 표기 원칙 |
| --- | --- |
| 고정-window temporal training | `O(WN)` |
| 전체 temporal history | `O(TN)` |
| PME long-range electrostatics | `O(N log N)` |
| FMM | 고정 error tolerance·order·bounded tree에서만 expected `O(N)` |
| docking 전체 | 후보 수와 반복 수를 포함해 보고하며 자동으로 `O(N)`이라 하지 않음 |
| free-energy ensemble | atom 수 외에 lambda·replica·sampling budget을 함께 보고 |

## 5. 기존 구조의 재사용·교체 정책

| 처리 | 재사용 가능한 영역 | 필수 조건 |
| --- | --- | --- |
| 재사용 | claim·provenance·abstention 계약, SoA·zero-copy 개념, compact buffer, Rust/HIP build·FFI, job 상태·경로 격리·복구, evidence·signed report 형식 | v2 소유 interface 뒤에서 dtype·device·lifetime·보안·schema 재검증 |
| 임시 adapter | compact-neighbor 값, legacy `[B,N,K]` training/evaluator 형태, schema 2.1 checkpoint consumer, 구버전 결과 reader | adapted provenance를 기록하고 native v2 과학 결과로 승격하지 않음 |
| 독자 구현으로 교체 | all-atom parser·preparation, heuristic force field, solvent, integrator, pose search, scoring, structure metric, MM/GBSA·FEP, frame-dependent AI correction | 독립 parameter·algorithm·validation·applicability 계약 필요 |
| 보관 | dense attention, proxy score와 공식 metric 명칭을 공유하는 코드, zero-output specialist, 정적 endpoint FEP, 근거 없는 MM/GBSA proxy | v2 runtime에서 접근 불가; 역사적 재현 용도로만 유지 |

자세한 파일별 처리는
[`independent_engine_v2_migration_matrix.md`](independent_engine_v2_migration_matrix.md)를
따른다.

## 6. 목표 제품 아키텍처

```text
입력·전처리 계층
  PDB/mmCIF/SDF/SMILES → canonical all-atom state → chemistry coverage gate
                              │
희소 기하·런타임 계층         ▼
  cell list / Verlet / PBC image shifts / compact buffers / CPU-HIP backend
                              │
독립 물리 계층                ▼
  bonded + nonbonded + long-range + solvent + constraints + integrators
                              │
AI 보정 계층                  ▼
  sparse parity-aware energy + torsion GNN + temporal GNN + PINN + uncertainty
                              │
분석·탐색 계층                ▼
  structure quality / pocket / interface / mutation / docking / MD / free energy
                              │
검증·제품 계층                ▼
  public holdout / evidence / capability gate / local UI·API / report / recovery
```

과학 core와 제품 layer를 분리한다. 제품 UI/API가 존재한다는 이유로 과학
capability가 활성화되지 않으며, 과학 gate를 통과한 capability만 product
dispatch allowlist에 들어갈 수 있다.

## 7. 단계별 개발 로드맵

| 단계 | 핵심 목표 | 선행 의존성 | 종료 시 허용되는 범위 |
| --- | --- | --- | --- |
| V2-0 | 독립 계약·희소 기하·AI 수학 primitive·CPU reference | 없음 | 내부 스캐폴드 실행만 허용 |
| V2-1 | 완전한 all-atom I/O·preparation | V2-0 contracts | 지원 chemistry의 canonical ingest |
| V2-2 | 독립 CPU 단거리 힘장·최소화 | V2-1 identity·coverage | 검증된 chemistry 범위 내 energy·force·minimization |
| V2-3 | 구조분석·torsion-aware docking·scoring | V2-1, V2-2 | 통과한 분석·pose capability의 내부 beta |
| V2-4 | PBC·장거리 물리·용매·constraints·MD | V2-2 | 검증된 ensemble별 내부 MD beta |
| V2-5 | production residual AI와 물리 결합 | V2-2~V2-4 evidence | calibration·OOD gate가 있는 AI 보정 |
| V2-6 | ROCm/HIP 가속 | CPU reference freeze | CPU와 parity가 증명된 AMD 실행 |
| V2-7 | 독립 상용 로컬 제품 | capability별 과학·benchmark·GPU gate | 승인된 capability만 고객 활성화 |

### V2-0 — 독립 엔진 기반

현재 확보한 산출물:

- `betelgeuze_engine_v2/` package와 versioned contracts
- all-atom identity·stereo shell과 explicit legacy adapter
- bounded sparse geometry와 hard capacity
- parity-aware energy, torsion·temporal GNN, PINN, projection primitive
- fail-closed CPU orchestrator
- runtime-input·checkpoint 의미론과 CPU CI

종료 기준:

- CPU compile, focused unit tests와 wheel import가 통과한다.
- covered primitive가 dense all-pairs·dense projector에 의존하지 않는다.
- periodic, scientific, benchmark, GPU, product claim blocker를 유지한다.
- 기존 고객 route를 v2로 자동 전환하지 않는다.

현재 판단: 스캐폴드 기준 완료. 이후 단계의 과학 기능을 대신하지 않는다.

### V2-1 — All-atom I/O와 preparation

주요 산출물:

- PDB·mmCIF·SDF·SMILES 입력과 canonical serialization
- biological assembly, altloc, insertion code, missing atom·residue 정책
- hydrogen, protonation, tautomer, aromaticity와 formal charge
- R/S·E/Z, isotope, water, ion, metal, cofactor와 modified residue
- ligand atom mapping, topology hash, source·변환 provenance
- 지원·미지원 chemistry와 parameterability report

종료 기준:

- round-trip에서 원자·결합·전하·stereo·residue·chain이 조용히 손실되지 않는다.
- supported corpus와 의도적으로 실패하는 failure corpus를 함께 유지한다.
- 미지원 화학을 carbon·alanine·generic bead로 바꾸지 않고 blocker로 반환한다.
- 동일 입력의 canonical hash와 atom order가 재현된다.

현재 판단: 부분 진행. schema-1.4 고정 corpus에서 strict canonical
projection, identity·context 보존, 명시적 실패와 기존 source-bound
explicit-H, 중립, 비동위원소, stereo-unassigned, acyclic saturated H/C
canonical-ingest-only profile의 선택 row를 검증한다.

| 선택 row | V2-1 canonical-ingest 판정 | 고정 경계 |
| --- | --- | --- |
| explicit-H methane | supported | positive row |
| explicit-H ethane | supported | positive row |
| explicit-H propane | supported | positive row |
| explicit-H n-butane | supported | positive row |
| explicit-H branched isobutane | supported | positive row |
| explicit-H cyclobutane | unsupported | `acyclic_graph` |
| hydrogen 하나가 빠진 explicit-H ethane | unsupported | `explicit_valence_closed` |

이 표는 기존 profile의 선택된 evidence일 뿐 화학 지원 범위 전반을
증명하지 않고 C1–C4 size ceiling도 선언하지 않는다. positive row에서도
global preparation·parameterability·simulation·claim은 모두 승격되지
않는다. 여기에 정확히 표현 가능한 parser-owned 단일-record SDF V2000
부분집합만 대상으로 deterministic writer와
`source -> canonical -> emitted SDF -> canonical` 선언 projection 동등성,
재출력 안정성 및 typed fail-closed 동작을 검증한다. 동등성 범위는 atom order,
element, isotope, known formal charge와 원래 encoding class, atom map, 지원 bond
order·aromatic marker, source bond row·endpoint marker, 안전한 header text,
parser가 합성한 단일 `LIG/L` context와 F10.4로 binary64 값이 정확히 재현되는
단일 coordinate model이다. 원본 byte·delimiter 존재 여부, `system_id`·`source_id`,
동적 source SHA·parser observation·전체 canonical snapshot provenance 동일성,
source authentication 또는 SDF stereo 보존을 의미하지 않는다. 이 base writer와
별개인 opt-in data-field envelope 1.0은 `M  END` 뒤 canonical
`>  <FIELD_NAME>` simple named item만 ordered opaque ASCII projection으로
보존한다. 중복 이름·빈 값·여러 줄 값·value-line 앞뒤 공백을 별도 digest에
묶고 stable re-emission을 검증하지만, 값을 SMILES·charge·water/ion role·준비
상태·경로·명령·URL·권한·과학 claim으로 해석하지 않는다. 기존 parser 1.5,
writer 1.0, `AllAtomSystem.metadata`, graph profile pedigree와 golden hash는
변경하지 않는다.

별도의 strict PDB writer 1.2는 parser-owned 상태 중 canonical bond와
altloc가 없는 부분집합과, 정확히 표현 가능한 optional
`CRYST1`를 받는 기존 profile을 유지한다. 추가로 단일 coordinate
model·model ID 1·bondless·no-altloc에서 최소 하나의 typed
source-reported `REMARK 465/470` claim을 갖는 좁은 semantic round-trip
profile을 받는다. 암시적 model과 명시적 `MODEL 1`, 원본 boilerplate,
line number, 470 row grouping과 atom position은 같은 model `[1]`에서 source
ordinal 순서를 보존한 residue/atom claim identity로 정규화한다. NMR range·다른 model ID·multimodel·
header-only·duplicate·coordinate conflict·stale raw/report/coverage/resource와
fixed-column overflow는 실패로 닫는다. 이 범위에서
atom order, `ATOM/HETATM`, atom-name alignment, residue·chain·insertion code,
segment, element, occupancy·B-factor, blank-unknown/명시적 formal charge, model
ID·좌표와 parser-owned `TER` 배치를 보존한다. F8.3 좌표와 F6.2
occupancy·B-factor가 binary64로 정확히 재현되지 않거나 fixed-width를
넘으면 실패로 닫는다. `CRYST1` length·angle은 각각 F9.3·F7.2로
반올림 없이 재현되어야 하고, space group·optional Z와 parser의
삼각함수 공식으로 만든 CPU `float64` cell vector가 전부 binary64로
일치해야 한다. 이 cell은 `(False,False,False)` periodic flag를 유지하는
결정학 metadata이며 simulation/PBC box나 symmetry·assembly 확장을 의미하지
않는다. 원본 공백·line ending·단일 model 표기 방식·`CRYST1` 표기·위치,
resource counter, `system_id`·`source_id`, 동적 source·parser-observation SHA와
전체 snapshot/provenance 동일성은 선언 projection 밖이다. canonical 출력은
optional `CRYST1`, 465 boilerplate/header/I5 claim, 470 boilerplate/header/I4
claim-one-per-line, coordinate/TER, `END` 순서이며 모든 record는 80-column
printable ASCII다. missingness는 20,000줄에서 절단 없이 실패로 닫는다.
receipt는 input raw report SHA·semantic schema/profile/SHA·evidence presence·
input/emitted remark line count·residue/atom count를 hidden input snapshot과 함께 묶는다.
round-trip report는 source/reparse raw report SHA를 따로 기록하지만 semantic SHA
동일성만 주장한다. 이 profile은 source가 보고한 claim만 보존하며 실제
완전성, SEQRES/reference membership, completion/modeling, altloc·assembly·multimodel
missingness, chemistry·preparation·parameterability·simulation·claim 권한을 입증하지 않는다.

별도 opt-in PDB `CONECT` source-declaration envelope 1.0은 변경하지
않은 base parser 1.8.0과 writer 1.2.0 위에서 동작한다. implicit model 1
또는 explicit `MODEL 1`의 단일 coordinate model과 `END` 바로 앞의
연속된 uppercase fixed-column `CONECT` suffix만 받는다. 각 row의
source serial과 1–4개 target slot은 모두 실제 `ATOM/HETATM` serial을
참조해야 하며 self-reference, reserved column, 빈 target gap, model 내부
선언, noncontiguous placement, 다른 model ID와 multimodel은 실패로 닫는다.
explicit `MODEL 1`은 base writer의 implicit single-model 형식으로 정규화된다.

선언 projection은 directed row 순서, source serial, target-slot 순서, 중복
slot, row grouping과 directional asymmetry를 그대로 보존한다. reciprocal row를
합치거나 반복 occurrence를 multiplicity·bond order로 해석하지 않는다.
carrier `AllAtomSystem` 및 coverage의 bond count는 항상 0이고 canonical
`Bond`, bond kind/order, covalence, coordination, chemistry·preparation·
parameterability·physics·runtime·simulation·execution·claim 권한은 전혀
얻지 않는다. declaration은 `AllAtomSystem`이 아니라 envelope evidence에만
존재하므로 bare `.system` 추출·base writer 직렬화는 의도적으로
`CONECT`를 잃는다.

factory-only artifact chain은 full/carrier/canonical source, detached snapshot,
topology, base representable state, ordered declaration projection, source binding,
record state, output·reparse·second emission을 결속한다. canonical 출력은
80-column `CONECT` row를 80-column `END` 직전에 배치하고 두 번째
출력의 byte 안정성을 요구한다. 고정 input/output byte·line, row,
target occurrence, projection, source-ID 상한을 넘으면 절단 없이
실패한다. 5개 round-trip·10개 failure를 고정한 corpus manifest payload
SHA-256은
`c6346f7b046d157a70fb1629dfe3e7f3c13a4b9b079474961a613ec436c38a75`이다.
SHA-256은 tamper/crosswire evidence일 뿐 source authentication이 아니며,
이 envelope은 general PDB round-trip을 준비 상태로 올리지 않는다.

strict mmCIF writer 1.5는 현재 parser가 만든 상태 중 model ID 1인 단일
coordinate model과 reviewed core 11 field를 기반으로 한 기존 여섯 개의 정확한
`_atom_site`-only header profile을 byte 불변으로 유지한다. core11, core11 뒤에
`_atom_site.pdbx_formal_charge`만 추가한 core12, core11 뒤에
`_atom_site.pdbx_pdb_ins_code`만 추가한 core12, 그리고 formal charge 뒤에
insertion code를 이 순서로 추가한 core13, core11 뒤에
`_atom_site.occupancy`만 추가한 core12, 그리고 occupancy 뒤에
`_atom_site.b_iso_or_equiv`를 이 순서로 추가한 core13이다. occupancy는
charge나 insertion code와 결합하지 않으며 B-factor는 이 정확한 pair의 두 번째
열로만 허용한다. profile은 값이 아니라 원본
header inventory로 선택하므로 optional 열이 전부 `.` 또는 `?`여도 그
profile을 유지한다. 이 선언 projection은 atom·residue·chain order와
identity, parser-owned bare 비좌표 token spelling, source atom-site ID·label
identity, 그리고 좌표의 정확한 IEEE-754 binary64 값을 보존한다. 좌표
token spelling은 source text 동일성을 주장하지 않고 deterministic representation으로
정규화한다. CIF 1.1 출력을 재파싱했을 때 동일한
projection·topology를 회복하고 두 번째 출력 byte가 동일해야 한다.
formal-charge profile의 bare `.`·`?`와 `[-32767,32767]` integer token은 `+01`·`+0`·`-0`을
포함해 원시 spelling 그대로 보존하며 canonical charge·knownness·source·
interpretation marker가 그 token과 정확히 일치해야 한다. insertion-code profile의
bare printable-ASCII token도 행별로 보존한다. `.`와 `?`는 모두 canonical blank이지만
raw marker는 같은 residue 안에서도 구분하며, 그 외 token은 canonical
`Residue.insertion_code`와 정확히 일치해야 한다. header가 없으면 canonical
insertion code는 빈 문자열이어야 한다. receipt는 profile과
header count를 묶고 token count는 header 수 `H`, row 수 `N`에 대해
`2 + H * (N + 1)`로 검증한다.
occupancy profile의 bare `.`·`?`는 canonical `None`으로 사상하지만 raw
marker는 구분한다. 그 외 bare single-line token은 standard uncertainty가 없는
finite CIF number이고 exact binary64 값이 `[0,1]`이어야 한다. `+0`·`-0`·
`01.000`·`1.`·`.25`·`1e0` spelling을 보존하며 canonical
`Atom.occupancy`와 binary64 bit까지 묶어 signed zero를 구분한다.
occupancy/B-factor pair의 occupancy도 같은 계약을 사용한다. B-factor는
`bare_dot_question_or_uncertainty_free_finite_binary64/1.0.0` value profile을
사용하며, bare `.`·`?`는 모두 canonical `None`이지만 raw marker는 구분한다.
그 밖의 token은 uncertainty 없는 finite CIF number이면 범위 제한 없이 받으므로
음수도 표현 가능하다. raw spelling, canonical `Atom.b_factor`, exact binary64
hex를 함께 묶어 `+0`과 `-0`을 bit 수준에서 구분한다. `0.5(1)` 같은
uncertainty, quote·multiline·nonfinite token, occupancy/B-factor ESD, header가
없는 live occupancy/B-factor, B-factor-only·reverse·middle 배치, charge 또는
insertion-code와 B-factor의 조합, raw/canonical 또는 atom/first-model payload
drift는 typed failure로 닫는다.

추가 profile
`pdbx_common_core21_complete_label_auth_entity_identity/1.0.0`은 정확히
`_entity.id,_entity.type`, `_struct_asym.id,_struct_asym.entity_id`, 그리고
official-order 21-column `_atom_site` loop만 받는다. `_entity.type`은 bare
`polymer`, `non-polymer`, `water`만 허용하고 auth atom/comp/asym/seq quartet은
모든 atom row에 완전하게 존재해야 한다. category 입력 순서는 layout으로
정규화해 출력은 `_entity`, `_struct_asym`, `_atom_site` 순서로 고정하지만 각
category의 row order와 selected raw bare token spelling은 보존한다. label은
유일한 canonical identity namespace이며 label asym은 struct-asym을 거쳐 entity로
해결되고 atom row의 label entity와 canonical atom·residue·chain entity state가
그 join과 정확히 일치해야 한다. auth quartet은 source alias일 뿐 label과 같다고
가정하지 않는다. 한 label residue 안의 auth comp/asym/seq는 일관되어야 하지만
서로 다른 label chain은 같은 auth asym을 공유할 수 있다.

polymer는 positive label sequence ID가 필요하다. non-polymer와 water는 row별
`.` 또는 `?` label sequence marker와 nonmissing auth sequence alias가 필요하며,
writer는 parser의 source-order synthetic negative canonical residue number를
독립 재계산한다. 같은 canonical residue 안의 `.`·`?` spelling도 row별로
보존한다. `ATOM/HETATM` record와 entity type은 서로 독립이므로 modified-residue
`HETATM` polymer도 polymer로 유지한다. semantic projection
`betelgeuze.mmcif_label_auth_entity_identity_projection/1.0.0`은 raw entity/type,
struct-asym join, atom별 label/auth/entity·selected marker, residue sequence source와
canonical number, chain label/entity/auth-asym set, category row order와 count를
묶는다. receipt/report/aggregate는 이 SHA를 representable-state SHA와 별도로
source/reparse 간 검증한다. common-core21의 token 공식은 entity row `E`,
struct-asym row `S`, atom row `N`에 대해 `8 + 2E + 2S + 21(N + 1)`이며,
writer cap은 각각 4,096, 16,384, 80,000 row, 2,000,000 token, 250,000 line,
2,048 character/line, 64 MiB output이다.

base parser 1.9.0과 writer 1.5.0의 동작·버전을 넓히지 않고, 별도 opt-in
`betelgeuze_engine_v2.molecular.mmcif_altloc_selection` envelope 1.0은 exact
`_entity(id,type)`, `_struct_asym(id,entity_id)`와 official-order common-core21
`_atom_site`만 받는다. single model ID 1·bare ASCII token이어야 하고,
빈 문자열이 아닌 `label_alt_id`를 명시적으로 선택해 적어도 하나의
residue가 그 선택의 영향을 받아야 한다. residue별 blank row와 요청한
alternate row만 selected `AllAtomSystem`에 남기고 다른 alternate row는 제외한다.
envelope는 kept/discarded source ordinal·atom-site ID를 독립적으로 다시 계산해
base parser ledger와 교차 검증하며, 요청 ID 부재·residue별 누락·alternate
atom identity 불일치·blank collision·duplicate identity/atom-site ID는 typed failure다.

source projection은 선택으로 버려지는 row를 포함한 모든 source atom row의
순서·bare token spelling을 보존한다. selected-state projection은 요청 altloc ID,
kept/discarded ordinal·ID, topology·atom/residue/chain order와 coordinate·occupancy·
B-factor의 exact binary64를 별도로 결속한다. 따라서 동일 source에서 A와 B를
각각 선택하면 source projection과 출력 byte는 같지만 selected state와 record
state는 다르다. canonical 출력은 `_entity`, `_struct_asym`, `_atom_site` 순서로
모든 alternate row를 다시 방출하고, 같은 explicit ID로 재파싱한 source/
selected-state·topology 동일성과 두 번째 emission의 byte 안정성을 요구한다.

base writer 1.5.0은 selected-altloc state를 계속 비표현 상태로 거부하고,
envelope는 그 상태에 base representable-state SHA를 잘못 적용하지 않는다. v1은
assembly·nonpoly/polymer·missingness·zero-occupancy envelope, cell·multimodel과
조합하지 않는다. extra category/header, scalar category, quote·multiline token,
numeric uncertainty와 지원 밖 entity type도 삭제하지 않고 typed failure로 닫는다.

factory-only source projection·selected state·record state·source binding·receipt·report·
aggregate chain은 detached snapshot, topology, source ID, output, reparse와 second emission을
서로 결속한다. input·output·projection은 각각 64 MiB, entity는 4,096 row,
struct-asym은 16,384 row, atom-site는 80,000 row, `source_id`는 UTF-8 4,096
byte, source token과 output line은 2,048 character, explicit altloc ID는 256
character로 제한한다. 6개 round-trip·15개
deterministic failure case를 고정한 manifest payload SHA-256은
`652ff9e1c1f849e8f9978fbf57e50ef8b2f1bd80349dde06cf2c1a34ee411625`다.

이 성공은 exact source row 보존과 explicit coordinate selection의 재현성만 증명한다.
source authentication, auth-label equivalence, coordinate completeness, altloc·occupancy
population, occupancy weighting, refinement validity, chemistry·role·bond/order·coordination·
charge·protonation, preparation, parameterability, physics, runtime, simulation, execution,
claim과 general mmCIF/all-format readiness는 모두 false다. 이 additive evidence로 V2-1이나
상용 단계를 완료 처리하지 않는다.

base parser 1.9.0과 writer 1.5.0의 동작·버전을 넓히지 않고, 별도 opt-in
mmCIF explicit biological assembly envelope 1.0.0은 exact common-core21 ASU와
세 assembly loop만 조합한다. `_pdbx_struct_assembly`는 `id` 하나,
`_pdbx_struct_assembly_gen`은 official-order
`assembly_id,oper_expression,asym_id_list`, `_pdbx_struct_oper_list`는 ID·3x3
matrix·3-vector exact 13-field여야 한다. 단일 definition과 explicit
`assembly_id`, generator 256개, operator 1,024개, source ID UTF-8 4,096 byte,
input과 canonical output 각각 64 MiB, selected token 2,048 character, canonical assembly row 2,048
character, single-model-ID1, bare token,
uncertainty-free finite operator만 허용한다.
scalar·mixed/extra category/header, 다른 assembly ID, unknown operator/asym,
non-rigid transform, altloc selection, multimodel, cell/symmetry, missingness와
numeric uncertainty는 typed failure로 닫는다.

envelope는 assembly loop만 떼어 기존 common-core21 writer로 deposited ASU를
canonicalize하고, 세 loop를 `_atom_site` 앞에 재삽입한 뒤 같은 assembly ID로
명시 재파싱한다. expanded atom을 ASU row로 평탄화하지 않으므로 operator를 두 번
적용하지 않는다. declaration projection은 ordered raw token·header·right-to-left
expression semantics·parsed generator를, expanded-state projection은 topology,
atom/chain instance order, source atom/asym pointer, instance/copy-group ID, parser
assembly ledger, exact model ID 1, angstrom 단위, absent periodic cell과 모든
transformed coordinate의 exact binary64를 묶는다. carrier
representable state, source ID, receipt, output, reparse와 두 번째 byte-stable
emission을 교차 검증한다.

envelope parser/writer 1.0.0, base parser name/version·deposited/assembly operation ledger, base writer
version·carrier representable-state schema와 parser/coverage의
`preparation_ready=false`, `claim_safe=false`도 admission에서 고정한다. nested
declaration/expanded evidence는 immutable canonical byte로 저장하고,
receipt/report는 예상 document를 다시 계산한다. aggregate는 첫 receipt와 source
ingest, emitted SHA와 reparsed full-source SHA, 두 번째 receipt와 reparse, source ID와
record state, stable emission을 모두 연결하므로 comment-only·source-ID crosswire와
authority field 위조를 fail closed한다.
canonical full output byte cap도 parse admission에서 미리 계산하므로 성공한
record가 emit 단계에서 뒤늦게 cap을 넘는 상태를 허용하지 않는다.
또한 raw generator/operator row에서 expected sequence·binary64 transform·
deterministic `ASMnnnnnn` chain/atom order·좌표를 독립 재계산한다. expanded atom의
비좌표 canonical state와 source metadata, residue identity/sequence/insertion/entity,
chain entity/source metadata는 명시적으로 합성한 assembly pointer와 chain ID를
제외하고 carrier topology의 exact copy여야 한다.

고정 corpus는 identity, translation two-copy, noncommuting composition positive와
numeric-uncertainty failure를 포함하며 manifest payload SHA-256은
`39a9d73e74ef71b7d740f4751edb35a78439eac059ec0f93f7b9eb5e40edffc5`다. 이
evidence는 source declaration의 진위나 biological correctness, crystallographic
symmetry·PBC, bond·chemistry·protonation·preparation·parameterability·physics·
runtime·simulation·execution·claim 권한을 만들지 않는다. exact envelope 밖
assembly와 general mmCIF은 계속 blocker다.

base parser 1.9.0과 writer 1.5.0의 동작·버전은 그대로 두고, 별도의 opt-in
mmCIF nonpoly identity envelope 1.0이 source가 보고한 비중합체 identity와
instance nomenclature alias만 보존한다. 입력은 exact `_entity`, `_struct_asym`,
common-core21 `_atom_site`에 `_pdbx_entity_nonpoly`의
`entity_id,comp_id` 또는 `entity_id,name,comp_id` exact profile과 다음
official-order `_pdbx_nonpoly_scheme` 10개 field만 더한 형태다:
`asym_id,entity_id,mon_id,ndb_seq_num,pdb_seq_num,auth_seq_num,pdb_mon_id,`
`auth_mon_id,pdb_strand_id,pdb_ins_code`. 출력 순서는 `_entity`,
`_struct_asym`, `_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site`로
고정하고 source/reparse projection과 재출력 byte 안정성을 검증한다. base
`parse_mmcif`가 이 두 category를 받도록 넓히지는 않는다.

선택된 entity-nonpoly row는 source의 `non-polymer`·`water` entity와 정확히
대응해야 하고, comp ID·struct-asym·scheme의 `asym_id,entity_id,mon_id`와
atom-site label residue instance join을 검증한다. `(asym_id,ndb_seq_num)` key는
유일해야 한다. 나머지 ndb/PDB/auth 값과 optional name은 서로 동등하다고
추론하지 않고 source-reported alias로만 보존한다. 이 envelope는 water·solvent·
ion·metal·ligand·cofactor·fragment role, chemistry, `_chem_comp` 또는
`_struct_conn` topology, bond/order·coordination, charge·protonation,
preparation·parameterability, physics·runtime·simulation·execution·claim 권한을
제공하지 않는다.

factory-only receipt·report·snapshot-backed aggregate는 input snapshot·topology·
projection·emitted source·reparse·reemission 연결을 검증하지만 source
authentication이나 preparation·parameterability·simulation·claim 권한을
올리지 않는다.

같은 base parser 1.9.0·writer 1.5.0과 nonpoly identity envelope 1.0을
변경하지 않는 별도 opt-in
`strict_mmcif_nonpoly_component_topology_envelope/1.0.0`은 위의 exact
five-category carrier에 세 category를 더한 exact eight-category profile이다.
`_chem_comp`는 `id,type,pdbx_formal_charge`, `_chem_comp_atom`은
`comp_id,atom_id,type_symbol,charge,pdbx_aromatic_flag,pdbx_stereo_config,`
`pdbx_ordinal`, `_chem_comp_bond`는
`comp_id,atom_id_1,atom_id_2,value_order,pdbx_aromatic_flag,`
`pdbx_stereo_config,pdbx_ordinal` official order만 받는다. canonical category
순서는 `_entity`, `_struct_asym`, `_chem_comp`, `_chem_comp_atom`,
`_chem_comp_bond`, `_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site`다.
그 외 header, scalar·mixed loop, extra category를 삭제하거나 추측하지
않고 typed failure로 닫는다.

v1은 source-reported `H B C N O P S F Cl Br I` organic subset과
atom·bond stereo marker `N`만 받는다. 모든 선택 nonpoly residue
instance의 label atom ID 집합은 해당 component template atom ID 집합과
정확히 같아야 하며 element도 일치해야 한다. `_atom_site` formal
charge가 명시적으로 known이면 template atom charge와 exact 일치해야
하고, source marker가 `.` 또는 `?`인 unknown이면
`_chem_comp_atom.charge`로 canonical charge를 채우고 known으로 만든다.
`_chem_comp.pdbx_formal_charge`는 해당 template atom charge의 exact 합과
같아야 한다. 이는 선택 source declaration의 자체 일관성과 complete
per-instance atom-set을 결속하는 규칙이지 독립 charge assignment·
protonation·oxidation-state 판정이 아니다.

`_chem_comp_bond.value_order`의 exact `SING`, `DOUB`, `TRIP`, `AROM`만
각각 canonical order `1.0`, `2.0`, `3.0`, `1.5`로 사상하고, aromatic
flag가 order와 일치하는지 검사한다. unique template bond를 source
component가 나타나는 모든 complete residue instance에 고정 순서로
확장해 실제 canonical `Bond` row를 생성하며, atom·bond·topology
state와 source template projection을 별도로 결속한다. self bond,
unknown endpoint, duplicate pair/ordinal, atom·component charge 불일치, incomplete
instance, aromatic flag 모순, 지원 밖 order·stereo는 partial result 없이
실패한다. exact reparse는 같은 source projection, 물질화된
atom charge·canonical bond·topology state를 회복해야 하고 두 번째 emission은
byte-stable이어야 한다.

input·output·projection은 각각 64 MiB, `_chem_comp`는 4,096 row,
`_chem_comp_atom`은 80,000 row, `_chem_comp_bond`는 120,000 row,
instance 확장 후 materialized bond도 최대 120,000개, `source_id`는 UTF-8
4,096 byte, source token과 output line은 2,048
character로 제한한다. factory-only projection·topology-state·source-binding·
receipt·report·aggregate chain은 full/normalized source, unchanged carrier state,
detached materialized snapshot, canonical topology, source ID, output, reparse와 second
emission을 서로 교차 검증하며 stale·tamper·crosswire·coherent whole-artifact
replacement을 거부한다. public carrier·receipt·report·aggregate child accessor는
내부 객체가 아닌 fresh detached artifact를 반환한다. public augmented system의
`provenance.source_sha256`는 raw eight-category input
digest이고 canonical output digest는 provenance metadata와 source-binding에 별도
이름으로 결속한다. source ID와 source-specific carrier/base snapshot digest는
source-binding·receipt가, normalized carrier·component projection·canonical
topology 비교는 source-independent topology-state가 담당한다. 고정
positive/failure corpus의 manifest payload
SHA-256은 `d8e1ed2173707c74b0101cdaec1bbacb5df7e875f57ec5243905f8e66166e34d`다.

이 topology envelope의 최종 augmented system은
`betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0` exact parser
pedigree를 사용한다. atom charge·aromatic state와 bond graph를 물질화한
후 최종 canonical topology digest와 parser-observation digest를 다시 계산하여
그 augmented state에 결속한다. base carrier의 이전 digest를 재사용하지
않는다. `_atom_site.pdbx_formal_charge`가 known인 row는
`_chem_comp_atom.charge`와 exact cross-check되었는지, `.`·`?`인 row는
template에서 fill되었는지를 서로 다른 marker 규칙으로 재검증한다.
두 경로는 preparation inventory에서
`metadata_observed_mmcif_chem_comp_atom`으로 보고되지만, charge
assignment가 아니라 source-observation provenance다. explicit H도 exact envelope
pedigree·source atom marker·refreshed observation digest가 함께 일치할 때만
source-observed로 분류한다. digest는 tamper evidence이지 source
authentication은 아니다.

이 경로가 사용하는 component ID·template atom ID·template ordinal·source
aromatic·stereo의 전체 per-atom marker mapping은 parser-observation digest에
직접 결속된다. 따라서 rehash 없는 marker 변조는 digest 불일치로
실패하고, 일관된 digest로 다시 감쌌 경우에도 각 non-polymer·water
instance의 ordinal 집합이 exact `1..N`이 아니면 그 instance의 marker는
preparation evidence로 인정되지 않는다.

이 refresh는 새 chemistry profile을 만들지 않고 기존
`source_explicit_h_neutral_nonisotopic_stereo_unassigned_acyclic_saturated_`
`hydrocarbon_ingest_v1` canonical-ingest profile과 기존
`betelgeuze.profile_local_preparation_evidence/1.0.0` gate를 그대로
소비하게 한다. 현재 고정 evidence에서는 exact single-methane fixture만
`canonical_ingest_supported=true`와
`profile_local_evidence_satisfied=true`를 동시에 만족한다. 이는
source-observed explicit-H·known-zero-charge·H/C-only·single-bond·acyclic·
H=1/C=4 closure에 한정된 graph-local evidence다. 선택 methane row는
profile 전체의 size ceiling을 새로 정하지 않는다. 같은 corpus의 aromatic
benzene, charged ammonium, two-water, mixed-polymer carrier는 기존 profile
규칙에서 계속 nonpositive다. generic `ChemistryCoverageReport.chemistry_supported`,
generic `MolecularPreparationReport.preparation_ready`, global preparation,
independent chemistry·valence·protonation, parameterability·physics·runtime·
execution·simulation·claim은 모두 false 또는 unassessed다.

이 evidence는 exact source-reported nonpoly component template과 그 템플릿에서
물질화한 선택 canonical charge·intra-residue bond graph만 보존한다.
source authentication, independent chemistry·valence·aromaticity·stereo, water·ion·
ligand·cofactor role, protonation, generic/global preparation, parameterability, physics, runtime,
simulation, execution과 claim 권한은 모두 false다. 이 8-category envelope에서
`_struct_conn`, inter-residue·cross-component link는 계속 false며, 아래의 별도
bounded profile만 선택 covalent surface를 다룬다. coordination·metal, stereo `N` 이외,
`SING/DOUB/TRIP/AROM` 이외 bond order, altloc·assembly·missingness·cell·
multimodel과의 조합, polymer template과 general mmCIF round-trip은 계속
blocker다. 따라서 이 envelope는 V2-1 종료 기준을 충족하지 않는다.

이 exact component carrier를 변경하지 않는 다음 additive profile은
`strict_mmcif_nonpoly_covalent_struct_conn_topology_envelope/1.0.0`이다.
envelope parser·writer는 각각 1.0.0이고, 최종 parser pedigree는
`betelgeuze.mmcif_nonpoly_covalent_struct_conn_topology_parser/1.0.0`이다.
canonical category order는 `_entity`, `_struct_asym`, `_chem_comp`,
`_chem_comp_atom`, `_chem_comp_bond`, `_pdbx_entity_nonpoly`,
`_pdbx_nonpoly_scheme`, `_struct_conn`, `_atom_site`의 exact 9-category다.

`_struct_conn`은 다음 exact 23-field official order만 받는다: `id`,
`conn_type_id`, `ptnr1_label_asym_id`, `ptnr1_label_comp_id`,
`ptnr1_label_seq_id`, `ptnr1_label_atom_id`, `pdbx_ptnr1_label_alt_id`,
`pdbx_ptnr1_pdb_ins_code`, `ptnr1_symmetry`, `ptnr2_label_asym_id`,
`ptnr2_label_comp_id`, `ptnr2_label_seq_id`, `ptnr2_label_atom_id`,
`pdbx_ptnr2_label_alt_id`, `pdbx_ptnr2_pdb_ins_code`, `ptnr1_auth_asym_id`,
`ptnr1_auth_comp_id`, `ptnr1_auth_seq_id`, `ptnr2_auth_asym_id`,
`ptnr2_auth_comp_id`, `ptnr2_auth_seq_id`, `ptnr2_symmetry`,
`pdbx_value_order`. scalar·mixed·reordered·extra header/category는 보존할 수
있다고 가정하지 않고 typed failure로 닫는다.

각 row는 exact bare `conn_type_id=covale`, explicit lowercase
`pdbx_value_order=sing|doub|trip`, 양쪽 exact identity symmetry `1_555`를
요구한다. 양쪽 `label_seq_id`=`.`, label-alt marker=`.`, PDB insertion
marker=`?`이며, 각 endpoint의 complete label+auth atom identity가 component-materialized
carrier의 단 하나의 atom에 동시에 join되어야 한다. 양 endpoint는
`non_polymer` 또는 `water`인 서로 다른 residue instance에 속해야
한다. missing·crosswired·ambiguous·same-residue·self·duplicate/reversed·
already-materialized·polymer endpoint는 partial result 없이 실패한다.

수용한 `sing/doub/trip`은 order `1.0/2.0/3.0`, nonaromatic,
stereo-none, source `mmcif_struct_conn_covale`의 canonical inter-residue `Bond`로
물질화한다. 이것은 source-reported bounded topology projection이지 독립
covalence·bond-order·valence·chemistry 판정이 아니다. 모든 bond를 추가한
뒤 exact new pedigree로 final canonical-topology digest와 parser-observation digest를
둘 다 다시 결속하며, inherited component digest를 augmented graph의
권한으로 쓰지 않는다.

factory-only projection·topology-state·source-binding·receipt·report·aggregate
chain은 exact component carrier, ordered 23-field row, endpoint join, materialized bond,
raw/canonical source digest, detached snapshot, refreshed topology/observation, source ID,
exact reparse와 byte-stable second emission을 교차 결속한다. input·output·
projection은 각 64 MiB, `_struct_conn` row와 총 materialized bond는 각각
120,000개, source ID는 UTF-8 4,096 byte, token·output line은 2,048 character로
제한한다. 고정 manifest
`config/independent_engine_v2_v2_1_mmcif_nonpoly_covalent_struct_conn_topology_corpus.json`
은 3개 round-trip과 15개 typed failure, strict JSON·fixture path confinement,
live limit·artifact crosswire evidence를 묶고 payload SHA-256
`2a8a2428ff39646f964af01773bc69b3f71cb03cfaba78b7ebb30ef2ba2d2704`를
고정한다.

이때 source-independent topology-state는 normalized component carrier state,
ordered `_struct_conn` projection과 final canonical topology만 담고, source ID와
carrier/final detached snapshot digest는 source-binding·receipt chain에만 둔다.
public carrier·receipt·report·aggregate child accessor는 fresh detached artifact를
반환하므로 caller-side mutation이 retained parent를 오염시키지 않는다.

이 profile은 새 chemistry·preparation profile을 만들지 않는다. exact
`split_ethane_sing` fixture는 두 nonpoly residue에 나뉘 그래프를 선택
`covale sing` row로 연결해, 기존
`source_explicit_h_neutral_nonisotopic_stereo_unassigned_acyclic_saturated_`
`hydrocarbon_ingest_v1`과
`betelgeuze.profile_local_preparation_evidence/1.0.0`의 변경 없는 ethane
규칙을 만족한다. 따라서 이 exact row만
`canonical_ingest_supported=true`와
`profile_local_evidence_satisfied=true`를 얻는다. generic chemistry,
generic/global preparation, independent chemistry·valence·bond-order, parameterability,
physics, runtime, simulation, execution과 claim 권한은 모두 false 또는
unassessed다.

general `_struct_conn`, `disulf`·`hydrog`·`metalc`·salt/ionic 해석,
`quad`·omitted/default order, nonidentity symmetry, coordination, polymer endpoint,
altloc·assembly·missingness·cell·multimodel과의 composition은 계속
blocker다. general cross-component topology·general mmCIF·V2-1은 완료되지
않았다.

같은 base parser 1.9.0·writer 1.5.0 및 nonpoly envelope 1.0을 변경하지 않고,
별도 opt-in mmCIF polymer sequence membership envelope 1.0은 exact
`_entity_poly_seq.entity_id,num,mon_id,hetero` loop만 추가한다. carrier는 exact
common-core21이거나 기존 nonpoly identity envelope와 조합된 상태여야 한다.
canonical 출력 순서는 base 모드에서 `_entity`, `_struct_asym`,
`_entity_poly_seq`, `_atom_site`, 조합 모드에서 `_entity`, `_struct_asym`,
`_entity_poly_seq`, `_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site`다.
source/reparse projection, optional nonpoly record state와 두 번째 emission의 byte
안정성을 함께 결속한다. standalone write artifact는 canonical payload fixed point와
polymer·base topology/representable·optional nonpoly state를 receipt에 다시 대조하고,
공개 evidence 직렬화도 fresh source·coverage·missingness·composed carrier 결속을
재검증한다. 7개 round-trip·7개 fail-closed case manifest의 payload SHA-256은
`accee9d4f69cd85c069f2b58d515f0a5ea4b0bccce3d90b7422b54b295ced289`다.

sequence row는 source의 모든 `polymer` entity를 정확히 덮고, `num`은 entity별
1부터 연속인 canonical positive decimal이어야 한다. 모든 polymer atom-site의
`label_entity_id,label_seq_id,label_comp_id`는 해당 membership row와 정확히
join해야 하며, 같은 entity를 여러 asym이 공유할 수 있다. v1은 duplicate position과
일반 mmCIF microheterogeneity를 의도적으로 fail-closed로 두고 bare `n`·`no`만
받아 canonical `n`을 출력한다. `mon_id`는 `_chem_comp` 검증 없는 opaque source
code다. matching atom-site가 없는 row는 “selected coordinate row에서 관측되지 않은
source member”로만 보존하며 missing-residue fact나 completeness로 승격하지 않는다.

이 envelope는 reference sequence 동일성, sequence·coordinate completeness,
auth/label alignment, modeled residue 존재, modified-residue identity,
microheterogeneity chemistry, preparation·parameterability, physics·runtime·simulation·
execution·claim 권한을 제공하지 않는다. `_entity_poly`, `_pdbx_poly_seq_scheme`,
reference-sequence, missingness, modified-residue 및 chemical-component category는
계속 차단된다.

별도 opt-in
`betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology` envelope
1.0은 변경 없는 exact 4-category polymer-sequence child에
`_chem_comp`, `_chem_comp_atom`, `_chem_comp_bond`를 더한 exact 7-category
fully-observed polymer component-topology surface다. canonical 순서는
`_entity`, `_struct_asym`, `_entity_poly_seq`, `_chem_comp`,
`_chem_comp_atom`, `_chem_comp_bond`, `_atom_site`이며 source category-order
variant는 이 순서로 정규화된다. child는 독립적으로 자신의
source를 parse·emit해야 하고 wrapper는 child grammar나 membership 의미를
넓히지 않는다.

이 profile은 source에 적힌 `polymer` entity를 sequence row가 정확히
덮고, 각 entity의 모든 asym×sequence position 조합에 coordinate residue
인스턴스가 정확히 하나씩 존재할 때만 받는다. 각 인스턴스는
선택 component template의 atom을 이름·element까지 정확히 한 번씩 모두
포함하고 extra atom이 없어야 한다. component definition은 sequence에
나타난 unique `mon_id` 집합을 정확히 덮고 quoted case-insensitive
`L-peptide linking`만 canonical spelling으로 수용한다. element는 H/C/N/O/S,
atom stereo는 source-reported N/R/S, bond stereo는 N만 허용하며 atom·bond
ordinal은 component별 positive contiguous sequence여야 한다. component formal
charge는 atom charge 합과 일치해야 한다.

알려진 `_atom_site.pdbx_formal_charge`는 template charge와 crosscheck하고
`.`·`?`는 template에서 결정적으로 fill한다. `SING/DOUB/TRIP/AROM`은
각각 canonical 1.0/2.0/3.0/1.5 bond로 물질화하며 aromatic flag도
정확히 일치해야 한다. atom aromatic·N/R/S는 source template metadata와
parser-observation marker로 보존할 뿐 독립 CIP·stereo·chemistry 판정이
아니다. bond는 정확히 residue 내부에만 생성하며 bondless child에
peptide·inter-residue·cross-component·`_struct_conn`·coordination bond를
추론해 추가하지 않는다.

완성된 detached system은
`betelgeuze.mmcif_polymer_component_topology_parser/1.0.0` pedigree를 받고,
charge·aromatic·stereo marker·bond 물질화 후 attached canonical-topology와
parser-observation digest를 둘 다 다시 계산한다. source-independent state는
정규화된 carrier·component projection·최종 topology만 결속하고 raw source,
source ID, canonical output, detached snapshot digest는 source-binding과 receipt
chain에 둔다. factory-only ingest/write/receipt/report/aggregate artifact는 exact
emitted-source reparse와 byte-stable second emission까지 재검증한다.

preparation inventory는 이 pedigree를 이름만으로 허용하지 않는다. exact
system profile과 모든 negative-authority field, provenance marker·carrier 의미,
exact 21-field `_atom_site` row shape와 그 label/auth·source-record·element·
sequence·altloc·insertion·model identity의 canonical atom/residue/chain 대조,
carrier category/resource/missingness ledger, 각 polymer atom의 component/
template ordinal·aromatic·N/R/S·charge fill/crosscheck marker, 각 residue 내부
bond의 component·endpoint·ordinal·order·aromatic·stereo·source를 모두 다시
맞춘 경우에만 recognized/self-consistent로 분류한다. parser는
`betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/1.0.0`
commitment를 붙이고 preparation은 이를 재계산한다. 그 commitment를 그대로 둔
stale observation과 topology/observation-only coherent rehash는 `unrecognized`로
fail closed한다. 이 commitment는 unkeyed digest-bound tamper evidence이며 source
authentication이 아니다. commitment와 모든 enclosing digest를 함께 다시 쓸 수
있는 행위자는 이 검사의 threat model 밖이다. 정상 inventory의 explicit source
H와 `_chem_comp_atom` charge 출처는 preparation report에 관찰값으로 연결하지만,
preparation·parameterability·peptide-link chemistry·physics·runtime·simulation·
execution·claim 상태를 승격하지 않는다.

input/output/projection은 각 64 MiB, sequence/component/component-atom/
component-bond/materialized-bond row는 각 100,000/4,096/80,000/120,000/
120,000개, source ID는 UTF-8 4,096 byte, selected token과 canonical output line은
2,048 character로 제한한다. 고정 3-round-trip/15-failure corpus는
`config/independent_engine_v2_v2_1_mmcif_polymer_component_topology_corpus.json`에
선언되며 canonical-manifest payload SHA-256
`6ae0e794e849b66f3d9f98717d3608e29e99852ed4853812692d6b54afea2808`를 결속한다.

이 coverage는 선택 source/template 상대 evidence일 뿐 CCD authentication,
reference/general completeness가 아니다. exact template 밖 modified residue·terminal
variant, D-peptide, nucleic acid, saccharide, peptide/inter-residue bond, general
chemistry·valence·completion, preparation·parameterability·physics·runtime·simulation·
execution·claim 권한, general mmCIF과 V2-1 완료는 계속 false 또는
blocked다.

별도 opt-in
`betelgeuze_engine_v2.molecular.mmcif_archive_standard_l_peptide_topology`
envelope는 parser/writer 1.0.0, pedigree
`betelgeuze.mmcif_archive_standard_l_peptide_topology_parser/1.0.0`, profile
`strict_mmcif_archive_standard_l_peptide_ALA_GLY_heavy_topology/1.0.0`을
사용한다. exact category는 `_entity`, `_entity_poly`, `_struct_asym`,
`_entity_poly_seq`, `_atom_site` 다섯 개이고 이 engine-selected 순서로
canonical emit한다. `_entity_poly` header는 exact `entity_id`, `type`,
`nstd_chirality`, `nstd_linkage`, `nstd_monomer`이며
후자 네 값은 bare `polypeptide(L),no,no,no`여야
한다. 나머지 네 category는 변경 없는 polymer-sequence carrier가
독립적으로 수용해야 하며 explicit link field나 추가 category는 fail-close한다.

이 profile은 pinned offline engine-owned rule에서 sequence-implied archive-standard
ALA/GLY heavy reference graph만 물질화한다. GLY core role은 N/CA/C/O,
ALA는 여기에 CB를 추가한다. asym별 마지막 residue와 singleton은 OXT를
반드시 갖고, outgoing sequence link가 있는 residue는 OXT를 갖지 않는다.
Intra-residue bond는 exact manifest rule에서 오며, 같은 asym의 인접한
`_entity_poly_seq` 위치만 exact single C(i)--N(i+1)로 연결한다. n개
residue chain은 exact n-1 path를 갖고 cross-asym bond는 없다. 좌표 거리와
auth alias는 topology 선택에 쓰지 않으며 이 값의 변경이 graph를 바꾸지
않는다.

Rule manifest schema는
`betelgeuze.standard_l_peptide_heavy_topology_rule_manifest/1.0.0`, SHA-256은
`4d941815d26431a5de9bd74b4860f84ce39232e7123ee87b3b61a104457eb244`다.
공식 CCD provenance는 ALA
`https://files.rcsb.org/ligands/download/ALA.cif`, 6,071 byte, SHA-256
`6d32b34d4f7b3ddf0cd3dff3f98ddaf7649bc5303ff9a8bd95ba62283f47a1ca`, type
`L-PEPTIDE LINKING`; GLY
`https://files.rcsb.org/ligands/download/GLY.cif`, 5,615 byte, SHA-256
`c49458946b0ebc057db6ad0a4e1557a1caaed4c80a203accd458efddccbf92ff`, type
`PEPTIDE LINKING`(즉 L type이 아님)을 고정한다. 둘 다 initial 1999-07-08,
modified 2024-09-27, release status REL이다. 이 파일 hash는 tamper evidence일
뿐 source authentication이 아니며 runtime은 CCD를 fetch하지 않고 내장 rule
manifest를 다시 hash한다.

Projection/state/source-binding/write-receipt/round-trip-report schema는 각각
`betelgeuze.mmcif_archive_standard_l_peptide_topology_projection/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_state/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_source_binding/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_write_receipt/1.0.0`,
`betelgeuze.mmcif_archive_standard_l_peptide_topology_round_trip_report/1.0.0`으로
고정된다.
Factory-only artifact chain은 ordered projection, rule manifest, final graph,
detached system, source identity, canonical output, exact reparse와 byte-stable 두 번째
emission을 상호 결속한다. Graph 물질화 후 canonical-topology와
parser-observation digest를 둘 다 새로 계산한다.

Parser provenance marker는
`betelgeuze.mmcif_archive_standard_l_peptide_topology_preparation_inventory_commitment/1.0.0`
schema와 SHA를 함께 결속한다. Preparation bridge는 exact rule manifest,
carrier ledger, system/chain/residue/atom/bond marker key set, graph와 commitment를
의미론적으로 재계산한 후에만 pedigree를 recognized로 다룬다. Commitment를
두고 topology/observation만 coherent rehash한 tamper는 fail-close한다. 고정
5-positive 모두 parser pedigree가 recognized이고 observation이 self-consistent하지만
canonical ingest는 `unsupported`, preparation은 `incomplete`이며 `invalid`는 아니다.
어떤 promotion도 없다.

Input/output은 각 64 MiB, source ID는 UTF-8 4,096 byte, token은 2,048 character,
atom row는 80,000개, materialized bond는 300,000개로 제한한다. 고정
5-positive/24-failure corpus
`config/independent_engine_v2_v2_1_mmcif_archive_standard_l_peptide_topology_corpus.json`의
canonical payload SHA-256은
`58377d1b60a493e62a53af8250c912b49b7475e76d41316ee8d2380ffaf967de`다.
성공은 rule manifest match·sequence-implied heavy reference topology·same-asym 인접
peptide reference bond만 확인한다. Source-observed covalence, coordinate peptide
geometry나 chain-break 탐지/배제, source authentication, formal charge·H·protonation·
stereo 할당, modified/nonstandard monomer, generic chemistry·preparation·parameterability,
physics·runtime·simulation·execution·claim, general mmCIF/all-format readiness와 V2-1은
모두 false다.

앞의 fully-observed polymer component-topology child를 변경하지 않는 별도
opt-in
`betelgeuze_engine_v2.molecular.mmcif_polymer_component_terminal_leaving_policy`
envelope 1.0은 profile
`strict_mmcif_polymer_component_terminal_leaving_annotation_envelope/1.0.0`을
사용한다. category 집합과 canonical category 순서는 기존 exact 7-category
polymer component-topology와 같고, `_chem_comp_atom` header만 다음 exact
official-order 11-field로 확장한다.

`comp_id, atom_id, type_symbol, charge, pdbx_aromatic_flag,
pdbx_leaving_atom_flag, pdbx_stereo_config, pdbx_backbone_atom_flag,
pdbx_n_terminal_atom_flag, pdbx_c_terminal_atom_flag, pdbx_ordinal`.
Wrapper는 0-based index `0,1,2,3,4,6,10`을 순서 그대로 투영해 기존 exact
7-field child source를 만들고, 그 source가 변경 없는 child parser에서 독립적으로
수용·canonical emit되는 경우에만 성공한다. 네 추가 flag는 bare `Y` 또는 `N`만
받아 ordered source annotation으로 보존하며 atom 이름, 좌표, 거리, valence 또는
component 이름에서 값을 추론하지 않는다.
원본 source stage와 canonical reparse stage는 각각 두 번째 exact child parse를
수행한다. private proof는 parser pedigree, component projection, topology state,
augmented topology, source binding, serialized system byte, snapshot, parser
observation, preparation-inventory commitment, canonical child emission을 실제로
비교한다. 기존 state는 exact 12-field required/pass-and-comparison gate map을,
source binding은 같은 gate map과 private proof SHA-256·state hash를 결속한다.
policy/round-trip report는 이 computed gate를 소비한다. 불일치는 typed
error로 fail-close한다.
source stage와 canonical reparse stage의 child proof·parser observation은 source/provenance
canonicalization으로 달라질 수 있으므로 cross-stage 동일성을 요구하지 않는다.

`betelgeuze.mmcif_polymer_terminal_leaving_rules/1.0.0`은 이 보존 규칙과
`singleton`, `n_sequence_boundary`, `internal`, `c_sequence_boundary` 네 위치 role만
고정한다. 각 role은 `_struct_asym`과 `_entity_poly_seq` 순서로부터 asym별로
결정되는 sequence boundary일 뿐 chemical terminus, retained/leaving atom,
reaction endpoint 또는 peptide-link chemistry가 아니다. 같은 component template이
internal과 boundary 위치에 나타나도 wrapper는 terminal variant를 합성하거나
다르게 적용하지 않는다.
canonical rules payload SHA-256은
`9235a365be1ee9f0189f94f37ed3317ff14903f0469d41f6fea2a6d2678f92b1`이다.

성공 결과의 `AllAtomSystem`은 같은 stage에서 독립 투영·parse한 child system의
byte-exact snapshot이며 parser
pedigree `betelgeuze.mmcif_polymer_component_topology_parser/1.0.0`, canonical
topology, parser observation과
`betelgeuze.mmcif_polymer_component_topology_preparation_inventory_commitment/1.0.0`
값도 그대로 유지한다. Annotation projection, rules/policy report, child state와
source binding, wrapper receipt와 round-trip report는 factory-only artifact chain에
결속된다. 따라서 bare system serialization은 wrapper annotation evidence를
의도적으로 잃으며, child chemistry/topology 권한을 넓히지 않는다.

Wrapper는 child의 polymer-sequence 100,000행, component 4,096행,
component atom 80,000행, component bond 120,000행, materialized child bond
120,000개 cap을 그대로 사용한다. input/output/projection은 각각 64 MiB,
source ID는 UTF-8 4,096 byte, token과 canonical output line은 2,048 character로
제한한다. 3개 round-trip과 20개 deterministic failure를 고정한 corpus
`config/independent_engine_v2_v2_1_mmcif_polymer_component_terminal_leaving_policy_corpus.json`은
canonical-manifest payload SHA-256
`3cfc5731f9943479f7246baf17148ac52a52b3557b35a584a14a6e606a579a3d`를 결속한다.

이 envelope는 `chemical_terminal_state_assessed`, `terminal_chemistry_assigned`,
`leaving_atom_policy_applied`, `leaving_atoms_removed`, `peptide_bonds_inferred`,
`inter_residue_bonds_materialized`를 모두 false로 고정한다. H/H2/OXT 또는 다른
atom을 삭제하지 않고, C/N 이름이나 geometry로 peptide bond를 만들지 않으며,
generic chemistry, generic/global preparation, parameterability, physics, runtime,
simulation, execution, claim, general mmCIF과 V2-1 상태를 승격하지 않는다.

`betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_neutral_preparation`
은 위 두 증거 surface를 하나의 raw source에서 독립적으로 다시
투영한 뒤에만 적용하는 별도의 non-writer 준비 transform 1.0이다.
profile은
`strict_mmcif_ALA_GLY_source_explicit_CCD_neutral_linkage_preparation/1.0.0`,
literal policy는
`exact_ALA_GLY_source_explicit_CCD_neutral_linkage_policy/1.0.0`이다. exact
8-category `_entity`, `_entity_poly`, `_struct_asym`, `_entity_poly_seq`,
`_chem_comp`, `_chem_comp_atom`, `_chem_comp_bond`, `_atom_site` source를 받아
exact 7-category terminal/leaving child와 exact 5-category archive-heavy child가
각각 독립적으로 수용되는지 검증한다. 이 경로는 outer-source writer,
write receipt 또는 canonical mmCIF round-trip을 구현하지 않는다.

고정 preparation-rule manifest schema는
`betelgeuze.standard_l_peptide_neutral_linkage_preparation_rule_manifest/1.0.0`,
SHA-256은
`daa2beb6648d2749204093bfd0db5dd316cb38557b29890054ddc54c73193d7f`이다.
source template은 ALA 13 atom/12 bond, GLY 10 atom/9 bond를 완전히
포함해야 하고 모든 formal charge는 known zero여야 한다. ALA CA는
source stereo `S`, 나머지 선택 stereo marker는 `N`이다. outer child는 ALA와
GLY 모두 quoted `L-peptide linking`으로 normalization하며, official GLY CCD의
`PEPTIDE LINKING`과 byte-exact하다고 주장하지 않는다.

role policy는 `singleton`에서 삭제하지 않고,
`n_sequence_boundary`에서 OXT/HXT, `internal`에서 H2/OXT/HXT,
`c_sequence_boundary`에서 H2만 삭제한다. 나머지 atom과 coordinate는
source의 exact binary64 값을 유지하며 hydrogen을 생성하지 않는다. 같은
asym의 연속 sequence position에만 single C(i)--N(i+1) bond를 추가한다.
link가 `L`개면 atom과 source bond를 각각 exact `3L`개 삭제하고 `L`개 bond를
추가하여 최종 bond 수가 source bond 수에서 `2L`을 뺀 값이어야 한다.
준비된 heavy induced graph는 독립 archive child와 일치해야 한다.

factory-only state/source-binding/report/atom-mapping/parameter-requirement
inventory는 raw source, 두 child, transformed snapshot, topology/observation,
mapping과 heavy crosscheck를 결속한다. `verify_replay()`는 보존한 raw
source에서 state를 byte-exact로 재생하지만 serialization round-trip 증거가
아니다. parameter inventory는 atom/bond/angle/proper/nonbonded/partial-charge
요구량만 나열하고 improper·CMAP을 나열하지 않으며 production parameter
set은 missing이다. 4-positive/16-failure 고정 corpus manifest
`config/independent_engine_v2_v2_1_mmcif_standard_l_peptide_neutral_preparation_corpus.json`
은 canonical payload SHA-256
`c5c0ab935305c8d15fb2868c8327d38622de85fe84b8426e32d14be88ff3c20d`를
결속한다. 따라서
`profile_molecular_preparation_assessed/ready`만 true고 generic/global
preparation, pH/protonation correctness, parameterability, physics/energy/force,
runtime/minimization/simulation/execution/claim, general mmCIF/all-format readiness와
V2-1 완료는 모두 false다.

다음 bounded slice인
`betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_heavy_completion`
은 exact 5-category archive-heavy ALA/GLY source만 받는 별도의 non-writer
heavy-to-all-atom transform 1.0이다. profile은
`strict_mmcif_ALA_GLY_heavy_complete_fixed_neutral_microstate_completion/1.0.0`,
policy는
`exact_ALA_GLY_heavy_to_fixed_neutral_microstate_completion_policy/1.0.0`이다.
같은 raw byte를 archive child가 독립 수용한 뒤에만 transform을 시작한다.
engine-owned rule manifest schema
`betelgeuze.standard_l_peptide_heavy_to_fixed_neutral_all_atom_completion_rule_manifest/1.0.0`
와 SHA-256
`eed2b432c6a4b916370e14d922830a5eeb9f531acc579c94b7e823b8949810c6`은
공식 ALA/GLY CCD ideal coordinate decimal token, atom ordinal, H parent와
sequence-role inventory를 offline으로 고정한다. CCD file과 manifest hash는
tamper evidence이지 source authentication이 아니다.

모든 source heavy coordinate는 output에서 binary64 bit-exact로 유지한다.
active intra-residue heavy bond 길이는 pinned ideal의 ±0.20 Å, 같은 asym의
인접 C--N은 inclusive 1.15–1.55 Å여야 한다. 각 residue의 N--CA--C frame
normalized sine은 0.05 이상이어야 하고, ALA는 N/C/CB-about-CA normalized
triple의 absolute value가 0.05 이상이면서 ideal과 같은 positive orientation을
가져야 한다. 이 값들은 bounded profile admission일 뿐 angle, omega, clash,
conformation 또는 scientific geometry validation이 아니다.

role-active hydrogen은 pinned ideal parent-relative vector를 ideal N--CA--C
frame에서 source frame으로 회전하고 retained parent에 anchor해 결정적으로
생성한다. output mapping은 모든 atom을 `source_retained`와
`profile_generated`의 disjoint union으로 나누고 generated H의 parent, rule
ordinal과 manifest SHA를 결속한다. 모든 formal charge는 fixed-neutral profile이
소유하는 known zero이며 ALA CA의 `S`도 profile-owned assignment다. 이는
environmental pH/protonation correctness나 independent CIP가 아니다.

factory-only state/source-binding/report/mapping/parameter-requirement artifact는
raw source, archive child, completed snapshot, topology/observation digest와 rule
manifest를 함께 결속한다. `verify_replay()`는 raw source에서 byte-exact state를
재계산하지만 outer writer나 serialization round-trip은 없다. atom/bond/angle/
proper/nonbonded/partial-charge instance requirement는 중복 없이 열거하지만
improper와 CMAP은 열거하지 않고 production parameter set은 missing이다.
4-positive/13-failure corpus
`config/independent_engine_v2_v2_1_mmcif_standard_l_peptide_heavy_completion_corpus.json`
은 canonical payload SHA-256
`7fed000628174709fb5cd30955239f65e9395e981d3a34422fdcdb3a932bfb1f`를
결속한다. profile-local heavy completion과 molecular preparation readiness만
true이며 generic/global preparation, generic H completion, parameterability,
physics/runtime/energy/force/minimization/simulation/execution/claim, general
mmCIF/all-format readiness와 V2-1 완료는 모두 false다.

polymer sequence와 nonpoly component-topology 두 기존 선택 surface를 함께
보존하는 별도 opt-in module
`betelgeuze_engine_v2.molecular.mmcif_polymer_sequence_nonpoly_component_topology`
은 envelope/parser/writer 1.0.0과 profile
`strict_mmcif_polymer_sequence_nonpoly_component_topology_composition_envelope/1.0.0`
을 사용한다. exact canonical category order는 `_entity`, `_struct_asym`,
`_entity_poly_seq`, `_chem_comp`, `_chem_comp_atom`, `_chem_comp_bond`,
`_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site`다. 이 module은
9-category source를 변경 없는 exact 8-category nonpoly component-topology
child와 exact 6-category polymer-sequence+nonpoly-identity child로 분리하고,
두 child가 각자 원래 envelope에서 독립적으로 수용된 경우에만 composition을
수용한다.

source-independent composition state는 shared nonpoly identity projection과 record
state, base topology와 representable state, data block을 교차 결속한다.
두 child writer가 출력한 공통 `_entity`, `_struct_asym`,
`_pdbx_entity_nonpoly`, `_pdbx_nonpoly_scheme`, `_atom_site` loop와 shared
nonpoly writer payload도 byte-exact여야 한다. child별 provenance가 다르므로
이 계약은 child snapshot digest의 직접 동일성을 주장하지 않는다. detached
`AllAtomSystem`은 component child가 소유하고 exact component-carrier system
pedigree `betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0`을 유지한다.
polymer membership은 canonical system chemistry나 polymer topology가 아니라
ordered source evidence로만 남는다. wrapper artifact identity는 위 profile과
`betelgeuze.mmcif_polymer_sequence_nonpoly_component_topology_state/1.0.0`
state schema에만 부여하며 새 system parser pedigree를 만들지 않는다.

factory-only state/source-binding/receipt/report artifact는 full source, source ID,
child source binding, component snapshot, 두 child projection과 semantic state,
shared carrier, canonical output을 결속한다. public nested artifact는 fresh detached
reconstruction이다. canonical output의 exact reparse는 두 child와 composition
state를 다시 회복하고 emitted payload와 reparsed raw source가 byte-exact여야 하며
두 번째 emission도 byte-stable해야 한다. input/output은 각 64 MiB, polymer
sequence row는 100,000개, component row는 4,096개, component atom row는
80,000개, component bond row는 120,000개, selected token은 2,048 character,
source ID는 UTF-8 4,096 byte로 제한한다. 고정 manifest
`config/independent_engine_v2_v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition_corpus.json`
은 2개 positive와 6개 deterministic failure를 묶고 canonical-manifest
payload SHA-256 `6ac10b99e058134bdcbf1739afd7d2d719dd15667890530e9c716beb14592e69`을 고정한다.

이 composition은 두 기존 child의 동시 보존 범위만 좁게 닫는다. polymer
template·modified-residue chemistry, reference-sequence 동일성 또는 완전성,
coordinate completeness·missingness, `_struct_conn`, altloc·assembly·cell·
multimodel과의 composition, generic/global preparation, parameterability,
physics, runtime, simulation, execution, claim 권한과 general mmCIF support는
모두 false 또는 차단 상태다. 따라서 V2-1을 완료로 표시하지 않는다.

별개의 downstream opt-in
`betelgeuze_engine_v2.molecular.mmcif_unobserved_residues` envelope 1.0은 기존
polymer sequence carrier 또는 nonpoly identity가 조합된 같은 carrier에 exact
official-order `_pdbx_unobs_or_zero_occ_residues` residue loop 하나만 더한다. v1은
11개 field `id,polymer_flag,occupancy_flag,pdb_model_num,auth_asym_id,`
`auth_comp_id,auth_seq_id,pdb_ins_code,label_asym_id,label_comp_id,label_seq_id`를
정확히 요구하며, `polymer_flag=Y`, `occupancy_flag=1`, model `1`인 bare ASCII
row만 받는다. 각 label residue는 `_struct_asym`에서 polymer entity로 해결되고
exact `_entity_poly_seq(entity_id,num,mon_id)` row에 join해야 하며, 같은
`(label_asym_id,label_seq_id,label_comp_id)`가 selected `_atom_site`에 있으면
claim 모순으로 거부한다. source row ID와 semantic residue key는 각각 유일해야
한다.

canonical 출력 순서는 base carrier에서 `_entity`, `_struct_asym`,
`_entity_poly_seq`, `_pdbx_unobs_or_zero_occ_residues`, `_atom_site`이고, 조합
carrier에서는 두 nonpoly category를 residue loop 앞에 둔 seven-category
순서다. ordered claim projection, polymer 및 optional nonpoly record state,
topology·snapshot·source binding, factory-only receipt/report/aggregate와 byte-stable
second emission을 교차 검증한다. normalized 출력은 raw missingness layout을
보존하지 않으므로 source/reparse raw missingness-report SHA 동일성은 주장하지
않고, source-independent semantic projection과 record-state 동일성만 검증한다.
입력은 64 MiB, selected claim은 20,000 row, selected identity token은 256자,
`source_id`는 UTF-8 4,096 byte로 제한한다. 6개 round-trip·14개 fail-closed case
manifest의 payload SHA-256은
`003b7f870a988fd39f83ca23302edeef2cd7d7123ea72a1c0508c8ee202b4750`다.

이 성공은 “source가 해당 polymer residue를 unobserved라고 보고했다”는 ordered
claim이 선택된 envelope에서 보존됐다는 뜻뿐이다. source authentication, 실제
missing-residue fact, reference-sequence 동일성, sequence·coordinate completeness,
auth-label equivalence, modeled/modified-residue identity, chemistry, preparation,
parameterability, physics, runtime, simulation, execution 또는 claim 권한을 만들지
않는다. atom-level `_pdbx_unobs_or_zero_occ_atoms`, `occupancy_flag=0`의
zero-occupancy 의미론, 다른 model, general missingness surface와 raw layout
round-trip은 계속 차단된다. base parser/writer와 polymer/nonpoly envelope의 기존
동작·버전도 변경하지 않는다.

같은 base 및 carrier 계약을 바꾸지 않는 네 번째 opt-in module
`betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms` envelope 1.0은 exact
official-order `_pdbx_unobs_or_zero_occ_atoms` loop 하나를 보존한다. field 순서는
`id,polymer_flag,occupancy_flag,pdb_model_num,auth_asym_id,auth_comp_id,`
`auth_seq_id,pdb_ins_code,auth_atom_id,label_alt_id,label_asym_id,`
`label_comp_id,label_seq_id,label_atom_id`다. v1은 bare ASCII token,
`polymer_flag=Y`, `occupancy_flag=1`, model `1`만 받으며 `label_alt_id`는 raw
`.` 또는 `?`만 허용한다. source row ID는 canonical positive decimal
`<=2^53-1`이고 ID와 선택 semantic atom key는 각각 유일해야 한다. residue와
atom missingness loop가 동시에 있는 입력은 v1에서 fail-closed다.

각 label identity는 `_struct_asym`을 통해 exact `polymer` entity로 해결되고
`_entity_poly_seq(entity_id,num,mon_id)`에 join해야 한다. 또한 model 1의 selected
coordinate에 exact `(label_asym_id,label_seq_id,label_comp_id,pdb_ins_code)` 부모
residue가 존재해야 하며, 그 안의 exact `(label_atom_id,label_alt_id)` atom은
존재하지 않아야 한다. `pdb_ins_code`와 `label_alt_id`의 raw `.`·`?`는 projection에서
서로 구분하지만 coordinate 비교에서는 둘 다 blank로 정규화한다. auth 값은 opaque
source alias일 뿐 label과 동등하다고 추론하지 않으며 atom-name dictionary나 residue
template도 조회하지 않는다. 기존 base missingness report와는 category·ordinal·model·
label residue/atom identity·정규화된 insertion/altloc·raw token·control·source row ID를
행별로 다시 대조하고 residue claim 0개, atom claim `N`개를 요구한다.

canonical 출력은 base carrier에서 `_entity`, `_struct_asym`, `_entity_poly_seq`,
atom missingness, `_atom_site` 순서이고, composed carrier에서는 기존 두 nonpoly
category를 atom missingness 앞에 둔다. ordered projection, polymer 및 optional
nonpoly record state, topology·detached snapshot·full/normalized source·source-ID,
base missingness report, factory-only receipt/report/aggregate와 stable second emission을
서로 결속한다. raw source와 canonical reparse의 missingness-report SHA는 별도로
기록하고 layout 정규화 때문에 동일성을 주장하지 않는다.

입력·출력 cap은 64 MiB, selected identity token은 256자, `source_id`는 UTF-8
4,096 byte다. unchanged base parser가 missingness value를 최대 40,000개 보존하고
이 loop는 row당 14개 value이므로 v1의 실제 row cap은 `floor(40000/14)=2857`이다.
2,858번째 row는 typed failure로 닫고, 2,048자를 넘는 유효 canonical row는 token별
line으로 분리해 CIF line cap을 지킨다. 6개 round-trip·10개 manifest failure case의
payload SHA-256은
`82081b2061386e90e2bf5e7ec94e5e6ab43d03c534d709dfbb76ffe7dbe33f7f`이다.
이 envelope가 보존하는 것은 ordered
source-reported unobserved-atom claim뿐이다. 실제 missing-atom fact, reference/sequence/
coordinate completeness, auth-label equivalence, modeled atom 존재, residue-template·
atom-name 검증, completion, modified-residue identity, chemistry, preparation,
parameterability, physics, runtime, simulation, execution 또는 claim 권한은 모두 false다.
`occupancy_flag=0`, nonpoly atom claim, nonblank altloc, 다른 model, 선택 범위 밖 general
atom missingness와 raw-layout round-trip도 계속 차단된다.

그 다음의 별도 additive module
`betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_residues` envelope 1.0은
같은 exact polymer-sequence carrier 또는 기존 nonpoly-identity 조합 carrier에
official-order 11-field `_pdbx_unobs_or_zero_occ_residues` loop의
`occupancy_flag=0` branch 하나만 더한다. base mmCIF parser 1.9.0, writer 1.5.0,
polymer-sequence/nonpoly-identity envelope 1.0과 기존 두 `occupancy_flag=1`
unobserved envelope의 동작·버전은 바꾸지 않는다. v1은 bare ASCII
`polymer_flag=Y`, `occupancy_flag=0`, model `1` declaration만 받고, label tuple이
`_struct_asym`의 exact polymer entity와 `_entity_poly_seq` member에 join하도록
요구한다. source row ID와 normalized-insertion-qualified semantic residue identity는
각각 유일해야 하며 atom zero-occupancy category 또는 두 zero category의 동시
입력은 fail-closed다.

선택 residue는 model-1 common-core21 `_atom_site`에 exact label asym·positive
label sequence·component·normalized insertion identity로 실제 존재해야 한다.
그 identity에 matching하는 모든 atom/alternate row의 occupancy는 bare,
uncertainty-free, finite numeric token이고 그 exact numeric 값이 zero여야 한다.
matching row 부재, `.`/`?` 또는 nonnumeric/unavailable 값, 단 하나의 nonzero
match라도 typed failure다. 이는 selected-coordinate consistency crosscheck일 뿐
zero occupancy에서 missing residue를 추론하는 규칙이 아니다.

`betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atoms` envelope 1.0은 같은
원칙을 official-order 14-field `_pdbx_unobs_or_zero_occ_atoms` loop에 적용한다.
bare `polymer_flag=Y`, `occupancy_flag=0`, model `1`, raw `.`/`?`
`label_alt_id`만 받고, exact normalized-insertion parent residue와 normalized blank
altloc의 exact label atom이 selected model-1 coordinate에 모두 존재해야 한다.
그 exact atom identity에 matching하는 모든 occupancy가 finite numeric zero여야
하며, parent/atom 부재, unavailable/nonzero occupancy, nonblank altloc, duplicate
semantic identity 또는 residue zero-occupancy loop 동시 입력은 실패한다.

base parser의 preserve-only evidence는 두 envelope 모두 missing-residue/atom claim
count가 각각 0이어야 한다. residue envelope는 `residue_row_count=N`,
`zero_occupancy_residue_row_count=N`, atom 관련 두 count 0을 요구하고, atom
envelope는 그 반대 count를 요구한다. 두 경우 모두 extension count는 0이며 이
metadata의 별도 SHA를 record state·source binding·receipt·report에 결속한다.
canonical 출력은 declaration을 `_atom_site` 바로 앞에 둔 five/seven-category
순서이며 exact output reparse와 byte-stable second emission을 요구한다.

입력 cap은 64 MiB, selected identity token은 256자, `source_id`는 UTF-8 4,096 byte다.
unchanged base parser의 40,000 preserved-value cap에 따라 residue 11-field loop는
`floor(40000/11)=3636` row, atom 14-field loop는
`floor(40000/14)=2857` row까지만 받는다. 두 envelope의 6개 round-trip·19개
failure case를 합친 manifest payload SHA-256은
`96564c7b9d4d70eed7ac65188783a6de0acf33a01ac18b7e0559afb28f61ae40`이다.

두 성공 결과가 보존하는 것은 ordered source declaration과 exact selected-
coordinate numeric-zero crosscheck뿐이다. source authentication, 실제 missing
atom/residue fact, occupancy population·weighting, altloc population,
sequence/coordinate completeness, refinement validity, reference/auth equivalence,
chemistry, preparation, parameterability, physics, runtime, simulation, execution,
claim과 general mmCIF readiness는 모두 false다. 따라서 이 additive evidence로
V2-1 또는 상용 로드맵 완료를 표시하지 않는다.

unchanged base parser/writer에서 common-core21의 exact `_entity`·`_struct_asym`
밖 non-`_atom_site` category,
기존 여섯 profile 또는 common-core21 외 field 집합, partial auth, 지원 밖 entity type과
다른 optional field,
canonical bond, exact explicit-altloc/assembly envelope 밖 selection, selected unobserved/zero-occupancy
residue/atom-level envelope 밖 source declaration, cell,
multimodel은 삭제하지 않고 typed failure로 닫는다. 선택된 두 nonpoly category는
별도 opt-in envelope에서만 받고, `_entity_poly_seq`와 selected residue/atom-level
unobserved loop, 그리고 두 `occupancy_flag=0` loop도 각각의 별도 opt-in
envelope에서만 받는다. 원본 공백·comment와 single/double quote
delimiter 선택은 layout이라 projection 밖이지만, optional name의 quoted/bare
token class는 bare missing marker와 quoted literal을 구분하도록 결속한다. full
source/base bytes와 detached serialized system snapshot은 각 SHA에 결속하고,
`system_id`·`source_id`, 동적 parser-observation SHA와 source/reparse 사이 전체
snapshot/provenance 동일성은 identity 주장이 아니다. 여기서 formal-charge source notation 보존은
charge assignment, protonation, oxidation/electronic state, ion·metal·cofactor
role, preparation, parameterability, simulation 또는 claim 근거가 아니다.
`pdbx_pdb_ins_code` 보존도 auth numbering, polymer sequence alignment·완전성,
modified-residue 의미, missingness, altloc, assembly, entity role 근거가 아니다.
occupancy/B-factor spelling 보존도 altloc population·occupancy weighting,
zero-occupancy missingness·완전성, refinement validity, atomic mobility,
temperature, disorder, 실험 uncertainty assessment·propagation,
chemistry·preparation·parameterability·simulation 또는 claim 근거가 아니다.
auth alias 보존은 label-auth 동일성 또는 numbering 정합성 근거가 아니고, source
entity type 보존은 polymer sequence completeness, modified-residue chemistry,
water·ion·ligand·cofactor role 근거가 아니다. 선택 nonpoly component
topology의 charge·bond도 source-reported template에서 materialize된 것일 뿐
독립 chemistry·valence·aromaticity·stereo 판정이 아니다. general mmCIF
category와 선택 common-core21·explicit-altloc selection·nonpoly identity·nonpoly
component topology·polymer sequence membership·source-reported
unobserved-residue·unobserved-atom·zero-occupancy-residue·zero-occupancy-atom
envelope 밖 auth/entity
surface는 계속
미지원이다.

strict SMILES writer 1.8은 현재 strict parser-owned 상태 중 source heavy
graph가 source order의 1–256개 component이고 global cycle rank가 0 또는 1인
organic-subset graph만 받는다. rank 1이면 cyclic component는 정확히 하나이고,
dependency-free iterative degree peel로 얻은 2-core가 simple cycle이며 closure는
parser 배열의 마지막 source bond여야 한다. non-aromatic profile은 3–8개 atom,
exact-single closure, all-single 또는 정확히 하나의 nonclosure double edge를
요구한다. selected aromatic profile은 5/6개 atom이고 모든 ring atom만 aromatic,
모든 ring bond만 exact binary64 1.5·aromatic·stereo-none이어야 한다. ring 밖의
tree·branch source edge는 exact single·double·triple 중 하나일 수 있다.
component·root·parent edge와 source/expanded membership은 metadata를 신뢰하지
않고 live graph에서 유도하며 `R in {0,1}`에 대해
`E_source=V_source-F+R`, `E=V-F+R`를 각각 검증한다. source-order
DSU로 tree/non-tree edge를 한 번에 나누고, 유일한 closure는 parser 배열의
마지막 source bond여야 한다. source atom은
`B C N O P S F Cl Br I`의 known-charge `{-1,0,+1}`·non-isotopic 상태이며,
map은 없거나 positive unique여야 한다. typed atom stereo는 아래 bounded
parser-owned tetrahedral R/S+exact RDKit CW/CCW 상태만 허용한다. source H와
선택 aromatic/tetrahedral 상태 밖 bracket-explicit H는 거부한다. selected aromatic token에 필요한
`[bH-] [cH-] [nH] [nH+] [oH+] [pH] [pH+] [sH+]`만 정확히 한 개의
`bracket_explicit` generated H를 허용하고, 각 admitted tetrahedral center의
ligand로도 0/1개를 허용한다. 그 밖의 generated H는 trailing
`implicit`이다. charged parent의 implicit H는 금지한다. generated H 자체는 known neutral이고
parent·origin·origin-local ordinal marker와 single·non-aromatic generated bond가 정확해야
한다. source bond stereo는 exact `none`, `E`, `Z`만 허용되고, `E/Z`는
non-aromatic exact-double source tree edge 또는 선택 8-member ring의 유일한
nonclosure double edge에만 속할 수 있다. 각 endpoint에는 parser가 보존한 서로
다른 source-neighbor reference가 정확히 하나씩 있어야 하며 generated H는
reference나 direction carrier가 될 수 없다. unknown bond stereo는 계속 fail
closed다. 각 graph component마다 정확한 `L1`–`Ln` residue·chain, 빈 CPU
`float64 (0,N,3)` coordinate carrier와 no-cell 상태도 정확히 유지해야 한다.
source atom이 모두 generated H보다 먼저 오므로 residue atom index는
비연속일 수 있다.

출력은 closure edge를 제거한 graph-derived forest의 root 각각에서 source
order로 시작하는 반복형 DFS와 정렬된
child order로 만든 한 줄 ASCII이며 root 사이에만 `.`을 하나 출력하고 전체
textual visitation은 source atom order와 같아야 한다. source edge를 한 번만
순회해 O(V+E) parent bond-token table을 만들고 branch·continuation child 직전에
빈 token, `=`, `#` 또는 bounded E/Z carrier의 `/`, `\\`를 출력한다. 고정 profile
`ordered_acyclic_organic_forest_bounded_formal_charge/1.0.0`은 rank 0에,
`ordered_forest_with_one_simple_unicyclic_component_bounded_formal_charge/1.0.0`은
rank 1에 선택된다. cycle policy는 rank 0의 no-ring과 all-single ring에는
`at_most_one_simple_nonaromatic_3_8_member_all_single_bond_source_ring/1.0.0`,
one-double ring에는
`at_most_one_simple_nonaromatic_3_8_member_source_ring_with_exactly_one_nonclosure_double_bond/1.0.0`이
선택된다. no-ring의 ring-bond profile은 `None`이고, ring-bond profile은
all-single의 `all_single_nonaromatic_stereo_none/1.0.0`과 one-double의
`one_nonclosure_double_otherwise_single_nonaromatic_stereo_none/1.0.0`으로 분리된다.
선택 8-member ring의 유일한 nonclosure double이 parser-typed E/Z이면 cycle과
ring-bond profile은 각각
`one_simple_nonaromatic_8_member_source_ring_with_exactly_one_nonclosure_parser_typed_ez_double_bond/1.0.0`,
`one_nonclosure_parser_typed_ez_double_otherwise_single_nonaromatic/1.0.0`이다.
fully aromatic ring은
`at_most_one_simple_fully_aromatic_5_6_member_b_c_n_o_p_s_source_ring/1.0.0`,
`all_order_1_5_aromatic_stereo_none/1.0.0`,
`ordered_forest_with_one_simple_fully_aromatic_5_6_member_ring_selected_unit_charge_and_canonical_bracket_hydrogen_states/1.0.0`을 선택한다.
ring이 있으면 closure endpoint 두 atom token 뒤, branch·continuation
앞에 marker `1`을 즉시 출력하며 closure가 E/Z direction carrier이면 close
endpoint marker는 `/1` 또는 `\\1`이다. raw label `0`, `2`, `9`, `%10`, `%99`는
graph spelling일 뿐이며 모두 `1`로 정규화되고 writer는 `%10`을 출력하지 않는다.
source atom token은 typed parser state에서 한 번 계산한다. stereo-free unmapped
charge 0은 bare element, `+1`은 `[Element+]`, `-1`은 `[Element-]`이고, admitted
atom map과 tetrahedral marker는 bounded bracket token을 사용한다. emitter는 이
token table을 사용할 뿐 charge·CIP label·protonation·valence chemistry를 유도하지 않는다. aromatic profile은
finite lowercase/bracket token table을 사용하고 `[cH]`처럼 canonicalization이
bracket-H origin을 없애는 상태는 fail closed다. aromatic edge의 빈 출력 token은
projection에 묶인 exact 1.5/aromatic 상태를 single bond로 강등하지 않는다.
E/Z carrier는 source-bond index가 가장 낮은 인접 exact-single·non-aromatic·
stereo-none edge를 선택한다. tree carrier의 lexical 방향은 parent→child,
closure는 close→open이며, `/=0`, `\\=1`, `E=1`, `Z=0`인 XOR 식에 carrier와
parser reference의 차이 및 endpoint를 향하는 emission 방향을 함께 반영한다.
conjugated double들이 carrier를 공유하면 전체 constraint graph에서 함께 풀고,
closure가 포함된 component는 closure `/`를 stable gauge anchor로 삼는다.

bounded tetrahedral center는 non-aromatic이고 정확히 네 개의 source 또는
bracket-H ligand, implicit H 0개, bracket-explicit H 0/1개, exact-single·
non-aromatic·stereo-none incident bond만 가져야 한다. profile
`source_order_dfs_parser_typed_tetrahedral_cw_ccw_lexical_parity_with_zero_or_one_bracket_hydrogen/1.0.0`
아래 source-order DFS emitter는 모든 center를 먼저 `@`로 출력해 pinned parser로
trial parse 한 번을 수행한다. trial의 local CW/CCW가 source와 다른 center만
`@@`로 바꾼 뒤 final parse 한 번으로 모든 center의 R/S와 CW/CCW가 각각 정확히
같은지 확인한다. 이 보정은 independent CIP assignment가 아니다. typed center는
source graph당 최대 256개이고, typed center가 하나라도 있으면 source atom은
최대 514개다. 이 조건에서 selected ring, bounded E/Z, positive unique atom map,
center당 bracket-H 0/1개가 기존 graph profile 안에서 함께 존재할 수 있다.
typed center가 있는 515개 이상 source-atom graph는 일반 4,096-source-atom parser
상한과 별개로 calibration parse 전에 fail closed한다.

component를 정렬하거나
atom을 재색인하지 않으므로
`CC.C -> C.CC`처럼 canonical component order가 달라지는 입력은 normalized hash
gate에서 거부한다. 출력 SHA는
parser가 기록한 normalized-isomeric-SMILES SHA와 같아야 하고, 같은 pinned
RDKit 계약으로 재파싱한 declared representable-state·topology가 동일하며 두 번째
출력 byte도 같아야 한다. 따라서 `C-C -> CC`처럼 raw spelling은 정규화될 수
있고 원문 byte·identifier·전체 snapshot·동적 provenance 동일성을 주장하지
않는다. hidden input snapshot을 가진 factory-only write result와 snapshot-backed
aggregate가 parent source·snapshot·topology·parser observation·reemission 연결을
재계산한다. representable state와 receipt는 formal-charge/cycle profile ID,
`betelgeuze.smiles_component_cycle_projection/1.3.0` SHA, component cycle-rank,
ring atom/bond table, source-index 순서
bond-order table, dynamic cycle/ring-bond profile, ring double count·index, closure index·endpoint,
source marker table, source/tree edge count, source atom token,
charged-source-atom count와 formal-charge total도 묶고 unit-charge count/total
parity를 검증한다. 별도
`betelgeuze.smiles_aromatic_ring_projection/1.0.0`은 atom element·charge·known-charge·
aromatic·implicit/bracket-H·token row, bond endpoint·exact-order·aromatic·stereo·
tree/closure role, bracket-H generated atom/bond·parent·origin·ordinal을 source-index
순서로 묶으며 receipt·report·aggregate가 그 SHA와 count/profile을 재검산한다.
별도 `betelgeuze.smiles_ez_stereo_projection/1.0.0`은 typed E/Z source double,
endpoint별 parser reference, 선택된 carrier, lexical from/to와 tree/closure role,
`/`·`\\` token, reference-carrier·emission-orientation parity와 shared-carrier
XOR constraint를 source-index 순서로 묶는다. lowest-index carrier policy와
normalized-spelling hash gate를 모두 통과하는 source tree의 branched·conjugated·
multi-component E/Z, 3–8-member selected simple ring에 인접한 exocyclic E/Z,
그리고 선택 8-member ring의 임의 위치 유일 nonclosure E/Z double이 이 bounded
profile에 포함된다. 구조적으로 비슷해도 다른 carrier placement가 canonical인
상태는 hash mismatch로 fail closed할 수 있다.
별도 `betelgeuze.v2_1_smiles_e_z_writer_corpus/1.1.0`은 이 경계의 17개
positive fixed point를 고정하며 manifest payload SHA-256은
`a58207f72b9127b3adf1cde9499b765ec934f7162fe52ef720aae74ebff8b03f`이며,
기존 ingest corpus의 E/Z 두 case-record SHA도 직접 재계산해 묶는다.
별도 `betelgeuze.smiles_tetrahedral_stereo_projection/1.0.0`은 각 center의
source atom index·optional map·target R/S·target CW/CCW, source-neighbor와
incident-bond order, emitted parent·closure·branch·continuation·ring marker,
optional bracket-H atom/bond, trial/final marker·stereo·tag·token을 묶는다.
receipt·report·aggregate가 input/reparse projection SHA를 교차 검증한다. 별도
`betelgeuze.v2_1_smiles_r_s_writer_corpus/1.0.0`, corpus ID
`v2_1_strict_smiles_bounded_r_s_writer_v1`은 bracket-H/no-H R/S, positive map,
multiple center, selected ring, E/Z coexistence, multi-component, charged N,
S, B, stereo-free baseline을 포함한 14개 inline-ASCII positive case를 고정하며,
최종 manifest payload SHA-256은
`34a1cadfe0c3fa321bfb256c28d723c29465c85384ec2e99f1022aef71a636fc`이며,
capability와 CI에 함께 묶는다.
이 결속은 authentication이나 preparation·parameterability·
simulation·claim 권한을 올리지 않는다. 선택 formal-charge serialization은 charge
assignment, protonation, tautomer, oxidation/electronic state, partial charge,
ion·salt·mixture·counterion role 또는 chemistry support가 아니다. bounded
parser-typed E/Z 및 R/S 직렬화는 독립 CIP assignment, global stereo
completeness, substituent equivalence, stereo geometry, conformation 또는
chemistry 판정이 아니다. E/Z projection 자체는 atom stereo를 인코딩하지 않고,
writer 1.8이 별도 tetrahedral projection으로 이를 묶는다. bounded cycloalkene과
selected parser-observed aromatic 직렬화도 unsaturation,
independent aromaticity·resonance·Kekulization·electronic structure,
ring strain·conformation·valence·protonation·tautomer·chemistry 해석이 아니다.
non-aromatic 9-member 이상, aromatic 5/6-member 밖, 두 번째 cycle,
fused·spiro·bridged, non-aromatic multiple-bond closure, ring triple,
두 번째 ring double edge, nonpositive/duplicate map, bounded tetrahedral R/S 밖
atom stereo, unknown bond stereo, 8-member 밖 ring-internal E/Z 또는 bounded
tree/simple-ring carrier profile 밖 E/Z, source H와 선택 aromatic/tetrahedral
상태 밖 bracket H는 계속
fail closed다. Kekule raw input은 sanitize된 source-index
순서가 canonical일 때만 lowercase aromatic byte로 정규화되며 raw spelling은 보존하지 않는다.

generic preparation inventory는 canonical validation·topology hash·audit
allocation 전에 atom 100,000, bond 200,000, residue 100,000, chain 100,000의
고정 상한을 검사한다. 초과 입력은 typed `PreparationCoverageLimitError`로
실패하며 contextual inventory, profile-local evidence와 canonical applicability도
같은 오류를 그대로 전파한다. 상한 이내의 기존 report schema·byte·digest와
모든 non-promotion 상태는 바뀌지 않는다. 이 값은 audit 안전 한계일 뿐 지원
system size, 성능, preparation 완료 또는 실행 권한 주장이 아니다.

`require_profile_local_preparation_evidence`는 이 좁은 local evidence를
소비하는 typed gate다. 매번 fresh report를 계산하고
`profile_local_evidence_satisfied=true`일 때만 그 report를 반환하며, 그 외에는
동일 report·status·bounded blocker를 가진 typed error를 낸다. resource-limit과
wrong-type 오류는 감싸지 않는다. 성공 반환도 global preparation·
parameterability·simulation·claim 상태를 승격하지 않는다.

별도 additive
`betelgeuze.cycloalkane_c3_c8_graph_profile/1.0.0`은 parser-owned SDF V2000
입력 중 source-observed explicit-H, 중립, 비동위원소, unmapped,
stereo-unassigned, nonaromatic single-bond unsubstituted monocycle만 판정한다.
C3–C8, 식 CnH2n, 하나의 connected simple carbon cycle, 각 C의 C 이웃 2개와
source H 이웃 2개, 각 H의 C 이웃 1개, source-observed known-zero formal charge,
partial charge 부재를 모두 요구한다. hidden canonical snapshot에서 generic
chemistry·preparation report version/SHA, canonical topology, parser-observation
schema와 attached/recomputed SHA, source-indexed exact graph projection, frozen
rule과 최종 report SHA를 매번 다시 묶는다. 이 SHA는 authentication이 아니다.

positive에서 true가 되는 공개 값은 `profile_chemistry_supported`와
`profile_graph_preparation_ready` 두 개뿐이고, exact scope는
`source_observed_graph_local_identity_and_valence_only`다. typed require gate는
`cycloalkane_c3_c8_graph_profile_audit` consumer 하나만 허용한다. projection
digest는 source atom/bond index를 보존하므로 order-independent graph-isomorphism
identity가 아니다. 동일 graph의 admission은 유지하되, 서로 다른 source-index
상태는 snapshot과 projection digest로 구분한다.

별도 versioned corpus는 C3–C8 전 positive와 C2/C9, branched,
fused·spiro, unsaturated, hydrogen 부족·초과, heteroatom, charge, isotope와
disconnected 실패를 고정한다. SMILES adapter-generated-H·wrong-pedigree 경계는
RDKit-version-dependent snapshot digest를 SDF corpus에 섞지 않고 별도의 pinned
focused test로 고정한다. 기존 acyclic canonical-ingest
profile의 explicit-H cyclobutane `acyclic_graph` negative row는 그대로이며, 같은
source가 이 additive profile에서만 positive다. C3–C8은 versioned product-profile
경계이지 C9 화학이 잘못됐다는 판정이 아니다.

성공 row에서도 `global_molecular_preparation_ready`, 환경 pH·protonation,
ring strain, conformation·geometry quality, parameterability, force-field type·
partial charge·parameter, physics, runtime, execution, energy·force,
minimization, simulation과 claim은 모두 false 또는 unassessed다. 따라서 이
profile과 corpus는 V2-1 완료나 V2-2 힘장 적용 범위 확대를 의미하지 않는다.

그 다음 additive
`betelgeuze.terminal_monoalkene_c2_c8_graph_profile/1.0.0`의 exact profile
ID는
`source_observed_explicit_h_neutral_unbranched_terminal_monoalkene_c2_c8/1.0.0`
이다. parser-owned `betelgeuze.sdf_v2000_parser/1.5.0` 상태 중
source-observed explicit-H,
원자별 source-observed known-zero formal charge, C/H only, nonisotopic,
unmapped, stereo-unassigned, nonaromatic인 하나의 component만 판정한다.
C2–C8, 식 CnH2n, connected carbon simple path, exact terminal C=C 하나,
나머지 C–C/C–H single bond를 모두 요구한다. C2 ethene은 double
bond 양 endpoint가 모두 path endpoint고, C3–C8은 정확히 한 endpoint만 path
endpoint다. atom·bond의 exact SDF source metadata와 integer source bond-order
ledger C=4/H=1도 함께 고정한다.

exact scope는
`source_observed_graph_local_unbranched_terminal_monoalkene_identity_and_bond_order_valence_ledger_only`
다. 여기서 unbranched는 carbon induced graph가 simple path라는 뜻이지
좌표가 직선이거나 정렬됐다는 geometry 주장이 아니다. source ledger
closure는 parser가 관찰한 bond-order annotation과 graph의 자체 일관성만
확인한다. 독립 bond-order·valence·unsaturation·E/Z·CIP·conjugation·
electronic-structure 검증으로 사용하지 않는다. source-indexed projection은
order-independent graph-isomorphism identity가 아니고, 각 SHA는 authentication이
아닌 tamper evidence다.

positive에서 true가 되는 값은 `profile_chemistry_supported`와
`profile_graph_preparation_ready` 두 개뿐이다. typed require gate는
`terminal_monoalkene_c2_c8_graph_profile_audit` consumer 하나만 허용한다.
C2–C8은 versioned product-profile 범위이므로 유효한 terminal C9 row는
`carbon_count_c2_c8` 범위만 실패하며 C9 화학이 잘못됐다고 판정하지
않는다. 별도 versioned corpus는 ethene부터 oct-1-ene까지의 positive와
크기·internal double·branched·cyclic·diene·alkyne·alkane·hydrogen ledger·
heteroatom·charge·isotope/map·aromatic·disconnected 경계를 고정한다.

성공 row에서도 generic chemistry와 generic/global molecular preparation,
pH·protonation·tautomer,
E/Z·CIP, conformation·geometry, electronic structure, parameterability,
force-field type·partial charge·parameter, physics, runtime, execution,
energy·force, minimization, simulation과 claim은 모두 false 또는 unassessed다.
이 SDF-derived profile은 SMILES writer의 선택 multiple-bond serialization 범위를
넓히거나 general alkene chemistry support를 주장하지 않는다. 또한 V2-1 완료나
V2-2 힘장 적용 범위 확대를 의미하지 않는다.

그 다음 additive
`betelgeuze.exact_h2o_graph_profile/1.0.0`의 exact profile ID는
`source_observed_explicit_h_neutral_h2o_graph/1.0.0`이다. parser-owned
`betelgeuze.sdf_v2000_parser/1.5.0` 상태 중 source-observed explicit H 두 개와
산소 하나, 원자별 SDF atom-block known-zero formal charge, nonisotopic,
unmapped, stereo-unassigned, nonaromatic인 한 component만 판정한다. exact
O–H single bond 두 개, O degree·integer source bond-order ledger 2, 각 H
degree·ledger 1, exact source atom/bond metadata와 parser가 합성한
`LIG/non_polymer`·`L/ligand` residue/chain context를 모두 요구한다.
hidden canonical snapshot에서 topology, generic chemistry/preparation report,
parser-observation attached/recomputed digest, source-indexed projection, frozen rule와
최종 report를 재계산하여 각 SHA를 결속하지만, 이 digest는 source
authentication이 아니다.

exact scope는
`source_observed_graph_local_h2o_identity_and_bond_order_valence_ledger_only`이고,
positive에서 true가 되는 공개 값은 `profile_chemistry_supported`와
`profile_graph_preparation_ready` 두 개뿐이다. typed require gate는
`exact_h2o_graph_profile_audit` consumer 하나만 허용한다. source-indexed
projection은 order-independent graph-isomorphism identity가 아니며, source ledger
closure는 parser가 관찰한 bond-order annotation과 graph의 자체 일관성만
고정한다. 독립 bond-order·valence·protonation·electronic-structure
검증으로 사용하지 않는다. 좌표는 snapshot에 결속되지만 admission은
graph-local이며 O–H bond length, H–O–H angle, conformation이나 geometry quality를
판정하지 않는다.

이 exact H2O graph은 water, solvent 또는 hydration role이 아니다. SDF
positive의 canonical context는 `LIG/non_polymer`·`L/ligand`이므로 water entity
marker도 관찰되지 않는다. 기존 mmCIF `HOH`·`entity_type=water`
marker와 contextual-component inventory의 water role은 계속 unassessed로
남는다. 고정 corpus와 focused fail-closed tests는 atom order·bent/collinear coordinate admission, H 부족/초과,
wrong connectivity·peroxide·multiple bond, heteroatom·charge·isotope/map,
stereo·aromatic, wrong pedigree와 metadata/context tamper 경계를 추가한다.

성공 row에서도 generic chemistry와 generic/global preparation,
pH·protonation·autoionization, isotope speciation, water/solvent/hydration role,
geometry·bond length·angle·conformation, parameterability, force-field type·partial
charge·parameter, water model·constraint, box·PBC·periodicity, physics, runtime,
execution, energy·force, minimization, simulation과 claim은 모두 false 또는
unassessed다. 따라서 이 profile과 corpus는 V2-1 완료나 V2-4
solvent/PBC 적용 범위 확대를 의미하지 않는다.

선택 declaration envelope 밖 `CONECT`·모든 bond-kind/order·covalence·
coordination·chemistry 의미론·altloc·선택 single-model source-reported
profile 밖의 general missingness·비표현 `CRYST1`·symmetry/PBC 의미론을
포함한 general PDB,
exact common-core21·선택 explicit assembly·nonpoly identity·nonpoly component
topology·선택 nonpoly identity-symmetry covalent struct-conn topology·polymer sequence membership·
선택 polymer terminal/leaving annotation inventory·
선택 exact polymer-sequence+nonpoly component-topology composition·
source-reported unobserved-residue·unobserved-atom·zero-occupancy-residue·
zero-occupancy-atom envelope 밖 categories·auth/entity와
optional fields·altloc·선택 envelope 밖 assembly declaration/operator form·선택 atom envelope 밖 atom-level missingness·
선택 zero-occupancy envelope 밖 declaration/occupancy semantics·cell·
multimodel, 선택 topology profile 밖 `_chem_comp*`·`_struct_conn`,
general `disulf/hydrog/metalc/salt`·`quad/default order`·nonidentity symmetry·
polymer endpoint·inter-residue/cross-component link·coordination·metal·지원 밖 stereo·bond order를
포함한 general mmCIF, fragment role·salt·mixture chemistry·선택된
single simple non-aromatic 3–8-member 또는 fully-aromatic 5/6-member ring 범위 밖의 general rings·
선택 범위 밖의 일반 multiple-bond chemistry·aromaticity·일반 charge/charge assignment·isotope·
nonpositive/duplicate map·bounded tetrahedral R/S 밖 atom stereo·unknown bond
stereo·bounded profile 밖 E/Z·source H·선택 aromatic/tetrahedral 상태 밖
bracket H를 포함한 general SMILES,
일반 SDF coverage,
hydrogen·protonation·tautomer·
aromaticity 준비, contextual chemistry 해석과 일반 parameterability는 계속
차단되므로 V2-1을 완료로 표시하지 않는다.

선택 terminal/leaving annotation inventory의 source flag와 sequence boundary는
chemical terminus, leaving-atom transformation 또는 peptide-link materialization의
근거가 아니다. 해당 wrapper corpus가 통과해도 child system과 preparation·claim
권한은 바뀌지 않는다.

특히 위의 선택 exact composition은 polymer template·modified-residue chemistry,
reference 또는 coordinate completeness·missingness, `_struct_conn`, altloc,
assembly, cell, multimodel, generic/global preparation, parameterability, physics,
runtime 또는 claim gate를 승격하지 않는다. 이 미승격 항목과 general mmCIF
support는 composition corpus가 통과해도 계속 false다.

simple named SDF data-field envelope은 field 256개, field name 128자, field당
value line 64개, 전체 value line 2,048개, line 200자, data payload 384 KiB로
제한되며, 이 하위 상한은 전체 record 2 MiB·4,096 line·line 256자 상한 안에서
적용된다. field가 있으면 blank terminator와 `$$$$`가 필수이며 malformed·nested
header, registry/field-number 또는 suffix header, second record, non-ASCII/control
text, limit 초과는 typed failure로 닫힌다. raw full source·normalized
base-parser input·canonical base-writer output·canonical snapshot·topology·base
representable state·ordered field projection·output·reparse·
second emission digest를 factory-only receipt/report에 결속한다. 이는 기존의
명시적 SDF property-data-field 손실 하나를 좁게 줄이는 V2-1 evidence일 뿐,
arbitrary `M` property record·stereo·rich data header·multi-record·V3000·general
context 또는 chemistry/runtime support는 아니다.

고정 corpus는 no-field legacy parity·empty field·ordered duplicate 및 authority-like
field name·`M  CHG`/`M  ISO` 동시 보존을 포함한 5개 round-trip row와 malformed
header·terminator·delimiter·second-record·non-ASCII를 포함한 8개 failure row다.
manifest는 fixture, projection, combined record state, base snapshot/topology,
output, receipt와 report digest를 결속하며 resource-limit·stale/crosswire 경계는
focused generated test로 별도 고정한다.

### V2-2 — 독립 CPU 힘장과 최소화

주요 산출물:

- bond, angle, proper torsion, improper와 constraint schema
- vdW, short-range electrostatics와 초기 implicit-solvation 범위
- atom typing, charge·parameter provenance와 applicability domain
- 독립 parameter fitting·versioning pipeline
- deterministic steepest-descent/L-BFGS 계열 최소화와 checkpoint/restart
- 항별 energy·force·virial diagnostics

종료 기준:

- 단위와 translation·rotation·permutation invariance가 검증된다.
- analytic/autograd force가 finite difference와 사전 선언 tolerance에서 일치한다.
- supported chemistry의 parameter coverage가 사전 선언 기준을 충족한다.
- minimization이 정의된 조건에서 energy를 감소시키고 실패 원인을 기록한다.
- 외부 솔버 비교는 oracle-labelled evidence로만 저장한다.

현재 판단: 부분 진행. source-bound SDF V2000, explicit-H, 중립,
비동위원소, 비방향족 선형 알케인 C1–C4에 한해 `H=2*C+2`, carbon
simple path와 정확한 C/H degree를 직접 검사하는 적용성 계약이 있다.
그 위의 environment ID는 좌표가 아닌 인접 C/H 개수로만 만든 graph
match key이며 **force-field atom type이 아니다**. bond·angle·proper을
열거하고 모든 unordered atom pair를 최단 graph distance 1·2·3·4+로
`excluded_1_2`·`excluded_1_3`·`one_four_separate`·`full_nonbonded`에
나누지만, 이 topology/inventory report 자체는 interaction을 계산하지
않는다. selected improper와 constraint는
각각 명시적인 versioned empty policy이다.

| 범위 | 원자 | bond | angle | proper | 1–2 제외 | 1–3 제외 | 1–4 분리 | 4+ full | 전체 pair |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 methane | 5 | 4 | 6 | 0 | 4 | 6 | 0 | 0 | 10 |
| C2 ethane | 8 | 7 | 12 | 9 | 7 | 12 | 9 | 0 | 28 |
| C3 propane | 11 | 10 | 18 | 18 | 10 | 18 | 18 | 9 | 55 |
| C4 n-butane | 14 | 13 | 24 | 27 | 13 | 24 | 27 | 27 | 91 |

이 V2-2 계약의
[`independent_engine_v2_v2_2_linear_alkane_corpus.json`](../config/independent_engine_v2_v2_2_linear_alkane_corpus.json)은
동일한 digest-bound fixture byte를 일부 재사용하더라도 V2-1 ingest
corpus와 별도로 유지하며 C1–C4 positive/failure source·report hash와
비승격 gate를 고정한다. branched isobutane은 더 넓은 V2-1 acyclic
saturated H/C canonical-ingest-only profile에서는 positive이지만, V2-2
**linear**-alkane force-field profile에서는 계속 negative다. V2-1 선택 row는
V2-2 힘장 적용 범위를 넓히지 않는다. SHA-256은
결합과 tamper evidence일 뿐 인증·서명·license·과학 evidence가 아니다. source
partial charge가 있으면 적용 불가로 닫으며, formal charge 0 관찰을 partial
charge 할당으로 바꾸지 않는다.

이 topology 위에는 별도의
`betelgeuze.linear_alkane_c1_c4_parameter_protocol/1.0.0`,
`betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0`,
`betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0` 계약이 있다.
protocol은 C1–C4 positive corpus 합집합의 environment 6개, bond key 6개,
angle key 9개, proper key 7개를 정확히 고정하고 harmonic bond·angle,
periodic proper, LJ 12-6, Coulomb base form, exact pair override 우선과
Lorentz–Berthelot 결합, 독립적인 1–4 LJ/Coulomb scale 의미를 명시한다.
모든 수치는 IEEE-754 binary64 big-endian hex로 직렬화한다.

현재 parameter 값은 테스트에만 선언한 **비물리 contract fixture**다. source
charge나 formal charge를 복사하지 않고 environment별 명시적 charge lookup을
사용하며, 양·음의 nonzero dyadic charge가 methane·ethane·propane·n-butane에서
고정 environment 순서 `math.fsum`으로 각각 정확히 0이 됨을 검사한다. assignment
report는 canonical system과 parameter bytes를 함께 묶고 fresh applicability →
typing → inventory를 재실행한 뒤 atom FF type/charge/LJ row, 모든 bond·angle·proper
parameter, 모든 unordered pair를 매핑한다. 1–2·1–3 pair는 parameter를 매핑하지
않고, 1–4와 full pair는 endpoint charge/type을 보존한 채 override 또는
Lorentz–Berthelot 결과를 기록한다. 1–4 scale은 1–4 pair에만 존재한다.
C1·C2·C3·C4의 method-deferred nonexcluded mapping 수는 각각 0·9·27·54다.

이 assignment 위에는 별도
`betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/1.0.0`,
`betelgeuze.linear_alkane_c1_c4_evaluation_method/1.0.0`,
`betelgeuze.linear_alkane_c1_c4_evaluation_method_binding/1.0.0` 계약이 있다.
이는 테스트용 비물리 method 값으로 다음 범위만 닫는다.

- 원자 수 `N≤14`, 전체 unordered pair 최대 91개, 평가 대상 nonexcluded pair
  최대 54개, 단일 coordinate model, cell-free·nonperiodic, CPU `torch.float64`,
  `requires_grad=false`
- assignment의 canonical pair row만 직접 순회하고 1–2·1–3을 생략하며,
  1–4에만 LJ/Coulomb scale을 적용하고 full pair는 scale 없이 사용
- cutoff·switch·spatial neighbor·dense `N×N`·minimum image·reciprocal·long-range
  correction·dispersion tail을 모두 사용하지 않는 direct-uncut tiny reference
- Coulomb을 binary64 순서 `(k_e/epsilon_r) → *q_i → *q_j → /r`로 고정하고,
  fixture의 `k_e=1.0`, `epsilon_r=1.0`은 과학 상수가 아님을 명시
- bond → angle → proper → selected pair 순서, proper component와 pair 내부
  LJ/Coulomb의 고정 `math.fsum`, round-to-nearest-ties-to-even, mixed precision·
  fast math·FMA contraction 금지. cross-platform libm bit replay는 미평가

binding report는 canonical system·parameter·method bytes를 각각 해시로 묶고,
system serializer가 원래 device를 CPU로 정규화하기 전에 dtype·device·shape·cell·
layout·`requires_grad` 실행-envelope를 별도로 관찰·결속한다. 매 접근마다 세
artifact를 strict round-trip하고 applicability → typing → inventory → assignment를
fresh 재계산한다. C1의 nonexcluded pair가 0개인 경우에도 전체 10개 pair
identity가 정확히 존재해야만 empty subset coverage를 인정한다. 그 뒤 bond 거리,
angle leg/sine, proper bond/normal, selected-pair 거리의 비특이 domain만 검사하고
binding report 자체에서는 어떤 interaction 값도 계산하지 않는다.

원본 n-butane corpus 좌표에는 H–C–H 하나가 정확히 180°라 method binding이
`method_incompatible`으로 닫힌다. 별도의 C4 계약 테스트는 동일 source-bound
identity를 가진 test-only 파생 좌표에서 한 수소만 exact dyadic 0.125 Å
이동해 91개 전체 pair와 54개 nonexcluded pair binding을 검증한다. 이는
실패를 완화한 것이 아니라 좌표-domain 검사와 C4 method 범위를 각각 증명한
것이다.

따라서 `bounded_contract_fixture_potential_method_defined=true`와
`bounded_contract_fixture_method_assignment_binding_complete=true`는 오직 이
비물리 `N≤14` method/binding 계약의 좁은 증거다. binding report에는
energy·force·virial 또는 per-term 수치 필드가 없고, 바인딩된 method artifact의
`energy_kernel_status="missing"`와 engine dispatch 미등록 상태도 바뀌지 않는다.

이 비실행 binding 다음에는 별도의
`betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic_protocol/1.0.0`과
`betelgeuze.linear_alkane_c1_c4_scalar_energy_diagnostic/1.0.0`이 있다. 이
evaluator는 method가 아니라 diagnostic schema가 소유하는 비물리 수치
진단이다. 입력은 정확한
`LinearAlkaneC1C4EvaluationMethodBindingReport` 하나만 받고 raw system·
parameter·method API는 거부한다. 각 public analysis는 binding의 canonical
system·parameter·method·assignment·input-envelope·report snapshot을 묶은
동일 immutable replay capsule 하나만 사용하고 live tensor를 다시 읽지
않는다.

수치 순서는 아래처럼 literal CPU binary64로 고정된다.

- bond·angle은 `(0.5*k*delta)*delta`를 사용하고, angle은 normalized
  singularity 검사 후 raw cross norm과 raw dot의 `atan2`를 쓴다.
- proper는 literal signed cross/dot `atan2`와
  `amplitude*(1+cos(n*phi-phase))`를 사용하며 component를 `math.fsum`한다.
- LJ는 `sigma/r → s2 → s4 → s6 → s12`와
  `(4*epsilon)*(s12-s6)` 순서를 쓴다. Coulomb은 한 평가당
  `(k_e/epsilon_r) → *q_i → *q_j → /r`순서를 쓴다.
- 1–4 scale은 base LJ/Coulomb에 각각 한 번만 적용하고 full pair는
  scale 곱셈 없이 LJ/Coulomb을 `math.fsum`한다.
- 최종 total은 bond → angle → proper → selected pair의 평탄한 canonical
  term sequence를 한 번 `math.fsum`한 값이다. class·LJ·Coulomb subtotal은
  보고용이며 total 입력으로 재합산하지 않는다.

테스트용 fixture의 C1–C4 평가 개수와 에너지 binary64 golden은 다음과
같다. C4는 위에서 정의한 exact-0.125 Å test-only 파생 좌표를 쓴다.
수치는 kJ/mol 표현의 hexadecimal encoding이며 과학 reference가 아니다.

| 범위 | 평가 B/A/P/pair | Bond | Angle | Proper | Selected pair | Applied LJ | Applied Coulomb | Flat total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 methane | 4/6/0/0 | `3ff9b589b5b18f2f` | `3fe80c7fa29664b5` | `0000000000000000` | `0000000000000000` | `0000000000000000` | `0000000000000000` | `4002dde4c37e60c5` |
| C2 ethane | 7/12/9/9 | `402c83072057e042` | `401138567aa253d8` | `402b00000f407602` | `3ff1db3b331b547c` | `3ff1b25deaa00700` | `3f846ea43da6be1e` | `404096a674d33ab0` |
| C3 propane | 10/18/18/27 | `4038debb80e2523f` | `40417da3afe515f8` | `403f11f3df977c69` | `bfcddd79234d656d` | `bfcead966d48c5dd` | `3f7a03a93f6c0e02` | `4056ac0ef37f57f3` |
| C4 derived n-butane | 13/24/27/54 | `404208fc6f52f5ff` | `405a8bb2829a5632` | `40490af7220cdfe4` | `40a5e286778d609b` | `40a5e2818bd1267f` | `3f83aef0e8705d5a` | `40a76333d9e7b2a4` |

protocol SHA-256은
`d749376664b1624ba53257378ef1e7c052e7a784a4e36393fa5874a007ad8f11`이다.
C1 canonical report는 5,590 byte이고 serialized SHA-256은
`3ba0b3dd03e41862512cf3843dcf023e6608aec4645d7b710cac970de88be825`이다.
term row는 compact serialized report에서 제외하지만 evaluation·canonical-sequence
digest에 묶는다.

upstream binding status가 `invalid_system`·`unsupported_system`·
`method_incompatible`이면 평가 개수는 모두 0, 에너지는 모두 null,
term tuple은 모두 없는 비평가 진단 report를 낸다. snapshot tamper·불일치,
표현 불가능 좌표 연산, nonfinite 연산은 partial result 없이 typed failure로
닫힌다. C1은 전체 10개 pair inventory를 검증한 후에만 selected-pair 빈
집합을 성공적인 positive zero로 보고한다.

성공 평가 전후에는 binary64 tie-sensitive rounding-mode 검사를 실행한다.
ambient rounding이 upward·downward·toward-zero이면 고정 total을 조용히
바꾸지 않고 typed failure로 닫힌다.

`bounded_nonphysical_diagnostic_scalar_evaluator_complete=true`와
`bounded_nonphysical_diagnostic_scalar_energy_evaluated=true`는 오직 이 계약
진단의 성공을 뜻한다. 이 진단 report 자체의 method-owned/runtime energy
kernel, force, virial, gradient/autograd, minimization, engine dispatch,
production method/assignment, parameterability·과학 검증·physics·runtime·
실행·simulation·claim gate는 모두 false다. direct all-pair 순회는 scaling
evidence가 아니고 digest와 input observation은 binding일 뿐 인증이나 과학
provenance가 아니다.

그 다음 로컬 실행 경계로 별도
`betelgeuze.linear_alkane_c1_c4_method_kernel_protocol/1.0.0`과
`betelgeuze.linear_alkane_c1_c4_reference_kernel_result/1.0.0`을 둔다. 이는
v1 method를 수정한 것이 아니라 overlay protocol이다. 따라서 v1 method의
`energy_kernel_status="missing"`와 force/virial 미정의 상태, 기존 binding과
scalar diagnostic의 bytes·SHA는 그대로 유지하면서 overlay만
`available_bounded_nonphysical`을 소유한다.

`compile_linear_alkane_c1_c4_reference_potential(binding)`은 정확한 성공
binding report 하나만 받아 immutable replay를 검증하고, resolved assignment의
수치 row만 tuple 기반 plan으로 고정한다. raw system·parameter·method API와
`method_incompatible` binding은 거부한다. compiled potential은 chemistry를
다시 만들지 않고 CPU `torch.float64 [N,3]`, `requires_grad=false`, finite,
동일 atom count인 좌표를 반복 평가할 수 있다. 매 호출은 입력 tensor alias를
끊은 뒤 좌표 hash와 geometry threshold를 새로 검사한다.

energy는 scalar diagnostic과 독립 구현으로 동일한 bond·angle·signed proper·
LJ·Coulomb·1–4·flat `math.fsum` 순서를 쓴다. force는 동일 forward
intermediate의 local reverse-mode VJP로 `F=-dE/dr`을 계산한다. 1–4 LJ와
Coulomb derivative에도 scale을 각각 정확히 한 번만 적용하고 full pair에는
적용하지 않는다. term별 canonical identity·parameter ID·energy·local force와
virial, class별 bond·angle·proper·LJ·Coulomb subtotal, 전체 atom force를 함께
기록한다.

cell-free nonperiodic virial은 아래로 고정한다.

```text
W[a,b] = sum_terms sum_local_atoms F[a] * (r[b] - r_anchor[b])
       = -dE/d epsilon[a,b],  r' = r @ (I + epsilon).T
```

index는 force axis `a`, coordinate axis `b` 순서다. bond·proper·pair anchor는
canonical atom-j, angle anchor는 center atom이고, total은 class subtotal이 아닌
flat term virial을 성분별 `math.fsum`한다. pressure·stress·volume·cell·PBC
virial 의미는 정의하지 않는다.

class energy·force·virial은 보고용 decomposition이다. selected pair는 flat
total 전에 LJ/Coulomb을 먼저 결합하지만 class report는 둘을 따로 누적하므로,
class 재합산은 선언한 binary64 tolerance에서 비교하며 bitwise 동일성을
계약하지 않는다.

protocol은 5,519 byte, SHA-256은
`c402308fbec145137a69917102c8539c224e6393567dc30fcc64496724359cad`다.
C1 compiled-plan SHA-256은
`e1107d0182ccc50e0bcc301d72d3f73cd143b06bc06fd7a47568ff26f7c55f62`,
14,655-byte result의 serialized SHA-256은
`9d72ddf1b55b7f029a6cac5349576373e6f71621a201460d8fa80bfd80799d50`다.
C1–C4 energy는 기존 scalar diagnostic과 binary64까지 일치하며, 모든 좌표
central FD, 독립 Torch autograd, 9개 affine virial FD, translation·rotation·
atom-reindexing equivariance, net force·torque, class decomposition, repeated
coordinate evaluation,
override·1–4·full pair와 fail-closed interface를 검증한다.

이 결과로 true가 되는 것은 bounded nonphysical method-owned reference
energy·force·virial kernel뿐이다. parameter는 여전히 비물리 fixture이고
production runtime kernel·evaluation method·physics·scientific validation·
engine dispatch·minimization·simulation·claim gate는 모두 false다. licensed
dataset fitting·provenance, force-energy reference validation, cutoff·switch·
PBC·long-range와 pressure virial을 포함한 production method, minimizer와
release attestation은 계속 blocker다.

실제 과학 참조 증거의 첫 bounded slice로 SPICE 2.0.1 (DOI
`10.5281/zenodo.10975225`)의 QCArchive singlepoint dataset 340,
`SPICE DES Monomers Single Points Dataset v1.1`, `spec_4`에서 methane,
ethane, propane, n-butane 각 50개씩 총 200개 complete record를 exact
artifact로 수용했다. Psi4 1.4.1 `wb97m-d3bj/def2-tzvppd` provenance와 release의
float32 coordinate·float32 total gradient, float64 total energy를 보존한다.
gradient는 `dE/dr`이며 force가 아니고, 이 slice는 `force=-gradient` 변환을
수행하지 않는다.

source 생성기의 `(i, i+25)` high/nearby-low conformation pair를 분리하지
않도록 group·pair ID의 domain-separated SHA-256 순서로 graph마다
15/5/5 pair, 즉 30/10/10 record를 fit/selection/holdout에 배치한다. 전역
record 수는 120/40/40, pair 수는 60/20/20이며 exact record·geometry·
QCArchive molecule ID·source-pair overlap은 모두 0이다. 그러나 세 partition은
같은 네 molecular graph와 같은 release/time provenance를 공유한다. 따라서
허용되는 claim은 `within_same_four_graphs_unseen_conformations_only`뿐이고,
graph·family·time·release-disjoint 또는 generic validation split이 아니다.

이는 observation inventory이지 parameter fitting이나 force-field validation이
아니다. 서로 다른 molecule의 absolute total energy는 공통 offset으로 직접 fit하지
않으며, 향후에는 molecule별 relative energy 또는 nuisance intercept protocol이
필요하다. isolated monomer energy·gradient만으로 transferable partial charge,
LJ 또는 1–4 parameter를 식별할 수 없다. upstream은 CC0를 선언하지만 human
license review와 whole-file authentication은 아직 pending이다. candidate fit,
parameter set, parameterability, reference validation, production parameter,
physics·runtime·execution·claim gate는 모두 false다.

이 pending 상태를 사람이 검토할 수 있는 입력으로 바꾸기 위해 별도의
`betelgeuze.spice_c1_c4_source_authentication_license_review_packet/1.0.0`
패킷을 둔다. 이 패킷은 기존 251,253-byte evidence를 수정하지 않고 그 exact
artifact/core SHA-256에 결속한다. 2026-07-15에 관찰한 Zenodo version record
10975225 revision 10과 단일 HDF5 file ID·37,479,271,148-byte 크기·공식 MD5,
GitHub release 2.0.1의 lightweight tag→commit, tag-pinned README와 LICENSE의
blob/byte/SHA-256을 canonical snapshot으로 분리해 보존한다. Zenodo와 README의
dataset CC0 선언은 저장소 code/documentation의 MIT LICENSE와 같은 범위가 아니며,
scope 해석은 사람의 검토 전까지 pending이다.

이 패킷은 인증서나 법적 승인서가 아니다. 37.5 GB 전체 파일을 local stream으로
읽은 byte-count/official-MD5/local-SHA-256 receipt, admitted C1–C4 array가 그
whole file에서 어떤 HDF5 path·dtype·shape·selection/order로 추출됐는지를 다시
결속하는 receipt, 그리고 그 receipt에 atomic number·mapped identity·connectivity
derivation·record/index mapping을 명시적으로 연결하는 요구, reviewer
decision/attestation은 모두 비어 있고 관련 gate는
false다. GitHub verified commit에는 HDF5 digest가 없고 tag 자체도 서명되지
않았으므로 publisher-signed dataset digest로 해석하지 않는다. 공식 MD5를 향후
로컬에서 일치시켜도 whole-file byte integrity evidence일 뿐 강한 publisher
identity authentication과는 별도다. CI·wheel·runtime은 원본 HDF5를 fetch하거나
hash하지 않고 패킷과 기존 evidence bytes만 offline replay한다.

이 exact source bytes만을 다시 strict replay하는 별도 target-view
계약에서 graph당 25개의 source pair를
`E(entry suffix p) - E(entry suffix p+25)`로 변환해 100개
pair-relative energy target을 만들고, 200개 record의 float32
gradient 스칼라 부호 비트를 정확히 반전해 `F=-dE/dr`인
5,700개 force scalar target을 만든다. pair 역할은 오직 numeric
QCArchive suffix로 결정하며 energy 정렬·절댓값을 사용하지 않는다.
`p+25`는 source 생성기의 nearby-lower member일 뿐 QM minimum이나
torsion-scan endpoint가 아니다. 2022 CODATA central value를 versioned
rational 관례로 고정하고 각 output을 binary64로 한 번만 반올림하며,
이는 측정된 물리상수가 exact라는 주장이 아니다.

target view는 60/20/20 energy pair와 120/40/40 force record로 기존
pair-atomic split을 그대로 보존한다. source·topology·row·protocol·derived
hash와 raw net-force/coordinate-centroid torque 잔차를 결속하지만 force
projection·centering·clipping·denoising은 수행하지 않는다. 별도 target
JSON을 commit하지 않고 외부 evidence에서 on demand로 재생성한다.
공개 holdout은 사람에게 blind가 아니고 세 partition이 같은 네 graph·
release·time provenance를 공유하므로 허용 claim은 여전히
`within_same_four_graphs_unseen_conformations_only`다. 이 변환은 loss,
fit, parameter identifiability, candidate parameter, scientific validation,
production physics·runtime·execution·claim gate를 승격하지 않는다.

그 downstream의 별도 fit-only bonded-basis observability 계약은 exact source
bytes와 target view를 다시 replay하고, atomic number·connectivity만으로 네 graph의
6 bond·9 angle·7 proper environment key를 재구성한다. 이 key는 frozen C1--C4
좌표에서 feature를 묶는 진단 label일 뿐 FF atom type·parameter ID·transferable
chemistry typing이 아니다. primary basis는 bond별 `0.5*r^2`, `-r`, angle별
`0.5*theta^2`, `-theta`, proper별 parity-even `cos(n*phi), n=1..3`의 51열로
사전 고정한다. sine 포함 또는 `n=1..6`까지 확장한 세 family도 함께 계산하지만
이는 target residual을 보지 않는 비선택 misspecification/allowed-family 감사이며
candidate model이 아니다.

오직 fit 60 pair만 사용해 pair당 `Phi(seed)-Phi(related)` energy 1행과 두
record의 atom-major `-dPhi/dR` force 행을 만들므로 전체 design은 energy 60행,
force 3,420행이다. fit target만으로 고정한 graph-balanced·energy/force-balanced
RMS loss scale과 fit-only column L2 normalization을 적용한 뒤 binary64 SVD의
rank·nullity·condition을 보고한다. selection·holdout은 basis·scale·rank·threshold에
사용하지 않고, SVD bit pattern도 cross-platform 계약으로 고정하지 않는다.

네 사전고정 variant가 frozen fit 좌표에서 full column rank인 결과는 해당 design
direction을 수치적으로 구분한다는 좁은 조건부 observability일 뿐이다. coefficient,
prediction, residual fit, candidate parameter와 별도 committed report artifact는
만들지 않는다. SPICE total energy·gradient에는 electrostatics·dispersion·1–4·
polarization·coupling이 함께 있으므로 bonded/physical parameter identifiability,
family sufficiency, transferability, reference validation, parameterability,
production physics·runtime·execution·claim gate는 모두 false다.

별도의 metadata-decided
`betelgeuze.spice_graph_family_disjoint_population_preflight/1.0.0`은 source와
review packet을 strict replay하고 current partition의 graph overlap 4·family
overlap 1, graph/family/time/release-disjoint false와 public-blind false를 고정한다.
strict integrity replay는 이미 동결된 target payload를 decode·검증하지만,
population·family·split 결정은 topology와 partition metadata만 소비하고 target
값으로 분기하지 않는다. 그 prospective protocol은
release→family→parent/scaffold→exact graph→related-conformer/cluster→record 계층,
whole-graph/whole-family split unit, metric·threshold·candidate 순서를 고정하지만
expanded row나 split manifest 자체를 만들지는 않는다. uncertainty의 outer
resampling unit은 graph 또는 family이고 source-pair block은 graph 내부에만
nested된다.

v1 exact graph identity는 isotope와 stereo가 모두 `explicitly_absent`인 bounded
C/H tree에만 적용된다. atomic number·bond order·molecular charge·multiplicity와
SHA-256 domain·rooted-tree encoding·canonical JSON recipe·C1–C4 graph digest·
topology receipt를 protocol에 결합한다. isotope 또는 stereo가 present이면
atom-level isotope label과 stereo descriptor를 담는 새 identity schema가 생길
때까지 fail closed한다.

graph-disjoint evidence를 단순히 C5+ holdout으로 덧붙일 수도 없다. 현재 C1–C4
합집합은 6 bond·9 angle·7 proper key인데 C5는 새로운 all-interior angle 1개와
proper 2개, C6는 추가 all-interior proper 1개를 요구한다. 따라서 C5/C6는 기존
C1–C4 parameter key universe의 in-domain accuracy holdout이 아니라 versioned
coverage expansion 또는 OOD다. 새 applicability·key·fit-only basis·observability
계약에서 C1–C6 coverage를 먼저 확립한 뒤에야 C7+의 whole graph를 같은
linear-alkane family 안 graph-disjoint selection/holdout 후보로 쓸 수 있다.
branched/cyclic/unsaturated family는 별도 applicability·coverage 계약 전까지
accuracy가 아니라 abstention/OOD evidence로만 취급한다. 공개 graph/family set은
사람에게 blind하지 않으며, 진짜 sealed blind evidence와 별도 lane이어야 한다.

별도로 exact methane의 네 C-H bond·여섯 H-C-H angle에 한해 1.0 legacy
파라미터 계약과 동일 바이트를 유지하면서, 1.1은 고정 harmonic
functional form을 payload에 결합한다. 합성 비물리 fixture의 exact-arithmetic fit,
버전별 protocol/receipt/bundle 결합, 비실행 analytic-force 진단과 1.1 form-bound
비주기 bonded virial 진단과 bounded raw-force Armijo descent 진단은 계약
검증용으로 존재한다. virial 진단은 9개 affine-strain 성분과 trace를 검사하지만
pressure·stress·volume·periodic·nonbonded virial은 정의하지 않는다. descent는
strict energy 감소, bounded line search, 명시적 stagnation/failure, accepted-step
transcript, canonical checkpoint의 prefix full replay와 검증된 current state에서의
suffix 재개를 같은 CPU 수학 runtime 안에서 검사한다. 파생 좌표 provenance는
입력 상태와 무관하게 preparation·claim 권한을 false로 내린다. 이는 비물리
first-order 수치 진단이지 minimum 증명이나 runtime minimizer가 아니다.
과학적으로 fitting·검증된 FF atom type·partial charge·bonded/LJ parameter,
improper·constraint coverage, 완전한 nonbonded evaluation method, 과학 reference,
전체 parameter coverage, cross-platform replay와 과학적으로 검증된 production
최소화가 없으므로 production energy·force·virial·minimization runtime 및 모든
과학·제품 gate는 계속 false다.

### V2-3 — 독립 구조분석·도킹·scoring

구조분석 산출물:

- 원자 충돌, 결합 geometry, Ramachandran·rotamer 등 정확한 정의의 quality metric
- pocket geometry·physicochemical profile과 ligandability evidence
- protein–protein·protein–ligand interface와 interaction network
- mutation 전후 local environment·stability·interaction 변화와 uncertainty
- 구조 정렬, RMSD 계열, contact·secondary-structure metric의 검증된 구현

도킹 산출물:

- ligand conformer와 rotatable-bond tree
- torsion-aware global search와 gradient local refinement
- diverse top-k, symmetry-aware clustering과 pose validity
- constraints, flexible side chain, ensemble receptor 정책
- water·metal·cofactor interaction policy
- 독립 physics score와 제한된 AI residual score

종료 기준:

- pose validity, recovery, ranking을 사전 고정한 public holdout protocol로 실행한다.
- aggregate 점수뿐 아니라 모든 row와 실패 row를 보존한다.
- 구조분석 metric을 공식 정의 또는 독립 reference implementation과 교차 검증한다.
- uncertainty와 failure domain을 결과에 포함한다.
- 임계치를 정한 후 benchmark를 실행하고 결과를 본 뒤 기준을 바꾸지 않는다.

### V2-4 — PBC·장거리 물리·용매·MD

주요 산출물:

- differentiable periodic image-shift를 energy·force 경로 끝까지 전달
- topology-aware explicit water·ion과 box preparation
- validated PME `O(N log N)` 또는 조건이 명시된 FMM
- SHAKE/RATTLE 계열 bounded constraint solver 또는 독립 대안
- NVE, NVT, NPT integrator와 thermostat·barostat
- trajectory, checkpoint/restart, seed와 environment provenance
- drift, temperature, pressure, density, distribution diagnostics

종료 기준:

- unit-cell 경계를 통과하는 energy·force finite-difference test가 통과한다.
- NVE energy drift와 momentum behavior가 사전 선언 기준을 충족한다.
- NVT temperature, NPT pressure·density 분포와 restart 일관성을 검증한다.
- long-range method와 실제 복잡도를 결과에 정확히 기록한다.
- 직접 Coulomb all-pairs는 tiny reference test 밖에서 금지한다.

### V2-5 — Production AI와 물리 결합

주요 산출물:

- license·source·split provenance가 있는 energy·force·pose dataset
- physics residual-energy SE(3) model과 parity·chirality channel
- `TorsionTopologyGNN` 기반 pose refinement
- `TemporalStateGNN` 기반 fixed-window short-rollout correction
- PINN objective와 science release gate
- ensemble uncertainty, calibration, OOD·chemistry abstention
- signed model card, runtime schema와 production checkpoint

종료 기준:

- protein family, ligand scaffold, target와 time leakage를 통제한 split을 고정한다.
- physics-only baseline 대비 AI의 개선과 실패를 모두 보고한다.
- energy, torsion, temporal, PINN, projection 요소별 ablation을 수행한다.
- equivariance, chirality, exact gradient와 long-rollout stability를 검증한다.
- calibration과 OOD 기준을 통과하지 못하면 AI capability를 비활성화한다.
- checkpoint의 code·feature·neighbor·parameter schema가 runtime과 완전히 일치한다.

### V2-6 — ROCm/HIP 가속

주요 산출물:

- cell-list, sparse message, force, projection, constraint, integrator HIP kernel
- frozen CPU golden reference와 kernel별 parity harness
- compact memory pool, zero-copy/SoA lifetime 계약과 overflow diagnostics
- deterministic mode와 high-throughput mode의 분리
- 로컬 AMD 설치·진단·fallback package

종료 기준:

- 실제 AMD GPU에서 CPU/ROCm energy, force, gradient와 docking ranking이 일치한다.
- capacity overflow와 fail-closed 동작도 CPU와 동일하다.
- determinism, peak memory, scaling과 장시간 soak evidence를 확보한다.
- 정확도 저하가 있는 mixed precision은 별도 capability로 표시한다.
- GPU가 없는 현재 모바일 환경에서는 이 단계의 gate를 닫지 않는다.

### V2-7 — 독립 상용 로컬 제품

주요 산출물:

- clean-machine installer와 완전한 offline execution bundle
- protein·ligand preparation wizard와 3D viewer
- structure analysis, docking, minimization, MD workflow와 job queue
- 중단·재시작, checkpoint, rollback, crash recovery와 resource limits
- 결과 table·3D pose·trajectory·uncertainty·provenance report
- tenant·path·secret 격리, signed manifest와 audit ledger
- capability별 enable/disable, license와 version migration 정책

종료 기준:

- clean installation, upgrade·rollback과 장시간 작업 복구가 통과한다.
- 데이터 격리, 악성 입력, path traversal과 resource-exhaustion test를 통과한다.
- blind customer-shadow 평가와 operator acceptance가 승인된다.
- 지원 chemistry·정확도·실패 범위를 UI와 보고서에서 명확히 알린다.
- 과학·benchmark·GPU·제품 gate를 모두 통과한 capability만 고객에게 활성화한다.

## 8. 병렬 capability lane과 의존관계

| Lane | 주요 범위 | 시작 가능 시점 | 다른 lane에 제공하는 계약 |
| --- | --- | --- | --- |
| Molecular | parser, preparation, canonical topology, chemistry coverage | V2-0 이후 즉시 | 모든 physics·AI·docking 입력의 identity |
| Physics | force field, minimizer, PBC, solvent, MD | V2-1 schema 안정 후 | AI baseline과 docking refinement energy |
| Structure | quality, pocket, interface, mutation, exact metrics | V2-1 parser와 함께 | 제품의 초기 독립 분석 capability |
| Docking | conformer, global search, local refinement, scoring | V2-2 energy 안정 후 | pose·ranking·interaction results |
| AI | residual energy, torsion, temporal, PINN, uncertainty | V2-2 reference와 dataset 후 | 제한된 정확도·효율 개선 |
| Runtime | Rust/HIP kernels, memory, determinism | CPU algorithm freeze 후 | 동일 science의 가속 실행 |
| Validation | corpus, oracle comparison, public holdout, evidence | 모든 단계와 병행 | capability 승격 결정 |
| Product | UI/API, jobs, reports, security, installer | contracts부터 병행 | 통과 capability의 안전한 전달 |

AI 학습과 GPU 최적화는 독립 CPU 물리 기준선보다 앞서지 않는다. CPU 결과가
계속 변하는 상태에서 GPU parity를 맞추거나, 불안정한 proxy force를 대규모로
학습시키면 검증 비용만 증가한다.

## 9. 검증과 승격 게이트

모든 capability는 서로 독립적인 다음 게이트를 통과해야 한다.

1. **계약 게이트:** schema, unit, atom identity, provenance, canonical hash,
   fail-closed.
2. **수학 게이트:** sparse bound, invariance·equivariance, parity,
   finite-difference force, projection adjoint.
3. **과학 게이트:** parameter coverage, conservation, ensemble, pose validity,
   structure metric, uncertainty.
4. **Benchmark 게이트:** 고정 public holdout, row-level evidence, failure row,
   baseline과 confidence interval.
5. **GPU 게이트:** 실제 CPU/ROCm value·gradient·ranking·memory·scaling parity.
6. **제품 게이트:** 설치, 복구, 보안, 보고서, 지원범위 표시와 customer shadow.

모든 release evidence에는 최소한 다음 정보를 포함한다.

- 원본 입력과 결과 SHA-256
- 실행 명령, random seed, Git commit와 software environment
- dataset·split·parameter·baseline·checkpoint version
- aggregate뿐 아니라 개별 결과 row와 실패 row
- benchmark 실행 전에 고정한 threshold
- uncertainty, confidence interval과 적용범위
- 자동 gate 결과와 최종 사람 승인 기록

## 10. 제품 성숙도 단계

| 제품 상태 | 진입 조건 | 외부 제공 정책 |
| --- | --- | --- |
| Scaffold | contract·unit test만 존재 | 개발자 내부 참고만 허용 |
| Internal alpha | capability의 수학 gate 통과 | 내부 synthetic·curated 입력만 허용 |
| Scientific beta | 과학 gate와 고정 benchmark evidence 통과 | 제한된 평가자에게 claim 범위를 명시해 제공 |
| Customer shadow | 실제 고객 입력을 결과 의사결정 없이 병렬 평가 | 결과는 검토용이며 자동 업무 사용 금지 |
| Release candidate | 보안·설치·복구·성능 gate까지 통과 | 명시된 chemistry·hardware 범위에서 pilot 허용 |
| Commercial release | capability별 승인과 운영 책임자 sign-off | 승인 capability만 제품 UI/API에서 활성화 |

하나의 기능이 commercial release라고 해서 전체 플랫폼이 자동으로 상용
승격되는 것은 아니다. 예를 들어 구조 품질 분석은 출시 가능하지만 FEP는
계속 차단된 상태가 될 수 있다.

## 11. 데이터·모델·파라미터 관리

- 원시 dataset, split manifest, parameter와 model checkpoint를 서로 다른
  versioned artifact로 관리한다.
- protein family, sequence identity, ligand scaffold, target, assay와 시간
  leakage를 가능한 범위에서 모두 통제한다.
- dataset license와 고객 데이터 사용 권한을 artifact에 기록한다.
- failure와 rejected chemistry를 삭제하지 않고 applicability evidence로 남긴다.
- model은 code commit, feature schema, neighbor schema, parameter version,
  dtype와 device policy를 함께 fingerprint한다.
- partial·shape/type/dtype mismatch, NaN/Inf 또는 legacy semantics checkpoint는
  production에서 fail-closed 처리한다.
- benchmark를 본 뒤 test split, threshold 또는 metric 정의를 변경하면 새
  protocol version과 독립된 재평가가 필요하다.

## 12. 핵심 위험과 대응

| 위험 | 잘못된 결과 | 대응 원칙 |
| --- | --- | --- |
| 조건부 `O(N)`을 무조건적 성능으로 표현 | 실제 density·candidate·long-range 비용 은폐 | hard cap, overflow row, scaling·memory evidence와 범위별 복잡도 표기 |
| parser의 조용한 chemistry 손실 | 잘못된 원자·전하·stereo로 전체 계산 오염 | canonical round-trip과 failure corpus, generic fallback 금지 |
| heuristic force field의 조기 제품 승격 | 그럴듯하지만 과학적으로 무의미한 energy·force | parameter coverage와 finite-difference·conservation gate 선행 |
| 학습 데이터 leakage | 공개 benchmark 성능 과대평가 | family·scaffold·target·time split와 immutable manifest |
| PBC image-shift gradient 오류 | 경계 통과 시 energy·force 불연속 | differentiable image shift와 boundary finite-difference test |
| 금속·cofactor·protonation 미지원 | 실제 표적에서 잘못된 pose·score | chemistry별 capability와 abstention, 단계적 coverage 확장 |
| AI direct-force drift | MD 장시간 불안정과 비보존력 | scalar residual energy와 exact VJP, rollout gate |
| CPU와 HIP kernel 불일치 | GPU에서만 ranking·trajectory 변화 | frozen CPU oracle와 kernel별 value·gradient parity |
| proxy metric의 공식 명칭 사용 | 고객이 정확도를 오해 | 정확한 정의 구현 또는 proxy 이름·claim 완전 분리 |
| 단독 개발 범위 과대화 | 모든 기능이 미완성 상태로 장기 정체 | critical path와 capability별 독립 출시, gate 미통과 기능 비활성화 |

## 13. 권장 critical path

개발을 재개할 때의 우선순위는 다음과 같다.

1. V2-0 contract와 CPU 결과를 안정화하고 불필요한 legacy import를 늘리지 않는다.
2. V2-1 parser·preparation과 supported-chemistry 표를 먼저 완성한다.
3. V2-2의 bounded C1–C4 topology·비물리 full-assignment·direct-uncut method
   binding·schema-owned scalar-energy 진단과 별도 bounded nonphysical
   method-kernel energy·force·nonperiodic-virial reference 계약 및 source-declared
   CC0 SPICE 2.0.1 C1–C4 observation inventory와 source-bound
   pair-relative-energy/negative-gradient target view와 현재 fit-only
   basis·loss·conditional-observability 및 nonidentifiability 경계 계약 다음으로,
   machine-prefilled source/license review 패킷의 남은 사람 license/legal 결정,
   whole-file local-stream·subset-extraction receipt와 필요한 strong publisher
   authentication을 닫는다. 그 뒤 target을 보기 전에 population taxonomy와
   graph/family 계층 split을 동결하고 graph-disjoint in-family validation,
   family-disjoint OOD/abstention, 외부 sealed blind evidence를 서로 분리한
   scientific protocol에서 실제
   type·charge·bonded/LJ parameter를 fitting·검증하고
   method-owned production energy·force·virial kernel 및 cutoff·switch·Coulomb·
   1–4·PBC 경계를 포함한 작은 production chemistry 범위를 정확하게 닫는다.
4. 정확한 structure-quality·pocket 분석을 초기 독립 capability로 만든다.
5. 안정된 energy·gradient 위에서 torsion-aware docking을 구현한다.
6. PBC·long-range·solvent·integrator를 닫아 MD capability를 분리 승격한다.
7. 충분한 reference data와 physics baseline을 확보한 뒤 production AI를 학습한다.
8. CPU algorithm·tolerance를 freeze한 다음 실제 로컬 AMD GPU에서 HIP parity를
   검증한다.
9. 마지막에 통과 capability만 제품 route와 UI에서 활성화한다.

GPU 없이 진행 가능한 단계는 V2-1, V2-2 CPU reference의 대부분, V2-3의
알고리즘·작은 benchmark, V2-4 CPU 정확성, V2-5 dataset·loss·CPU 검증,
문서·보안·제품 계약이다. 실제 ROCm 성능·메모리·determinism·soak와 GPU
제품 gate는 로컬 AMD 환경에서 별도로 닫아야 한다.

## 14. 장기 확장 항목

다음 항목은 핵심 V2 상용화 critical path를 닫은 뒤 별도 capability로 다룬다.

- sampled lambda ensemble 기반 독립 FEP와 BAR/MBAR
- protein conformational ensemble와 enhanced sampling
- de novo protein structure prediction 또는 sequence design
- covalent docking, metalloprotein, membrane protein 전용 chemistry
- wet-lab active learning과 자동 실험 설계
- multi-GPU·distributed execution

이 기능은 이름만 먼저 제품에 노출하지 않는다. 각 기능에 별도의 데이터,
과학, benchmark, GPU와 제품 gate가 필요하다.

MM/GBSA, FEP, `Delta G`, wet-lab hit, de novo structure prediction 또는
AlphaFold·Schrodinger·OpenMM 계열과의 parity는 non-empty blind row, 실패 row,
고정 protocol과 confidence interval이 확보되기 전까지 claim하지 않는다.

## 15. 결정 기록

현재 고정된 핵심 결정은 다음과 같다.

- 외부 molecular solver는 customer runtime이 아니라 offline oracle이다.
- v2 과학 core는 `betelgeuze_engine_v2/`에서 독립적으로 발전시킨다.
- AI는 non-attention·non-Transformer sparse residual-energy 구조를 기본으로 한다.
- force는 scalar energy의 exact reverse-mode gradient로 정의한다.
- TorsionTopologyGNN과 TemporalStateGNN을 혼합된 “T-GNN”으로 부르지 않는다.
- PINN은 solver가 아니라 objective와 release gate다.
- projection은 matrix-free·fixed-rank이며 dense `N x N` operator를 만들지 않는다.
- `O(N)`은 hard-cap·fixed-budget 조건부 계약이고 PME·ensemble 비용을 숨기지 않는다.
- CPU reference를 먼저 안정화하고 GPU parity는 실제 ROCm 장비에서 증명한다.
- 과학 gate를 통과하지 못한 capability는 제품에서 기본 비활성화한다.

다음 항목은 각 단계 착수 전에 다시 결정해야 한다.

- 최초 commercial chemistry coverage와 atom-typing 범위
- 첫 구조분석·도킹 benchmark protocol과 threshold
- PME와 FMM 중 첫 production long-range 방식
- 첫 AMD 지원 GPU·ROCm version matrix
- 로컬 GUI 기술과 offline installer 형식
- 상업 license, 공개 범위와 parameter·model 배포 정책

## 16. 관련 참고문서

- [Independent Engine v2 Architecture](independent_engine_v2_architecture.md):
  수학·AI·희소 기하·복잡도와 claim boundary
- [Independent Engine v2 Migration Matrix](independent_engine_v2_migration_matrix.md):
  기존 파일별 reuse·adapt·replace·archive 결정
- [`independent_engine_v2_capabilities.yaml`](../config/independent_engine_v2_capabilities.yaml):
  현재 capability 상태와 machine-readable blocker
- [Target Bioscience Architecture](target_bioscience_architecture.md):
  최종 workflow와 result contract 목표
- [Release Claim Evidence Ladder](release_claim_evidence_ladder.md)와
  [Benchmark Ledger](BENCHMARK_LEDGER_CURRENT.md): claim 승격 증거 규칙
- [Product Vision](PRODUCT_VISION_CURRENT.md)과
  [Legacy Product Implementation Plan](product_full_implementation_plan.md):
  기존 restricted 제품·운영 lane이며 V2 과학 완료 상태와 분리
- [Complete Commercial Product Gap Analysis](complete_commercial_product_gap_analysis.md):
  과거 시점별 상세 gap·receipt 참고자료이며 현재 전략의 source of truth는 아님
- [README 한국어](../README.ko.md): 저장소 운영·산출물·로컬 실행 개요

이 문서의 phase 완료 표시는 구현 코드, 테스트, row-level evidence와 capability
gate가 함께 변경될 때만 갱신한다. 계획 문구만으로 phase를 완료 처리하지 않는다.
