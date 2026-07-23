# Independent Engine v2 독립 상용화 장기 로드맵

기준일: 2026-07-17

문서 상태: current-main canonical planning reference; 비실행·비주장 문서

현재 단계: V2-0 독립 CPU 스캐폴드와 V2-1의 bounded source-contract, exact
PubChem CID 176 pH-state, CID 177/11199 reference-canonical tautomer 조각을
구현하고 four-case public redocking protocol definition, H5 parameter/runtime
boundary, CPU reference energy/force contract-validation protocol을 결과 실행
전에 고정하고 reference evaluator·exact fixture materializer·독립 analytic oracle의 source binding,
실제 review를 포함하지 않는 signed independent-review attestation 계약과 실제
receipt를 포함하지 않는 single-run execution-authorization 계약, 실제 실행·결과를
포함하지 않는 execution-environment/result-receipt 계약, raw signed artifact를
재검증하는 local POSIX atomic nonce-reservation primitive, 그리고 전체 chain과 실제
CPU process를 run-start에서 재검증해 secret-free environment receipt를 원자적으로
기록하는 primitive, source-only Python import와 Git replacement-ref 거부를 포함한 root-owned
absolute Git의 read-only clean-checkout proof로 실제 Git HEAD를 확인하고 signed runner
source·frozen evaluator source·dependency를 다시 확인하며 manifest와
case materialization/evaluator/oracle을 automatic site 초기화를 끄고 검증 runtime dependency
root만 받은 고정 supervised child에서 실행해 native stall까지
hard-kill하면서 모든 실패를 보존하는 120초 제한 CPU float64 runner, trust key가 없는 canonical stdin 요청과 저장소가 bundle하지
않는 고정 `/etc` root-owned mode-0600 외부 trust store만 사용해 Git metadata가 있는 clean
source checkout의 verified supervisor chain에서 전체 chain을 실행하고 trust material은 child에 넘기지 않으며 미설정 store·wheel-only 실행은 fail-closed하는
exact module entrypoint, 그리고 raw chain·environment·runner-start·observation을
재검증해 test-only failure-inclusive receipt를 원자적으로 기록·검증하는 primitive를
완료한 상태다. 두 bootstrap의 full source/Git-tree canonical manifest, nonce별 source
sidecar와 digest chain, bounded source/dependency streaming, request-bound worker
pre/payload/post lifecycle, child-PID 결속, stdout hard byte bound도 구현됐고 minimization과
energy-force result-review 계약은 source digest와 accepted/rejected disposition을 Ed25519 서명에 결속한다. 그러나 production receipt,
실제 independent result-review 승인·attestation·trusted result-reviewer key는 포함하지 않는다. Energy-force의 upstream scientific-review와 authorization도 공개키 전용 Ed25519로 전환됐으며, leaf review의 독립 dependency-manifest 재검증과 외부 custody는 여전히 미완료다.
두 lane 공통으로 exact `synthetic_validation_production` evidence class, Ed25519
pre-execution permit, monotonic status snapshot, permit→status snapshot의 frozen base
custody와 이를 raw byte로 다시 검증하는 additive companion을 추가했다. Companion은
production-only Ed25519 review·authorization carrier와 seq3·seq4 custody event를
구현하고 causal-time·exact-scalar·role/key/material separation·raw/logical revoke를
검증한다. Linux PID/parent/start-tick/boot/PID-namespace 측정 digest도 결속한다. 다만 실제
key·carrier/event·permit·external log·one-use registry·enrolled host·custody chain은 없고 permit
검증도 bounded 외부 소비 목록을 조회할 뿐 one-use를 원자적으로 강제하지 않는다.
Seq5 reservation companion은 seq1~4 전체 raw prefix와 lane-local canonical nonce
record를 재검증하고, custodian-signed intent에 realm-global permit·authorization-nonce·
predecessor slot 및 registry/witness identity·key·epoch·prior checkpoint를 결속한다.
이어지는 commit artifact는 registry와 witness 서명 및 commit 이후의 더 최신 status
descendant를 검증한다. 그러나 이는 외부 commit에 대한 attestation일 뿐 실제 serializable
CAS, one-use slot 소비, non-equivocation, epoch continuity, 유일 successor를 독립적으로
증명하지 않는다. 같은 prior head에서 갈라진 sibling attestation도 각각 검증될 수 있으므로
모든 실제 CAS·소비·유일성 필드는 false다. 실제 registry·key·intent·commit proof는
provision되지 않았고 environment 이후 custody stage는 planned-only다. Process tuple의
외부 authenticity와 worker carrier 결속도 아직 없고 같은 clock tick의 PID 재사용을
배제하지 못한다. 외부 append-only successor registry가 없어 기존 seq2 sibling event도
상호 배타적으로 만들지 못한다.
V2-1 all-atom preparation,
V2-2 과학 힘장, V2-3 도킹,
V2-4 MD, V2-5 production AI, V2-6 ROCm/HIP, V2-7 상용 제품은 완료되지 않았다.

이 문서는 과거 donor PR의 구현 상태를 승계하지 않는다. 2026-07 donor 정리에서
선택된 변경만 current `main`에 다시 구현·검증됐으며, 나머지 donor patch는
폐기됐다. 이후 작업은 모두 current `main`에서 독립적으로 설계한다.

실제 capability 상태와 출시 가능 여부의 source of truth는 다음 순서다.

1. 실행 코드와 검증 테스트
2. `config/independent_engine_v2_capabilities.yaml`
3. non-empty row-level 과학·benchmark·release evidence
4. 이 로드맵과 기타 narrative 문서

## 1. 최종 목표

고객 실행 경로에서 외부 분자 솔버를 호출하지 않는 완전한 로컬·오프라인
단백질·분자구조 분석 프로그램을 구축한다.

최종 제품은 capability별 검증 범위 안에서 다음 기능을 독립 제공해야 한다.

- 단백질·리간드 all-atom 입력, 정규화, 전처리와 적용범위 판정
- 구조 품질, 결합 포켓, 인터페이스, 상호작용과 변이 영향 분석
- 독립 힘장, 에너지·힘, 구조 최소화와 국소 refinement
- torsion-aware docking, diverse top-k pose와 독립 재점수화
- PBC, 명시적 용매·이온, 장거리 정전기와 NVE/NVT/NPT MD
- 물리 scalar energy에 결합되는 residual-energy AI
- uncertainty calibration, OOD·미지원 chemistry abstention
- capability별 재현 가능한 benchmark와 signed evidence
- CPU 기준과 수치 동등성이 증명된 AMD ROCm/HIP 가속
- 설치·업데이트·복구·3D 시각화·보고서·데이터 격리 제품 기능

Vina, GNINA, Smina, OpenMM, AMBER, GROMACS 등 외부 molecular solver는
offline reference oracle로만 사용할 수 있다. 그 결과를 v2 native 결과로
표시하거나 고객 runtime의 숨은 의존성으로 둘 수 없다.

## 2. 고정 설계 원칙

### 2.1 물리와 AI

독립 물리 엔진이 기준 energy를 소유하고 AI는 제한된 residual scalar energy만
보정한다.

```text
E_total = E_independent_physics + sum_i delta_e_i
F_i = -dE_total / dr_i
```

AI가 보존력을 주장하는 direct force vector를 출력하지 않는다. OOD 또는
calibration 실패 시 residual을 끄거나 결과를 abstain한다.

### 2.2 희소성과 복잡도

제품 경로에 full attention, Transformer, dense `[N,N]` learned weight,
`torch.cdist`, full Hessian/Jacobian을 두지 않는다. 단거리 `O(N)` 표기는 고정
density·cutoff·neighbor/cell capacity·layer/width·candidate budget이 모두
고정되고 overflow가 fail-closed일 때만 허용한다. PME는 `O(N log N)`, 전체
docking과 ensemble은 candidate·step·replica budget을 함께 보고한다.

### 2.3 identity와 fail-closed ingest

지원하지 않는 atom, residue, charge, stereo, connection 또는 chemistry를
carbon·alanine·generic bead로 바꾸지 않는다. source token을 보존하는 것과 그
과학적 의미를 해석하는 것을 별도 capability로 둔다.

### 2.4 CPU 우선

CPU reference algorithm과 tolerance를 먼저 고정한다. 실제 AMD GPU에서 value,
gradient, ranking, overflow, memory와 soak parity를 증명하기 전에는 GPU gate를
열지 않는다.

### 2.5 capability별 승격

한 capability의 구현 또는 출시가 전체 플랫폼을 자동 승격하지 않는다.
구조분석은 출시 가능해도 docking, FEP 또는 MD는 계속 차단될 수 있다.

## 3. 단계별 로드맵

| 단계 | 핵심 목표 | 종료 후 허용 범위 |
|---|---|---|
| V2-0 | 독립 계약·희소 기하·AI 수학 primitive·CPU reference | 내부 스캐폴드 |
| V2-1 | all-atom I/O, canonical identity와 preparation | 명시한 chemistry의 canonical ingest |
| V2-2 | 독립 CPU 단거리 힘장·최소화 | 검증 범위의 energy·force·minimization |
| V2-3 | 구조분석·torsion-aware docking·scoring | 통과 capability의 internal beta |
| V2-4 | PBC·장거리 물리·용매·constraints·MD | 검증 ensemble별 internal MD beta |
| V2-5 | production residual AI와 물리 결합 | calibration·OOD gate가 있는 AI 보정 |
| V2-6 | ROCm/HIP 가속 | CPU parity가 증명된 AMD 실행 |
| V2-7 | 독립 상용 로컬 제품 | 승인 capability만 고객 활성화 |

## 4. 현재 구현 기준점

### V2-0

현재 `main`에는 versioned all-atom contracts, canonical hashes, bounded sparse
geometry, parity-aware scalar-energy reference, exact gradient primitive,
matrix-free projection, torsion·temporal scaffold, fail-closed CPU orchestrator,
strict checkpoint contract와 독립 Python 3.10–3.12 wheel이 있다.

V2-0은 스캐폴드 기준선일 뿐 calibrated physics나 상용 solver가 아니다.

### V2-1 bounded source contracts

현재 machine-readable capability 원장에 등록된 mmCIF 범위는 다음과 같다.

| Capability | 구현된 범위 | 명시적으로 미구현인 의미 |
|---|---|---|
| `v2_bounded_cif_syntax` | 단일 data block의 bounded lexical/structural subset | dictionary conformance·semantic mmCIF |
| `v2_bounded_mmcif_semantic_projection` | entity·asym·polymer sequence source identity | atom coordinate observation·chemistry·topology |
| `v2_bounded_mmcif_zero_occupancy_declarations` | zero-occupancy source declaration 보존 | occupancy crosscheck·missingness 추론 |
| `v2_bounded_mmcif_altloc_declarations` | polymer atom-site altloc source declaration 보존 | conformer selection·population 해석 |
| `v2_bounded_mmcif_atom_site_model_policy` | 전체 `_atom_site.pdbx_PDB_model_num` 정수 token·row 결속과 model-set 분류; model 1 단일 입력만 bounded execution 허용 | multi-model·single non-1 model 실행, model selection·ensemble·trajectory·averaging, cross-category model reconciliation |
| `v2_bounded_mmcif_biological_assembly_policy` | `_pdbx_struct_assembly`·`_pdbx_struct_assembly_gen`·`_pdbx_struct_oper_list` exact selected row 결속과 source-declaration preparation admission | assembly ID·operation expression·asym list·matrix/vector 해석, composition, coordinate expansion, biological correctness 판정; category 부재를 ASU=biological assembly 증거로 사용 |
| `v2_bounded_mmcif_missing_atom_residue_policy` | `_pdbx_unobs_or_zero_occ_residues`·`_pdbx_unobs_or_zero_occ_atoms` 전체 selected row와 `occupancy_flag` 0/1을 결속하고 source-declared observation gap이 있으면 preparation을 차단 | missing identity 해석·missingness 추론·atom/residue repair·coordinate generation; category 부재를 structure completeness 증거로 사용 |
| `v2_bounded_mmcif_modified_residue_declarations` | `_pdbx_struct_mod_residue`의 source-declared modified polymer component를 label asym·sequence·component identity와 결속 | atom-site observation·parent chemistry·modification nature·auth/model/insertion semantics·preparation |
| `v2_bounded_mmcif_nonpoly_identity` | nonpoly component/entity/asym/instance alias와 source insertion-code marker identity | atom-site join·role·chemistry·topology, general author/label 의미 |
| `v2_bounded_mmcif_nonpoly_component_declarations` | selected component atom과 optional component bond source row | element·charge·aromaticity·stereo·bond order·topology |
| `v2_bounded_mmcif_nonpoly_component_roles` | `_entity.type`, `_chem_comp.type`, component element·formal-charge composition으로 source water와 단원자 metal/nonmetal ion 경계를 보수적으로 분류 | general ligand·cofactor·nonpoly modified-residue 역할, metal coordination chemistry, ion/metal preparation |
| `v2_bounded_mmcif_struct_conn_declarations` | selected 23-field `_struct_conn` row의 nonpoly instance·component atom identity join | connection type·symmetry·order·covalence·coordination·topology |
| `v2_bounded_mmcif_nonpoly_atom_site_observations` | exact 21-field `_atom_site`에서 selected nonpoly instance·component atom과 `_struct_conn` endpoint observation join; known insertion code의 scheme·atom-site·connection exact identity 일치 | coordinate numeric value·geometry·occupancy·B-factor·formal charge·topology, polymer insertion/deletion·renumbering 의미 |
| `v2_bounded_mmcif_nonpoly_coordinate_values` | selected `Cartn_x/y/z` 원문 spelling·finite binary64 값·exact bit pattern 결속 | coordinate unit·geometry quality·distance·clash·occupancy·B-factor·formal charge·topology |
| `v2_bounded_mmcif_nonpoly_atom_site_scalar_values` | occupancy·B-factor·formal charge의 known/unknown/not-applicable 상태와 bounded numeric value 결속 | occupancy population·B-factor quality·charge chemistry·altloc·topology |
| `v2_bounded_mmcif_nonpoly_canonical_topology` | component SING/DOUB/TRIP/QUAD/AROM bond와 identity-symmetry `covale` Bond, 별도 `metalc` coordination edge | 비identity symmetry·hydrog·disulf·DELO/PI/POLY·원소/charge/aromaticity chemistry |
| `v2_bounded_mmcif_nonpoly_neutral_coh_preparation` | neutral acyclic C/O/H component의 single/double bond graph, 명시적 0 formal charge, fixed-valence hydrogen completion과 instance별 failure-complete parameterability report | hydrogen 좌표·reviewed parameter source의 graph binding·parameter assignment·canonical `AllAtomSystem` binding·charged/aromatic/stereo/extended-element/cyclic/pH/tautomer/intercomponent preparation |
| `v2_bounded_mmcif_nonpoly_hydrogen_coordinates` | prepared graph와 source Cartesian Å 좌표를 결속하고 source atom 좌표를 보존하며 added H에 deterministic 1.0 Å fixed parent-offset table 적용 | neighbor geometry·stereo·protonation·tautomer 해석, bond-length calibration, clash·coordinate quality, minimization, parameterability |
| `v2_bounded_mmcif_nonpoly_all_atom_systems` | eligible instance의 prepared atom/bond identity, source scalar state, exact coordinate bit, residue/chain source identity를 기존 canonical `AllAtomSystem`과 SHA-256에 결속; coordination edge는 metadata로 보존하고 intercomponent covalence는 fail-closed | parameter source·parameter/partial-charge/mass assignment, geometry·chemistry validation, coordination의 canonical Bond 승격, source-format round trip, parameterability |
| `v2_bounded_mmcif_nonpoly_parameter_source_binding` | reviewed Sage source identity·immutable artifact SHA-256·license identity·candidate scope를 eligible canonical system hash와 별도 carrier로 결속 | artifact bundling·OFFXML parsing·parameter coverage/applicability·parameter/partial-charge/mass assignment·geometry·force/energy·과학 검증·parameterability |
| `v2_bounded_mmcif_nonpoly_partial_charge_assignment` | caller가 제공한 explicit partial-charge vector를 exact parameter-bound system hash·atom order·finite binary64 bit·method provenance SHA-256·formal total-charge 보존과 결속해 `Atom.partial_charge_e`에 적용 | charge 생성·보정·과학적 method validation, parameter coverage/applicability, force-field parameter·mass assignment, geometry·force/energy 검증·parameterability |
| `v2_bounded_mmcif_nonpoly_all_atom_round_trip` | charge-assigned system의 canonical Engine v2 JSON encode/decode/re-encode byte identity, atom·bond·residue·chain, topology·coordinate hash, source lineage metadata, parameter-source binding과 partial-charge binary64 bit 보존 receipt | original mmCIF text 재출력, source token spelling·category order·comment·whitespace 보존, chemistry·parameter·과학 검증·parameterability |
| `v2_bounded_mmcif_nonpoly_ph_dependent_protonation` | 입력 graph가 reviewed PubChem CID 176 neutral acetic-acid graph contract와 정확히 일치할 때 pKa 4.76과 caller pH를 결속하고 Henderson–Hasselbalch 우세 population이 90% 이상이면 protonated/deprotonated canonical `AllAtomSystem` 선택; 경계 population은 abstain하고 선택 system은 canonical JSON byte round-trip 검증 | source structure identity 인증, general acid/base·multi-site·polyprotic chemistry, pKa prediction/calibration, source-observed H 제거, resonance equivalence·tautomer selection, partial charge·parameter·mass, geometry·energy·과학 검증·parameterability |
| `v2_bounded_mmcif_nonpoly_ph_protonation_corpus` | PubChem CID 176·702 factual identity, source URL·retrieval date·license-review boundary를 결속한 7-case real-world-identity corpus; supported 2·abstention 1·failure 4를 모두 실행 | source structure identity 인증, raw PubChem record·contributor text·PubChem conformer bundling, general chemistry coverage, legal determination, parameter fitting·과학/benchmark/product 승격 |
| `v2_bounded_mmcif_nonpoly_reference_tautomer_selection` | exact neutral C2H4O PubChem CID 177 acetaldehyde 또는 CID 11199 vinyl-alcohol graph contract만 인식하고 reviewed reference-canonical acetaldehyde graph 선택; vinyl alcohol에서는 generated hydroxyl H 하나만 이동하고 canonical JSON byte round-trip 검증 | source structure identity 인증, general tautomer enumeration, source-observed H 이동, population·equilibrium·thermodynamic preference·pH 해석, partial charge·parameter·mass, geometry·energy·과학 검증·parameterability |
| `v2_bounded_mmcif_nonpoly_tautomer_selection_corpus` | CID 177·11199·702 factual identity와 license-review boundary를 결속한 6-case real-world-identity corpus; supported 2·failure 4를 모두 실행 | raw PubChem record·contributor text·conformer bundling, source identity 인증, general chemistry coverage, thermodynamic evidence, legal determination, parameter fitting·과학/benchmark/product 승격 |
| `v2_reviewed_parameter_source_provenance` | OpenFF Sage 2.2.1 unconstrained의 release tag·commit·immutable artifact URL·byte size·SHA-256, repository license identity·license-text SHA-256와 검토 범위를 고정한 offline provenance 계약 | OFFXML semantic parsing·artifact bundling/network fetch·graph binding·parameter/partial-charge assignment·coverage/applicability/calibration·force/energy·과학/benchmark 검증·법률 판단 |
| `v2_bounded_mmcif_nonpoly_preparation_corpus` | SHA-256으로 고정한 exact ASCII 30-case synthetic contract corpus와 별도 7-case pH·6-case tautomer real-world-identity corpus를 결속한 52-axis executable coverage ledger; supported 25·explicitly unsupported 27·not implemented 0 | zero implementation gap을 과학·commercial readiness로 해석, parameter fitting·V2-1 종료·과학/benchmark/product 승격 |
| `v2_frozen_public_benchmark_protocol` | PoseBusters 공식 저장소 고정 commit의 packaged PDB example 4건에 대해 external receptor/reference/ligand-identity-seed SHA-256, MIT·RCSB CC0 license metadata, seed 좌표를 무시하는 fixed-receptor-frame 2 Å symmetry-aware direct RMSD·bounded validity endpoint, all-case failure denominator와 scorer source SHA-256을 고정한 v1.1 protocol; bounded offline materializer가 caller-provided exact SDF byte를 검증하고 모든 multi-record parse/match/failure 행, directional V2000 stereo-aware labeled-graph match, bounded automorphism, 모든 일치 reference에 대한 무정렬 receptor-frame RMSD 최솟값과 canonical receipt를 보존; 별도 installable offline suite command가 symlink 없는 local root의 receptor 포함 12개 artifact를 검증하고 4개 case 성공/실패 행을 누락 없이 no-overwrite receipt로 기록 | raw data bundling·network fetch·pose 생성·receptor-ligand validity·scoring/ranking·도킹 benchmark 실행/결과/발표 승인, ligand-only alignment, 독립 chemical standardization, directional bond mark를 넘는 완전한 atom stereo 해석, 통계적 대표성, PoseBusters Benchmark 동등성, 법률 판단, 과학/benchmark/product 승격 |
| `v2_h5_reference_physics_parameter_applicability_record` | caller-supplied explicit parameter origin, 구현된 5개 energy term·mixing/switch/pair semantics, code-enforced topology·neighbor·orthorhombic-PBC·capacity admission, 7개 runtime source SHA-256을 고정한 H5 record | production parameter set, Sage-to-runtime value binding, OFFXML parsing·assignment, scientific chemical applicability, fitting·calibration·force/energy validation, physics/customer 실행 승인 |
| `v2_bounded_cpu_reference_minimization` | single-model CPU float64 입력과 caller-supplied explicit parameter에 한정한 deterministic force-steepest-descent, Armijo backtracking, iteration/backtrack/displacement/neighbor hard bound, failure-inclusive evaluation row, source/topology/parameter/config identity와 exact little-endian binary64 좌표를 결속한 checkpoint/restart | production parameter set·assignment, general chemistry/applicability, improper·constraint·long-range·solvation, 독립 minimization reference/validation, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_reference_term_diagnostics` | unchanged frozen evaluator의 5개 component energy를 single-model CPU float64의 모든 `6N` plus/minus perturbation에서 중앙차분해 per-term force를 만들고 analytic total force 합계·component net force를 검증하며, non-periodic 입력에 `sum((r-r_center) outer F)` configurational virial·대칭성·uniform-strain derivative를 제공 | independent scientific reference, parameter/applicability validation, pressure/stress, periodic cell-strain virial, improper·constraint·long-range·solvation, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_reference_improper_constraint_extension` | frozen v1 evaluator·parameter source를 변경하지 않는 별도 versioned schema에서 ordered-star `asin` out-of-plane harmonic improper energy·autograd force와 simultaneous equal-weight degree-relaxed Jacobi distance projection을 제공하고, single-model CPU float64에서 초기 상태와 모든 trial을 제약면에 투영한 뒤 bounded iterative tangent-force projection과 실제 projected displacement Armijo 감소를 적용하는 constrained minimization·exact checkpoint/restart를 제공; position/force iteration·pair correction·capacity hard bound, minimum-image PBC distance, 모든 nested residual/failure row와 identity digest를 보존 | reviewed parameter·general improper/constraint assignment와 coverage, atomic-mass-weighted constraints, independent force·constraint·constrained-minimization validation, long-range vacuum electrostatics·fixed-radius polar GB 이외 solvation, MD integrator 연계, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_fixed_born_polar_solvation` | Still DOI `10.1021/ja00172a038`의 `sqrt(r² + alpha_i alpha_j exp(-r²/(4 alpha_i alpha_j)))` pair function을 고정하고, exact topology·v2 charge-parameter fingerprint·caller radius-source SHA-256에 결속된 전 원자 fixed effective Born radius로 non-periodic single-model CPU float64 polar dielectric-transfer self/pair energy와 autograd force를 계산하며 v2 energy/force 결합 evaluator와 solvation fingerprint를 결속한 optional constrained minimization·exact checkpoint/restart를 제공; 512 atom·130816 pair hard bound와 minimum-distance admission 적용 | effective Born radius geometry 추정·reviewed radius/charge parameter와 applicability, nonpolar solvation, salt·explicit ion, PBC solvent, MD 통합, independent solvation·solvated-minimization reference/validation, 과학·benchmark·product/customer 승격 |
| `v2_cpu_reference_minimization_validation_protocol` | unsolvated v1·constrained v2·fixed-Born constrained v2·checkpoint/restart·identity/applicability failure의 ordered 14-case, CPU float64 사전 10개 metric, all-case failure denominator, exact minimizer/evaluator source SHA-256와 independent-reference import 분리 요구사항을 결과 전에 고정한 execution-disabled protocol; 별도 exact materializer와 source-bound 표준 라이브러리 독립 reference를 구현하고, Ed25519 independent-review attestation·CPU-only network-disabled execution-environment/failure-inclusive result-receipt·single-run authorization 계약을 고정함; 별도 local POSIX atomic reservation primitive가 raw signed review/authorization을 재검증하고 caller-provisioned mode-0700 root에 `O_EXCL`·`O_NOFOLLOW`·mode-0600 canonical record·file/directory `fsync`로 one-time nonce를 소비하며, 별도 run-start primitive가 raw chain과 durable nonce·실제 CPU-only deterministic process·network namespace를 다시 검증하고 최대 5분 operator-signed network-isolation attestation을 확인한 뒤 separate private root에 canonical mode-0600 secret-free environment receipt 하나를 원자적으로 기록함; 두 stdlib-only bootstrap은 signed raw Git commit/tree object를 Git SHA-1 framing으로 자체 재검증하고 전체 tracked `betelgeuze_engine_v2` file의 mode·blob OID·SHA-256·size를 root-owned read-only live tree와 비교한 canonical source manifest를 6-tuple state로 전달함; run-start는 이를 `<nonce>.source-tree.json`으로 mode-0600·`O_EXCL`·`O_NOFOLLOW`·fsync 보존하고 runner/writer는 persisted/live exact equality와 environment→start→observation→result digest chain을 확인함; bounded runner는 선택된 6개 aggregate dependency identity·manifest를 함께 재검증하고 bounded `scandir`·direct `RECORD` streaming·pre-read cap·carried deadline 아래 nonce별 start marker를 소비한 뒤 ordered 14-case를 실행해 성공·실패, 독립 오라클 비교, checkpoint exactness와 complete ordered coordinate trace를 writer receipt에 결속함; frozen trajectory-comparison 계약은 exact evaluation index·iteration·trial·outcome 정렬, 사전 `1e-8 Å` coordinate와 `1e-10 kcal/mol` energy max/RMS, branch·rejection·count·fail-closed disposition, 3개 checkpoint case의 uninterrupted/paused/resumed digest를 runner·writer·result review에 결속하고 omission·reorder·cross-wire·non-finite·digest tamper를 거부함; 외부 acceptance threshold를 유지한 채 declared constraint tolerance의 절반을 내부 projection convergence headroom으로 쓰는 v2.1 protocol로 refreeze했으며, 비-production 점검은 fixed-Born 2건을 포함해 14/14 comparison과 3/3 restart equality를 모두 통과함; exact canonical-input entrypoint는 package import 전에 signed nonce·author·source·dependency를 결속하고 고정 외부 root-owned mode-0600 trust store에서만 reviewer/operator key를 재로딩하며 고정 supervised evaluator subprocess를 검증한 뒤 같은 verified process에서 result receipt를 finalize함; 별도 Ed25519 result-review 계약은 full writer-schema validation 뒤 raw signed pre-execution chain, source-manifest digest, exact receipt, 14개 case, retained/missing metric, runtime/oracle/result hash, status/error, exact count, finite energy ledger, complete coordinate trace와 모든 disposition을 role-separated caller public key signature에 결속하되 어떤 claim도 승격하지 않음; release/delete API는 없고 실제 key/trust store/attestation/authorization receipt/production root/reservation/environment receipt/start/result/result-review approval은 bundle하지 않음 | externally provisioned root-owned/read-only source/dependency runtime, kernel-backed source/Git-metadata immutability·custody, pre-bootstrap stdlib closure, mapped native-DSO lifetime closure·worker pre/post-state, lane별 status 이후 carrier propagation·provisioned external custody, 실제 independent scientific review와 attestation/trusted key, signed authorization receipt·trusted operator key·production nonce reservation/root와 environment receipt, production result receipt·independent result-review approval, 승인된 production trajectory comparison, 두 CPU host 재현, 승인된 production external implementation receipt, reviewed parameter/applicability, validation 실행·결과·human review·parameter fitting·과학/제품 승격 |
| `v2_cpu_reference_energy_force_validation_protocol` | 7개 synthetic fixture profile·20개 mutation contract·ordered 27 case·59 deterministic CPU float64 variant·19 metric·failure-inclusive denominator, exact materializer/evaluator/oracle, 공개키 전용 Ed25519 pre-execution review와 single-run authorization, CPU environment/result receipt, atomic nonce/run-start, full source/dependency manifest, request/PID/transcript-bound supervised worker, failure-inclusive result writer를 고정함; 별도 Ed25519 result-review leaf는 exact receipt와 retained raw energy/force array에서 56개 required metric occurrence를 독립 재계산한 bitwise-equal 값, 모든 case/variant/metric/failure/worker disposition, 성공 input/component/total/force evidence, four-role separation을 결속하고 모든 claim flag를 false로 유지함 | 실제 independent scientific/result review와 production result-review attestation/trusted key, independent dependency-manifest 재검증, lane별 status 이후 carrier propagation·provisioned external custody, externally provisioned root-owned source/dependency runtime, signed native-DSO lifetime closure, 실제 nonce/environment/start/result receipt, external receipt authenticity, 실제 27/59 production run·두 CPU host·승인된 production external comparison·human approval, reviewed runtime parameter/applicability, energy/force/minimization validation, parameter fitting·제품 승격 |
| `v2_openmm_reference_offline_oracle` | `OpenMM==8.4.0.post2`, native build `8.4.0.dev-4768436`/commit, `Reference` platform만 허용하고 CPU 대체를 금지하는 offline mapping; 27/59의 47 pass variant를 exact atom order·Å↔nm·kcal↔kJ·orthorhombic PBC·exclusion·scaled pair·quintic switch·5개 force group으로 비교하고 12 failure variant는 `not_applicable_engine_contract`로 보존; 14-case operational trace 중 8개 pass의 모든 좌표를 재평가하고 6개 fail-closed 빈 행을 보존하며 ordered-star improper와 fixed-Born self/pair CustomForce를 별도 기록; 전체 OpenMM distribution·Python wrapper·`_openmm`·Python executable·path-free environment identity와 사전 energy `1e-10`, force `1e-8` max/RMS를 canonical receipt에 결속; 별도 v4 Ed25519 verifier가 두 Engine result-review chain·exact materialization·component/trace receipt·14행 native endpoint receipt·host/CPU/session/custody identity·역할 분리·freshness·revocation/supersession을 재검증하고, frozen endpoint health가 8/8이 아니면 exact fixed-Born disposition receipt·configuration·physics·완결성·분류를 별도 결속한 뒤 실패 case ID를 보존한 signed rejection을 생성하며 accepted endpoint에서는 failure-specific disposition 입력을 금지함; OpenMM L-BFGS는 Engine trace와 다른 별도 endpoint | development observation이나 signed rejection을 production evidence로 해석, 실제 reviewer key/accepted attestation·signed production external-oracle receipt·두 CPU host exact physics equality·외부 custody·최종 human S0 approval, parameter 값·chemical applicability·과학 검증, OpenMM customer runtime 의존성, Engine Armijo/Jacobi trace 또는 checkpoint 동등성, 과학/benchmark/product 승격 |
| `v2_s0_production_evidence_bundle` | 정확히 두 raw host evidence를 single-host verifier로 새로 검증하고 두 host 모두 native endpoint health 8/8·실패 ID 없음·accepted review이며 failure-specific disposition path가 not applicable임을 먼저 요구함; host·CPU·session·custody·result/review/OpenMM/environment receipt·authorization/review nonce의 상이성, commit·source manifest·dependency·OpenMM runtime/source·seed·energy-force/minimization/native-endpoint physics projection의 exact equality를 요구하는 frozen v4 S0 bundle; 모든 하위 역할과 분리되고 host review보다 늦게 시작하며 더 오래 유효하지 않은 최종 human Ed25519 승인, canonical transport, freshness, revocation/supersession을 검증함; 두 host 검증 후 secret-free detached signing request와 exact canonical approval byte를 생성하고 설치형 CLI가 private key 없이 외부/HSM signature를 public key로 검증·attachment하며 output overwrite를 금지함; attachment 뒤에도 full raw evidence 재검증이 필수이고 통과 시 frozen synthetic S0 protocol acceptance와 S1 admission만 true | 현재 6/8 native endpoint failure disposition, 실제 두-host production evidence·trust key·authenticated external custody·최종 승인, real-molecule chemistry/applicability·validated refinement claim, parameter fitting·benchmark·product·customer·broad scientific 승격 |
| `v2_synthetic_validation_production_evidence_custody_foundation` | 두 synthetic lane의 exact production evidence class, 24시간 이내 one-use-intent Ed25519 permit, adjacent previous-hash와 full-row 누적 불변을 요구하는 monotonic status snapshot, 4 MiB signed-carrier 및 argv/bundle/status-row hard bound, frozen seq1 permit→seq2 status base를 변경하지 않고 raw prefix를 내부 재검증하는 additive production-only Ed25519 review/authorization carrier와 seq3·seq4 custody event, 전체 seq1~4 raw ancestry·lane-local nonce record·realm-global slot·registry/witness authority를 결속하고 dual-signed commit 주장과 post-commit status descendant를 검증하는 attestation-only seq5 companion, seq5를 다시 검증하고 고정 순서의 정확한 3-leaf 인접-root 전이·분리된 backend/observer 서명·공급되어 재검증된 status-lineage-tail denial·caller-expected native checkpoint 일치를 검사하는 verifier-only same-epoch boundary, fixed `/proc`의 PID·nonnegative parent·start tick·boot ID·PID namespace 측정 digest 결속; caller expectation provenance와 global latest status head는 인증하지 않으며 downgrade·bounded replay-list·key alias·status rewrite·stale/retroactive status·exact-scalar 혼동·causal-time 위반·raw/logical revoke·context transplant를 fail-closed하고 모든 actual/scientific/product claim을 false로 유지 | 실제 external serializable CAS·permit/nonce/predecessor global one-use 소비·status-head CAS·non-equivocation·epoch continuity·successor uniqueness, 실제 Evidence Authority/Run Custodian/review/authorization/registry/witness/backend/observer key와 carrier/event/proof/authenticated head receipt, permit·external append-only log/TSA·global one-use registry, enrolled host·immutable store·실제 custody chain, worker carrier 결속, same-tick PID reuse 배제, procfs/host/launch external authenticity, environment→start→worker-transcript→observation→result→review→response carrier, production result·과학/제품 승격 |

표의 `worker pre/post-state` blocker는 endpoint snapshot 자체의 부재가 아니라, signed
native allowlist와 load/execute/unload 전체 수명·외부 custody가 결합된 production-grade
closure의 부재를 뜻한다. Endpoint snapshot·payload aggregate·child PID 결속은 구현됐다.

> **2026-07-20 runtime-integrity 갱신:** 위 두 synthetic validation lane의
> durable dependency manifest와 full source/Git-tree manifest 코드 blocker는
> 해소됐다. 두 bootstrap은 signed raw commit/tree object를 Git SHA-1 framing으로
> 자체 재검증하고, 전체 tracked package file의 mode·blob OID·SHA-256·size를
> root-owned read-only live tree와 비교한 canonical manifest를 6-tuple로 전달한다.
> Run-start는 이를 nonce별 mode-0600 `<nonce>.source-tree.json`으로
> `O_EXCL`·`O_NOFOLLOW`·fsync 보존하며 runner/writer는 persisted/live exact
> equality와 environment→start→observation→result digest chain을 확인한다.
> minimization과 energy-force result-review의 Ed25519 signature도 이 digest를 결속한다.
> Runtime-integrity v14는 공개키 전용 energy-force Ed25519 chain, refreeze된 minimization trajectory-comparison 계약과 permit→status snapshot custody-v1, review/authorization
> custody extension, seq5 reservation extension, verifier-only external registry-
> proof boundary, verifier-only authenticated head/status receipt boundary,
> verifier-only same-epoch later-head consistency boundary, fixed-policy exact-
> anchor witness-quorum boundary, verifier-only adjacent epoch-transition
> continuity boundary, process-launch-identity의 exact frozen SHA-256을
> 직접 결속해 독립 drift를 차단한다. Runtime v8~v13은 read-only legacy
> identity로 보존한다.
> 공급된 registry proof가 검증할 수 있는 것은 backend의 serializable/committed
> attestation, 고정 순서의 정확한 3-leaf 전이, observer-signed native checkpoint와
> caller expectation의 일치뿐이며 그 expectation의 provenance나 global latest
> status head를 인증하지 않는다. 실제 external CAS·global one-use·non-equivocation·
> epoch continuity는 계속 false다.
> 추가된 authenticated head/status receipt verifier는 두 nested 입력을 사용 전에
> snapshot하고 같은 raw registry proof를 두 번 재현한 뒤, 분리된 외부 Ed25519
> authority가 proof·seq5·realm/epoch/sequence·native checkpoint/state root·receipt 시점
> status tail·service identity·causal time·caller challenge를 정확히 결속했는지
> 확인한다. 또한 receipt 발행 뒤의 strict status descendant를 별도로 재검증해
> receipt 자체와 authority/proof/checkpoint/service에 대한 revoke·supersede를
> 적용한다. 이는 bounded signature와 challenge equality만 증명하며 challenge
> freshness/one-use, global latest, CAS, later-head consistency, non-equivocation,
> epoch continuity는 증명하지 않는다. 실제 receipt/key/challenge/current-status
> descendant는 provision되지 않았다.
> 추가된 later-head consistency verifier는 authenticated receipt를 다시 검증하고,
> 같은 epoch의 sequence-adjacent backend-signed checkpoint/state-root path와 전체
> path에 대한 observer countersign을 확인하며 anchor가 attested한 세 consumed-leaf
> encoding의 selected later root 포함을 재구성한다. 이 포함은 실제 global slot
> consumption 증명이 아니며 DTO는 challenge freshness/one-use를 계속 false로
> 보존한다. 별도 sibling pin은 각각 통과할 수 있으므로 global latest·
> non-equivocation·epoch continuity는 계속 false이고 실제 proof와 post-proof status
> descendant는 provision되지 않았다.
> fixed-policy witness-quorum verifier는 N/F/Q와 `2Q-N>F`, 전체 ordered roster의
> caller-pinned 상이한 witness/operator/fault-domain 식별자, exact anchor에서 파생된 stable fork scope,
> exact descendant lineage에 대한 Q개 서명을 검증한다. Q signer뿐 아니라 전체 N의
> policy-window validity와 post-certificate denial을 적용한다. 그러나 fault bound의
> 실제 준수, exclusive-vote locking, 독립 witness journal 일치, 숨은 sibling
> certificate 부재는 관찰하지 못한다. 따라서 참인 것은 conditional same-epoch
> exact-anchor certificate뿐이며 realm-wide non-equivocation은 계속 false다. 실제
> policy/key/certificate/journal/post-quorum status는 provision되지 않았다.
> adjacent epoch-transition verifier는 이전 exact witness-quorum proof를 다시
> 검증하고 caller-pinned integer ordinal의 정확한 `+1`, terminal state root의
> 변경 없는 sequence-zero genesis 이관, 전체 transition context에서 유도한 genesis
> checkpoint, 동일 statement에 대한 상이한 이전/다음 fixed-roster Ed25519 quorum을
> 요구한다. 이는 공급된 한 전환의 continuity만 증명한다. 외부 locking 없이 별도
> quorum-signed sibling도 각각 통과할 수 있으므로 successor uniqueness·독립 journal
> 일치·realm-wide non-equivocation·global latest·CAS는 계속 false다. 실제 transition
> proof/policy/key/vote/post-transition status는 provision되지 않았다.
> `rglob`·`os.walk`·`distribution.files` 기반 열거와 unbounded source read는
> bounded `scandir`·direct `RECORD` streaming·pre-read cap·carried deadline으로
> 교체됐다. 다만 외부 root-owned source/dependency runtime은 아직
> provision되지 않았다. 활성 energy-force base 계약은 run-start까지 v3이며
> runner/result writer는 v5, result review는 v2다. Minimization base 계약은 v4이며
> runner는 v8, writer/result review는 v7이다. Production review/authorization 및
> reservation custody extension은 v4, runtime-integrity는 v14로 전환해 전체 upstream hash DAG를 다시 고정했다.
> superseded 계약 문서 76개는 canonical
> projection hash 기반 read-only verifier로 보존하지만, 과거 signed artifact나
> receipt 호환을 claim하지 않는다. 외부 runtime provisioning, kernel source/Git-
> metadata immutability·custody, pre-bootstrap stdlib closure, signed native-DSO
> allowlist·full lifetime closure·kernel vDSO identity, measured process identity의
> worker-carrier 결속·same-tick collision resistance와 외부 launch authenticity/custody,
> 최종 evidence-class carrier·provisioned custody chain, energy-force의 실제
> receipt/result-review/attestation/trusted key, leaf의 independent dependency-manifest
> 재검증, 실제 run·두 host·human review는 여전히 blocker이며 모든
> production/scientific/fitting/product claim은 false다.

두 declaration capability는 source row의 identity와 tamper/crosswire 경계를
닫는다. observation capability는 그 identity를 selected source atom row와
결합하고 instance별 component-atom coverage를 검증한다. 셋 모두 canonical
`Bond`를 만들지 않는다. `_struct_conn`의 `covale`, `metalc`, symmetry와
`pdbx_value_order`는 보존될 뿐 topology 의미로 해석되지 않는다. 별도
coordinate-value capability는 selected `Cartn_x/y/z`를 finite binary64로,
scalar-value capability는 occupancy·B-factor를 finite binary64로, formal charge를
PDBx/mmCIF 범위의 정수로 해석한다. marker에는 기본값을 추론하지 않는다.
이 값 해석은 coordinate geometry, occupancy population, B-factor quality,
charge chemistry 또는 구조의 과학적 타당성 판정이 아니다.

bounded component-role capability는 공식 PDBx/mmCIF source vocabulary인
`_entity.type`, `_chem_comp.type`, `_chem_comp_atom.type_symbol`과
`_chem_comp_atom.charge`만 사용한다. source entity가 water이고 neutral O/H2O
composition인 경우만 water로 해석하며, bounded explicit element allowlist의
단원자 metal과 known nonzero charge의 단원자 nonmetal만 composition 역할로
분리한다. metal/nonmetal 어느 allowlist에도 없는 원소는 역할을 추정하지 않는다.
unknown charge에는 dictionary default를 추론하지 않고, 일반 nonpoly component를
ligand·cofactor·modified residue로 추정하지 않는다. metal/ion은 분류되더라도
preparation과 parameterization은 명시적으로 미지원이다.
일반 nonpoly component의 `unresolved_nonpoly_component` 결과와
`ligand_cofactor_and_other_nonpoly_roles_not_interpreted` blocker는 corpus evidence로
고정되며, cofactor 역할을 추정하지 않는 명시적 미지원 경계다. 이는 해당 component가
생물학적으로 cofactor가 아니라고 판정하는 것이 아니다.

bounded modified-residue declaration capability는 공식
`_pdbx_struct_mod_residue` category가 명시한 modified polymer component만
해석한다. `label_asym_id`, `label_seq_id`, `label_comp_id`는 기존 polymer
semantic projection과 교차검증하고 parent component, model number와 insertion
code token을 source spelling 그대로 결속한다. 이 source declaration은 atom-site
observation, parent chemistry, modification nature, auth/label equivalence 또는
modified-residue preparation을 뜻하지 않으며 모두 명시적으로 차단된다. 또한
이 bounded subset만으로 전체 dictionary conformance를 주장하지 않는다.

bounded atom-site model policy는 공식 PDBx/mmCIF 정수 item인
`_atom_site.pdbx_PDB_model_num`을 모든 atom-site source row에서 해석한다.
dictionary 최소값 0과 exact token spelling을 보존하되 현재 execution profile은
model set이 정확히 `{1}`인 입력만 허용한다. 둘 이상의 model 또는 단일 non-1
model은 source 사실을 삭제하거나 첫 model로 자동 선택하지 않고 명시적으로
차단한다. 이 분류는 model selection, ensemble·trajectory·averaging 의미,
cross-category model reference 또는 좌표·원자 identity 해석이 아니다.

bounded biological-assembly policy는 공식 PDBx/mmCIF assembly metadata,
generation specification과 Cartesian operation category의 exact selected row를
결속한다. 세 category 중 하나라도 있으면 preparation 전에 명시적으로 차단한다.
모두 없을 때는 이 declaration gate만 통과하며 deposited asymmetric unit이
biologically relevant assembly라는 증거는 아니다. assembly ID, `oper_expression`,
`asym_id_list`, matrix/vector 값과 composition order를 해석하거나 좌표를 확장하지
않고, source assembly의 생물학적 정확성도 판정하지 않는다.

bounded missing atom/residue policy는 공식 PDBx/mmCIF
`_pdbx_unobs_or_zero_occ_residues`와 `_pdbx_unobs_or_zero_occ_atoms` source row를
전체 결속하고 controlled `occupancy_flag`를 0=`zero_occupancy`, 1=`unobserved`로
분류한다. 두 category 중 하나라도 declaration을 가지면 chemistry 해석 전에
preparation을 명시적으로 차단한다. category가 모두 없을 때는 이 declaration
gate만 통과하며, 그 부재가 구조가 완전하거나 missing atom/residue가 없다는 증거는
아니다. 이 capability는 declaration identity, missingness, repair 또는 좌표를
추론하지 않는다.

bounded nonpoly insertion identity는 공식 PDBx/mmCIF의
`_pdbx_nonpoly_scheme.pdb_ins_code`와 `_atom_site.pdbx_PDB_ins_code` marker를
source state·value·quoted 형태로 보존하고, known code가 scheme·selected atom-site·
`_struct_conn` endpoint에서 정확히 같을 때 동일 instance identity로 결속한다.
이는 bounded nonpoly source identity 지원일 뿐 polymer insertion/deletion,
canonical renumbering, sequence alignment 또는 일반 author/label 의미 해석이 아니다.

bounded topology capability는 component bond order·aromatic flag·E/Z stereo를
명시적으로 교차검증한다. `_struct_conn`의 identity-symmetry `covale`만 explicit
order로 canonical Bond를 만들고 `metalc`는 Bond가 아닌 coordination edge로
남긴다. 비identity symmetry, `hydrog`, `disulf`, DELO/PI/POLY는 fail-closed다.

bounded preparation capability는 neutral acyclic C/O/H와 single/double component
bond로 범위를 고정한다. source element·formal charge·nonaromatic·stereo 상태를
교차검증하고 fixed neutral valence로 hydrogen-completed chemical graph만 만든다.
source-declared zero-occupancy 또는 unobserved atom/residue가 있으면 chemistry 전에
fail-closed한다.
모든 instance는 실패 원인을 보존하는 parameterability report를 가지며,
base graph snapshot에는 hydrogen 좌표가 없고 reviewed parameter source와 canonical
`AllAtomSystem` adapter가 직접 결속되지 않으므로 항상 `parameterable=false`다. 별도 bounded hydrogen-
coordinate capability가 좌표 projection을 제공하더라도 geometry validation이 없어
이 gate는 열리지 않는다. 이는 pH-dependent protonation, tautomer selection,
과학적 chemistry validation 또는 실행 가능한 all-atom preparation이 아니다.

bounded hydrogen-coordinate capability는 공식 PDBx/mmCIF Cartesian Å source
좌표를 preparation graph와 결속한다. source atom의 finite binary64 좌표와 identity를
그대로 보존하고, added hydrogen은 parent 중심의 고정된 네 방향과 1.0 Å offset으로
결정론적으로 배치한다. 이 table은 coordinate-bearing contract fixture일 뿐
neighbor bond geometry, stereo, protonation·tautomer, calibrated bond length,
steric clash 또는 coordinate quality를 해석하지 않고 minimization도 수행하지 않는다.

bounded all-atom materializer는 preparation graph와 hydrogen-coordinate snapshot이
정확히 일치하고 intercomponent covalence를 누락하지 않는 instance만 기존 versioned
`AllAtomSystem`으로 만든다. prepared atom·bond identity, source atom scalar state와
coordinate binary64 bit, nonpoly residue·chain source identity 및 parent snapshot hash를
보존한다. metal coordination edge는 canonical covalent `Bond`로 승격하지 않고 exact
identity metadata로 남긴다. intercomponent covalence가 있으면 affected instance를 모두
명시적으로 차단한다. 생성된 system은 contract-valid이지만 partial charge·mass·parameter가
없고 fixed-offset geometry도 검증되지 않았으므로 parameterable·chemistry/scientific
valid·source-format round-trip 또는 customer-ready system이 아니다.

bounded parameter-source binding capability는 위 canonical system을 변경 가능한
parameter 값과 혼동하지 않도록 별도 evidence carrier를 만든다. reviewed Sage source의
identity·version·artifact SHA-256·license identity와 candidate scope를 source system
SHA-256에 결속하고, binding metadata 외 topology·coordinate·atom state가 동일함을
검증한다. artifact를 bundle하거나 OFFXML을 해석하지 않으며 parameter coverage,
applicability, parameter·partial-charge·mass assignment, geometry 또는 과학적 타당성을
확립하지 않으므로 system은 계속 `parameterable=false`다.

bounded partial-charge assignment capability는 charge를 계산하는 알고리즘이 아니라
명시적 값 적용 계약이다. caller가 제공한 vector가 exact parameter-bound system과
instance에 결속되는지, atom 수와 canonical order가 일치하는지, 모든 값이 finite
binary64인지, method provenance SHA-256이 있는지, 합계가 canonical formal total charge와
`1e-12 e` 안에서 일치하는지를 fail-closed 검증한다. corpus는 전부 positive-zero인
synthetic contract fixture만 사용하며 parameter fitting data가 아니다. 따라서 이
capability는 charge generation·calibration·scientific validation·applicability 또는
force-field parameter/mass assignment를 확립하지 않고 `parameterable=false`를 유지한다.

bounded all-atom round-trip capability는 charge-assigned canonical system을 Engine v2
canonical JSON으로 encode한 뒤 독립 decode·re-encode하고 byte SHA-256과 system,
topology, coordinate, identity-projection hash가 모두 동일한지 검증한다. atom·bond·
residue·chain field, source lineage metadata, parameter-source binding과 partial-charge
binary64 bit도 projection에 포함한다. 이는 canonical interchange identity receipt이며
original mmCIF text를 다시 쓰거나 source token spelling, category order, comment,
whitespace를 보존하는 lexical round trip이 아니다. chemistry·parameter·scientific
validation 또는 customer readiness도 승격하지 않는다.

bounded pH-dependent protonation capability는 general protonation predictor가 아니라
exact PubChem CID 176 neutral acetic-acid graph 하나에 대한 독립 contract layer다.
PubChem PUG REST에서 검토한 CID·formula·connectivity SMILES·InChIKey와 PubChem
page의 pKa 4.76, source URL·retrieval date·source-specific license-review boundary를
고정한다. 입력 graph 일치는 contract 비교일 뿐 source structure identity를 인증하지
않는다. raw PubChem response, contributor text와 PubChem conformer는 bundle하지
않고 deterministic mmCIF 좌표는 contract fixture일 뿐이다. caller pH는 finite
binary64와 bounded `[0, 14]` 범위로 결속하고, monoprotic Henderson–Hasselbalch
population의 한 상태가 90% 이상일 때만 선택한다. 그보다 모호한 population은
system을 만들지 않고 abstain한다. deprotonated state는 source-observed atom이 아닌
exact generated hydroxyl H 하나만 제거하고 singly bonded O에 localized `-1` formal
charge를 둔다. resonance equivalence와 tautomer selection은 해석하지 않으며 선택된
system도 partial charge·parameter·mass, geometry·energy·과학 validation 없이
`parameterable=false`, `claim_safe=false`를 유지한다.

별도 real-world-identity pH corpus는 CID 176의 low-pH protonated, high-pH
deprotonated, pKa 경계 abstention과 CID 702 ethanol graph mismatch, reference
crosswire, pH range, source-observed acidic-H failure를 합계 7개 row로 고정한다.
supported·abstention·failure를 모두 denominator에 남기며 parameter fitting data가
아니다. PubChem download policy가 contributor별 제약 확인을 요구하므로 commercial
redistribution 승인이나 법률 판단도 주장하지 않는다.

별도 tautomer-selection capability는 CID 177 acetaldehyde와 CID 11199 vinyl
alcohol의 exact neutral C2H4O graph contract만 인식하고 acetaldehyde를 reviewed
reference-canonical identity로 선택한다. vinyl alcohol의 generated hydroxyl H만
이동하며 source-observed H 이동은 fail-closed다. 이는 population, equilibrium,
thermodynamic preference 또는 pH 예측이 아니다. 6-case corpus는 두 supported
selection과 structure mismatch·source-H·reference·instance crosswire failure 네
개를 모두 denominator에 유지한다.

reviewed parameter-source provenance capability는 OpenFF 공식 force-field repository의
Sage 2.2.1 unconstrained artifact를 release tag `2024.09.0`과 exact commit에 고정하고,
artifact byte size·SHA-256, `CC-BY-4.0` license identity와 license-text SHA-256,
reviewer role·timestamp·포함/제외 scope를 결속한다. 이는 identity·license·후보 범위의
contract review일 뿐 artifact를 bundle하거나 runtime에서 내려받지 않는다. OFFXML을
해석하거나 이 preparation graph에 parameter를 배정하지 않고 partial charge,
molecule coverage, applicability domain, parameter calibration, force/energy 정확도,
과학·benchmark 타당성 또는 법률 준수를 승인하지 않는다.

H5 parameter-applicability record는 위 Sage 2.2.1을 기존 reviewed candidate
identity로만 참조한다. 최신 release를 선택했다는 주장도, OFFXML에서 runtime
parameter 값을 추출했다는 주장도 하지 않는다. 실제 reference evaluator의 값은
caller가 `ReferenceForceFieldParameters`로 모두 명시하며 package에는 production
또는 reference parameter set이 없다. record는 harmonic bond/angle, graph-implied
proper periodic torsion, Lorentz-Berthelot Lennard-Jones, screened Coulomb,
quintic switch, explicit exclusion/scale, orthorhombic minimum image와 exact
topology·neighbor·capacity admission을 7개 source SHA-256에 결속한다. 이 admission은
bounded code path가 실행 가능하다는 뜻일 뿐 molecule·element·charge coverage나
physical accuracy를 검증한 scientific applicability domain이 아니다.

CPU reference energy/force contract-validation protocol은 H5 record를 exact
SHA-256 dependency로 결속하고 synthetic implementation-mathematics lane을 결과
관측 전에 고정한다. 7개 synthetic fixture profile·20개 mutation contract와
27개 ordered pass/fail-closed case·19개 float64 metric을 포함한다. harmonic bond/angle, proper torsion, Lennard-Jones,
screened Coulomb, mixing/scaling/switch, orthorhombic minimum image, full-term
composition, central finite difference, translation/rotation/permutation,
same-environment determinism과 12개 fail-closed row를 포함한다. 모든 metric은
float64 unit·aggregation·threshold가 사전 정의되고 27개 case 전체가 denominator다.
별도 frozen artifact binding은 reference evaluator source와 모든 fixture·mutation·case를 59개 deterministic CPU
float64 runtime variant로 materialize하는 source, 표준 라이브러리 scalar 식과 forward-mode
exact derivative만 사용하는 독립 analytic oracle을 exact source SHA-256으로 결속한다.
Oracle source는 reference evaluator·validation protocol·Torch·NumPy·외부 molecular
solver import가 없음을 AST로 검사한다. 두 구현을 비교하는 test-only observation과
receipt writer는 존재하지만 production validation study, production result receipt 또는
independent result acceptance는 없다. 별도 frozen review contract는 exact dependency, ordered review
check/limitation, implementation-author/reviewer SHA-256 identity 분리, 외부 trusted
Ed25519 reviewer public key, signature integrity와 최대 30일 validity를 요구한다. 저장소는 trusted
key나 실제 attestation을 bundle하지 않고, verified review만으로 실행 또는 fitting을
승인하지 않는다. 별도 authorization contract는 verified review, author/reviewer와
pairwise-distinct operator identity, 외부 trusted key, exact code·runner·environment·
result·dependency hash, 최대 24시간 validity, 외부 revocation 목록과 unused one-time
nonce를 요구한다. 별도 local atomic reservation primitive는 raw review/authorization을
재검증하고 caller-provisioned mode-0700 POSIX directory에서 `O_EXCL`·`O_NOFOLLOW`와
file/directory `fsync`로 nonce를 소비한다. release/delete API는 없고 duplicate 또는
poisoned path는 fail-closed다. 그러나 operator key·receipt·reservation root·production
reservation은 bundle하지 않으며 filesystem locality와 same-UID replacement resistance도
확립하지 않는다. 따라서 receipt verifier와 primitive 모두 실행 gate를 열지 않는다.
별도 run-start primitive는 raw review/authorization과 durable nonce record를 다시
교차검증하고 실제 Linux·Python·Torch·NumPy·GPU visibility·seed·thread·determinism·
고정 logical argv를 관측한다. exact authorization/operator/network namespace에 결속된
최대 5분의 Ed25519 network-isolation attestation을 외부 trust anchor로 검증한 뒤
private artifact root 아래 mode-0600 canonical environment receipt 하나를 `O_EXCL`과
file/directory `fsync`로 기록한다. 실제 path와 secret-bearing argv는 기록하지 않고,
library 자체는 network namespace를 만들거나 kernel isolation·same-UID resistance를
확립하지 않는다. production key·attestation·root·receipt는 bundle하지 않으며 생성된
receipt도 production validation execution, fitting 또는 과학 주장을 승인하지 않는다.
별도 bounded runner는 persisted receipt와 live process, validation dependency import
전에 root-owned Python executable로 실행되는 source-only stdlib `-I -S -B -X pycache_prefix=/dev/null` outer
bootstrap과 동일 interpreter의 고정 source-bound `-S -B -X
pycache_prefix=/dev/null` controlled inner 재실행,
replacement ref를 비활성화·거부하는 root-owned absolute Git read-only preflight가 증명한
clean HEAD·bootstrap·dependency-identity helper·runner를 함께 묶은 signed runner source·frozen evaluator/materializer/oracle
source·선택된 6개 aggregate dependency identity를 다시 확인하고 nonce별 mode-0600 runner-start marker 하나를
`O_EXCL`·file/directory `fsync`로 소비한다. Frozen manifest는 marker 소비 전 supervised
preflight child에서 만들고 남은 budget을 다시 확인한 뒤에만 marker를 소비한다. 이후 CPU float64 27개 case·59개 variant는 고정 case worker에서
순서대로 평가한다. Parent의 120초 hard deadline은 Torch/native stall도 worker kill로
중단하며 worker 내부 POSIX timer는 보조 경계로 유지한다. threshold failure, expected fail-closed row,
unexpected evaluator failure와 미관측 metric까지 canonical in-memory observation에 모두
보존한다. Outer는 stdin을 읽기 전에 exact executable·flag·argv·cwd·source를 검증하고
요청에서 allowlist 환경을 구성해 inner로 재실행한다. Inner는 전체 process identity를
검증한 뒤에만 bounded canonical stdin을 읽으므로 canonical uint32
`PYTHONHASHSEED`가 기록만 되는 것이 아니라 interpreter 초기화에 실제 적용된다.
Bootstrap 코드는 non-root 실행과 root-owned/read-only package snapshot을 요구한다.
Signed raw Git commit/tree object는 Git SHA-1 framing으로 자체 재검증되고 전체 tracked
package file의 mode·blob OID·SHA-256·size canonical manifest가 live tree와 비교되어
6-tuple bootstrap state로 전달된다. Run-start는 `<nonce>.source-tree.json`을 mode-0600·
`O_EXCL`·`O_NOFOLLOW`·fsync로 보존하고 runner/writer가 persisted/live equality와
environment→start→observation→result digest chain을 확인한다. Source/dependency 열거는
bounded `scandir`·direct `RECORD` streaming·pre-read cap·carried deadline을 사용한다.
Worker는 request-bound pre/payload/completion frame, native endpoint snapshot과 payload
aggregate를 출력하고 parent는 stdout을 hard byte cap 아래 streaming하며 pre/post PID가
실제 child PID와 같을 때만 전체 payload를 수용한다. Canonical worker request와
transcript digest·길이·frame 순서를 observation에 보존하고, complete raw stdout이
request·retained rows·lifecycle에서 재구성한 transcript와 byte 단위로 같아야 한다.
Writer와 두 result review도 이를 독립적으로 재구성·재해시한다. Incomplete
output은 bounded digest·길이·prefix/discard disposition만 남기고 child payload를 전부
폐기하며 승인 대상이 아니다. 다만 외부 production
source/dependency runtime, kernel source/Git-metadata immutability와 custody,
pre-bootstrap stdlib closure, signed native-DSO allowlist·full lifetime closure·kernel
vDSO identity, worker PID start-time/boot-ID와 외부 launch custody는 production
blocker로 남는다.
별도 Linux process primitive는 이 tuple을 fixed `/proc`에서 bounded·race-checked로
측정하지만 worker evidence에는 아직 결속되지 않고 durable uniqueness를 주장하지 않는다.
공통 Ed25519 permit/status base, raw prefix를 재검증하는 seq3 review·seq4
authorization companion, 그리고 attestation-only seq5 reservation companion도
구현됐다. 그러나 실제 key/carrier/event, 외부 serializable registry/CAS proof,
slot 소비는 provision되지 않았다. Same-epoch witness quorum과 adjacent epoch-
transition continuity verifier도 구현됐지만 실제 proof/policy/key/vote가 없고 외부
witness locking·journal comparison·유일 successor·realm-wide non-equivocation은
증명하지 않았으며 environment 이후 stage도 없으므로 production blocker를 해제하지 않는다.
Worker의 argv·cwd·flag·전체 환경·uint32 hash seed·application seed와 parent/child hash
probe도 verified receipt에서만 유도해 평가 전에 확인하며 mutable supervisor 환경을
복사하지 않는다. Exact process chain은 absolute checked-out bootstrap path를 사용하고
`PYTHONPATH`·user-site override와 `sitecustomize`·`.pth` 실행을 무시하며 root-owned
read-only dependency root만 허용한다. Package initializer import 전에 external operator
Ed25519 signature, signed commit/source와 clean checkout을 검증하며 reservation/artifact root는
checkout과 ancestry가 겹치지 않는 private 외부 directory만 허용한다. trust key가 없는 bounded canonical stdin 요청만 받고,
reviewer/operator anchor는 저장소가 bundle하지 않는 고정 `/etc/betelgeuze/engine-v2/
reference-validation-trust-anchors.json` root-owned mode-0600 외부 store에서만 읽는다.
trust material을 stdin·argv·worker request·response에 남기지 않고 verified supervisor가
environment receipt 생성과 result finalize를 소유하되 Git metadata가 있는 clean source checkout을
요구하며 store 미설정·unsafe mode·wheel-only invocation은 fail-closed한다. marker
release/delete API는 닫혀 있다. 별도 result writer는 raw
signed review/authorization, persisted/live environment, durable runner-start와 exact
observation identity를 다시 확인한 뒤 private caller root에 mode-0600 canonical receipt
하나를 `O_EXCL`·`O_NOFOLLOW`·file/directory `fsync`로 기록하고 모든 실패 case·variant·
metric을 유지하고 metric/status 모순, filename/embedded nonce 불일치, blocking special-file
read를 거부한다. verifier는 외부 exact receipt SHA-256과 최신 revocation/supersession
입력을 요구한다. receipt는 unsigned이며 private POSIX storage를 external authenticity로
간주하지 않고 same-UID replacement resistance도 확립하지 않는다. 테스트 전용 signed
artifact와 receipt로 이 primitive를 검증하지만 production key·attestation·receipt·root·
runner start/result·independent acceptance를 bundle하지 않는다.
별도 energy-force Ed25519 result-review leaf는 exact receipt와 ordered 27 case·59
variant·19 metric을 재검증하고 retained raw energy/force array에서 56개 required metric
occurrence를 독립 재계산해 retained float와 bitwise equality를 요구하며,
case/variant/metric/expected-failure/worker disposition,
성공 input/component/total/force evidence와 four-role separation을 결속한다. Upstream
scientific-review와 authorization도 공개키 전용 Ed25519이며, leaf는 live dependency
manifest를 독립 재검증하거나 external custody를 확립하지 않는다. 실제 production
receipt, result-review attestation, trusted result-reviewer key, independent human approval은
없고 모든 production/scientific/fitting/benchmark/product flag는 false다.
별도 frozen receipt 계약은
CPU-only·network-disabled Linux 환경, Python 3.10–3.12, Torch 2.6.0, NumPy 1.26.4,
empty GPU visibility, deterministic seed/thread/argv/dependency와 confined artifact path를
고정하고 27개 case·59개 variant·19개 metric 전체의 failure-inclusive 결과 형식을
고정한다. 그러나 production environment receipt·runner start, durable observed value 또는
result receipt는 포함하지 않는다. Energy-force Ed25519 post-result-review 계약과
upstream review·authorization·run-start 공개키 chain은 구현됐지만 실제 독립 과학
review·result-review 승인, production attestation/trusted key, independent dependency-manifest 재검증과 외부
custody는 아직 없다. 계약의 source-digest 서명 결속은 이 부재를 대체하지 않는다.
synthetic 값은 parameter-fit data가 아니며 scientific parameterized-force-field
lane의 reviewed runtime 값, chemical applicability, holdout과 독립 reference도 아직
고정되지 않았다. 따라서 current artifact authorization decision은 validation 실행과
parameter-fitting proposal을 모두 거부한다.

bounded preparation corpus는 30개 입력과 기대 결과를 개별 SHA-256으로 고정한다.
지원 그래프 4개, intercomponent preparation 차단 1개, 명시적 미지원 chemistry
18개, upstream policy 차단 5개, invalid-source 2개를 모두 실행하고 failure row를
denominator에서 제거하지 않는다. 별도 7-case pH 및 6-case tautomer
real-world-identity corpus를 결속한 52-axis coverage ledger는 25개 supported,
27개 explicitly unsupported, 0개 `not_implemented`로 분류하며 unclassified
row는 0이다. 이 분류 완전성은
기능 완전성이나 과학적 corpus coverage가 아니다. 따라서
`parameter_fitting_allowed=false`, `v2_1_exit_ready=false`를 유지한다.

nonpoly atom-site의 explicit `label_alt_id` 입력은 현 observation profile이
dot/question marker만 허용하므로 chemistry preparation 전에 fail-closed된다.
corpus는 이 입력과 안정 error code를 고정하지만 conformer를 선택하거나 occupancy
population, missingness 또는 altloc chemistry를 해석하지 않는다.

PDB·SDF V2000 bounded ingest도 존재하지만 general PDB/mmCIF/SDF/SMILES,
biological assembly generation·coordinate expansion, multimodel execution·ensemble
semantics, source declaration을
넘는 general missingness·repair,
neighbor-aware·stereo-aware hydrogen geometry와 general protonation, tautomer,
aromaticity, general ligand/cofactor와
non-source-declared modified residue 역할, metal/ion/cofactor/modified-residue
preparation은 완료되지 않았다.

### V2-1 종료 기준

V2-1 완료를 주장하려면 최소한 다음 증거가 모두 필요하다.

- atom·bond·charge·stereo·residue·chain identity가 round-trip에서 조용히
  손실되지 않는다.
- supported corpus와 의도적 failure corpus가 함께 고정된다.
- `_atom_site` coordinate observation이 entity/asym/residue/component/atom
  identity와 결속된다.
- altloc, assembly, insertion, missing atom/residue와 multimodel 정책이
  capability별로 명시된다.
- hydrogen, protonation, tautomer, aromaticity와 formal charge preparation이
  독립 규칙·provenance·applicability report를 가진다.
- water, ion, metal, cofactor, modified residue와 미지원 chemistry가 명시적으로
  분리된다.
- 지원 chemistry·parameterability 표가 executable gate와 일치한다.

현재 상태는 위 종료 기준을 충족하지 않는다.

## 5. 다음 current-main critical path

작업 순서는 다음과 같이 고정한다.

1. 현재 declaration과 atom-site observation identity contract를 executable
   registry, canonical main CI와 clean-wheel import에서 유지한다.
2. 완료된 bounded layer로 selected `Cartn_x/y/z`의 finite binary64 값, raw
   token spelling과 exact bit pattern 결속을 유지한다. 좌표 identity·numeric
   value와 과학적 geometry quality는 계속 분리한다.
3. 완료된 bounded layer로 occupancy, B-factor와 formal charge의
   known/unknown/not-applicable·numeric semantics를 coordinate value와 분리해
   유지한다. missing marker에는 dictionary default를 자동 적용하지 않는다.
4. 완료된 bounded layer로 source declaration에서 canonical topology로 넘어가는
   connection type, identity symmetry, bond order, covalence와 coordination
   규칙을 유지한다. 해석되지 않은 연결에서는 `Bond`를 생성하지 않는다.
5. 완료된 bounded layer로 최초 chemistry 범위를 neutral acyclic C/O/H와
   single/double bond로 고정하고, fixed-valence hydrogen-completed graph 및
   failure-complete parameterability report를 유지한다. 별도 deterministic
   coordinate-bearing hydrogen projection은 geometry validation과 분리한다.
   canonical `AllAtomSystem`과 reviewed parameter-source identity binding은 별도
   carrier로 유지하며 parameter 값, general pH·tautomer·aromatic/charged chemistry와
   계속 분리한다.
6. 완료된 첫 contract layer로 exact ASCII 30-case synthetic supported/failure
   corpus와 52-axis coverage ledger를 유지한다. expectation mismatch, input hash
   drift, coverage row 누락과 evidence signal 누락은 모두 fail-closed다.
7. 완료된 exact PubChem CID 176 pH-dependent protonation과 7-case corpus,
   exact CID 177/11199 reference-canonical tautomer selection과 6-case corpus를
   유지한다. 52-axis ledger의 implementation gap이 0이어도 scientific 또는
   commercial readiness로 승격하지 않으며 original mmCIF lexical 재출력은 별도
   미지원으로 유지한다.
8. 완료된 v1.1 four-case public benchmark protocol/manifest의 exact source·license
   metadata·endpoint·failure denominator·scorer identity와 source-bound offline
   materializer를 유지한다. 별도 suite command로 receptor를 포함한 12개 입력 identity와
   4개 failure-inclusive case receipt를 보존한다. 모든 reference record·graph
   match/mismatch/failure, stereo-preserving bounded automorphism과 무정렬 receptor-frame
   RMSD 최솟값을 보존하되 데이터 fetch/bundle·pose 생성·validity·scoring·도킹 결과·
   발표·과학 승격은 계속 금지한다.
   별도 same-input 외부 baseline 준비 계약은 frozen source에 결속된 exact receptor/
   ligand PDBQT byte와 preparation tool/configuration/executable/container identity를
   검증하고, 동일한 native-defined center·22.5 Å box·seed·exhaustiveness·mode 수·CPU
   수를 쓰는 Vina/GNINA/Smina 비실행 work order 3개만 만든다. 준비 파일·엔진·실행·
   결과 receipt·통계적 holdout·독립 준비 audit·독립 재실행은 포함하지 않는다.
   공개 split provenance 계약은 PDBbind v2020 fit·285-case CASF-2016·논문판
   308-case PoseBusters Benchmark의 source/access/license/endpoint를 분리하고 공식
   PoseBusters case list를 raw/canonical SHA-256으로 고정한다. case별 release·receptor/
   ligand/scaffold/protein-chain-set·target family·cofactor·chemistry disposition과
   모든 chain pair 최대 Smith-Waterman/BLOSUM62 identity stratum을 결속하며 generic
   calibration leakage 및 all-case/target-family 분모를 다시 검증한다. PDBbind 접근
   승인·full manifest·dataset byte·sequence 실행·fit/result·독립 재실행은 포함하지 않는다.
   그 위의 installable public-ranking-corpus intake는 caller-pinned canonical
   PDBbind-v2020 `fit`, full 285-case CASF-2016 `validation`, full 308-case
   PoseBusters `test` manifest와 fit↔validation·fit↔test·validation↔test
   all-chain sequence receipt 3개를 동시에 결속한다. exact
   case/PDB/target/receptor/ligand/scaffold/target-sequence overlap, 0.90 초과
   sequence identity, fit→test·validation→test release-order 위반, sequence
   method drift와 scoring/preparation drift를 fail-closed로 기록한다. frozen
   configuration SHA-256은
   `4972e41765076e09b7bbec43b7e506dede6ab48b01b173f62cd73a749f694681`이다.
   input은 no-follow canonical file과 caller-pinned file/payload hash만 허용하고
   receipt는 mode-0600/no-overwrite다. 실제 licensed PDBbind/CASF manifest와
   실행된 sequence evidence가 아직 없으므로 production receipt를 만들지 않았고,
   partition·score·label·fit·model selection·metric·review·claim은 모두 false다.
   passing corpus receipt 위의 별도 installable calibration-partition intake는
   canonical PDBbind `fit`·CASF `validation` `PoseRankingCalibrationPartition`
   파일만 허용한다. public manifest binding과 pose-level fit/validation leakage를
   재계산하고 success/failure·positive/negative·case·pairwise-uninformative 분모를
   모두 보존한다. validation label은 evaluation-only이며 test partition 인자는
   존재하지 않는다. fit failure는 조용히 버리지 않고 별도 bound training view가
   필요하다고 표시한다. frozen configuration SHA-256은
   `c4b423063a36f38d7f6f098a38c7ea54b078c25f3cc04d060ae88638902ff8be`다.
   genuine upstream corpus가 없으므로 production partition receipt·fit·selection·
   test evaluation·metric·review·claim은 아직 없다.
   그 위의 installable calibration training-view boundary는 fit row의 `status`
   만으로 모든 success를 변경 없이 embedded training partition에 넣고, 모든
   failure를 실행 가능한 fit에서만 제외한 뒤 hash-bound disposition으로 보존한다.
   training-view/CASF leakage를 다시 계산하며 validation label이나 test partition
   없이 기존 deterministic fit API를 호출하는 guarded bridge를 제공한다. frozen
   configuration SHA-256은
   `e5e202d10420b5a557b1227aa0f7735433ebaeadc1656f6b981c14453aeb25b8`이다.
   genuine upstream corpus가 없으므로 production training-view receipt·fit·selected
   model·metric·review·claim은 아직 없다.
   별도 extraction-free PoseBusters intake는 공식 Zenodo ZIP·논문판 308-ID byte를
   exact identity로 고정하고 전체 central directory를 bounded audit한 뒤 선택 case별
   필수 artifact 4개의 CRC/SHA-256을 308개 failure-inclusive 행으로 보존한다.
   2026-07-23 local ignored-state 관측은 308/308 ready와 exact 재실행 일치를 확인했지만
   이는 public input-carrier identity sub-gate만 닫는다. sequence/release provenance·
   family provenance·preparation·pose generation·validity·scoring·external baseline·
   독립 재실행·과학 승격은 여전히 열려 있다.
   그 위의 별도 extraction-free corpus audit는 exact intake를 재실행하고 receptor/
   native/start 308건 전부의 parser failure, heavy labeled connectivity, raw V2000
   directional/aromatic bond 표현, 원소·formal charge·ligand capacity, metal과
   non-water cofactor를 all-case Wilson 95% CI로 보존한다. 같은 날짜의 ignored-state
   receipt는 308/308 parse와 heavy connectivity 308/308을 확인했지만 provisional
   scorer chemistry 범위는 34/308, 실제 admission은 parameter·partial charge 미할당으로
   0/308이었다. raw directional mark 일치는 128/308이고 raw aromatic bond type 4는
   0/308이므로, 이를 atom stereo 또는 aromaticity validation으로 해석하면 안 된다.
   receipt payload SHA-256은
   `a239aae11a46be01c5f6f11082e6aa51cd57f256e228082c80abae3a6a3b4507`이며 exact
   재실행이 일치했다. 이 결과는 chemistry/ingest preflight이지 docking benchmark가 아니다.
   그 다음 native-geometry preflight는 native crystal pose를 receptor frame에서
   fixed-radius overlap·topology-excluded ligand self-overlap·native/start heavy-bond
   delta로 진단했다. 2026-07-23 ignored-state receipt는 308/308 처리·failure 0,
   element geometry 159/308, bounded geometry 교집합 89/308, reference scorer chemistry
   범위와의 교집합 15/308, complete pose validity 0/308을 기록했고 exact 재실행이
   일치했다. case CCD와 같은 residue name이 receptor에 남은 6건도 별도 관측했지만
   covalent 결합으로 판정하지 않았다. receipt payload SHA-256은
   `118c1c0db0424504ad7727e1b7bbbc355138f2693805439061395421da109a12`이다.
   이 결과는 native positive-control 휴리스틱이며 force-field strain·generated-pose
   validity·PoseBusters oracle·redocking·scoring/ranking·benchmark evidence가 아니다.
   그 위의 strict external-input preparation receipt는 provisional chemistry 범위
   34건에 pinned Meeko 0.7.1/RDKit 2025.9.6 AD4/Gasteiger default를 적용하고 Python·
   dependency payload·source role·native-defined box center·private PDBQT byte를
   고정했다. exact 재실행은 ligand 준비 34/34, receptor/input-pair 준비 18/308,
   template failure 15건, 기타 receptor-construction failure 1건, chemistry abstention
   274건을 기록했다. receipt payload SHA-256은
   `3856706f5b470386e9151bc272f158192839683deaf08a2bc8f1d377b22082ba`,
   artifact-set SHA-256은
   `5ff0ae2a54ec1c70f61011b76a24242a0eccbffbd23f523ff035f9e18e040e19`이다.
   `allow_bad_res`로 residue를 삭제하지 않았으며 이 결과는 preparation coverage일
   뿐 charge/type 과학 검증·generated pose·Vina/GNINA/Smina result·PoseBusters
   oracle·family/leakage metric·독립 재실행·docking benchmark evidence가 아니다.
   그 preparation receipt를 입력으로 하는 installable ligand charge/type diagnostic도
   추가했다. Meeko `SMILES IDX`·`H PARENT`를 엄격히 해석하고 생략된 H 전하는 부모
   원자에 합산하며 macrocycle closure `G0` pseudoatom은 실제 화학 원자와 분리한다.
   RDKit core 2022.09.5와 2025.09.6 관측은 각각 prepared 18건·실제 PDBQT 원자
   481개·zero-charge `G0` 2개를 failure 없이 보존했다. 실제 원자 전부가 PDBQT
   3자리 직렬화 허용치 0.0005 e 안에 있었고 최대 오차는
   0.0004979832249129013 e였다. element/type 호환성과 aromatic-carbon `A` 일관성도
   18/18 통과했으며 두 버전의 expected charge 481/481개는 binary64 bit 단위로
   같았다. 2022·2025 observation payload SHA-256은 각각
   `df57b0d48ba905e0f132b66a3b4d4fc344fffc4a40f1d78de181c0264bedba8f`·
   `6d3389ed55e7d47c8e0b0076c485b3f4ee7590cb3f9ddcd12db89030e92b6b50`,
   cross-version comparison payload SHA-256은
   `ab9cf4b72d3af848dd48484fcbb203268fe8d7336ec552ffe52c360dca972b5f`이다.
   source-tree와 isolated installed-wheel exact 검증이 모두 일치했고 wheel 2회는
   `9d1c96336c1fa55051ab3e0fc2192d990860c644dc5f39a0685f07c39613124e`로 byte
   단위 일치했다. 하지만 두 관측은 같은 Gasteiger 알고리즘의 버전 비교이므로 독립
   charge oracle이 아니다. AD4 type semantics·source SDF chemistry·receptor charge/type·
   unsupported chemistry도 독립 검증되지 않았다.
   별도의 installable Open Babel 3.2.1 독립 구현 비교도 추가했다. 동일한 exact
   preparation identity를 입력으로 `OBChargeModel("gasteiger")`의 full-precision
   charge와 Open Babel PDBQT writer의 AD4 type을 비교하고, 308개 행 전체를
   보존했다. prepared 18건 모두 comparison failure 없이 완료됐고 실제 원자 481개와
   별도 보존·통계 제외된 `G0` pseudoatom 2개를 다뤘다. Meeko 3자리 PDBQT charge
   대비 MAE/RMSE/최대 절대 delta는 0.0038510594375734796 /
   0.012204476318346003 / 0.18097866788513423 e였고, AD4 type exact 일치는
   476/481이었다. 불일치 5개는 `SA`/`S` 3개와 macrocycle `CG0`/`C` 2개로
   모두 보존했다. source-tree와 isolated installed-wheel exact 검증은 receipt
   payload SHA-256
   `7754c4b56e10d4543b064c23daaf69ab99e098fda81bfd9fbaecc8694439d943`을
   재현했고 wheel 2회는
   `d0fc6a2acce76f2e3d23915b533528263d10e8277c0cf6feafd09e318c6d9529`로 byte
   단위 일치했다. 이 결과는 독립 구현 실행 공백만 닫는다. charge 정확도 임계값은
   사전등록되지 않았고 Open Babel은 quantum charge oracle이 아니다.
   exact-tag source 검사로 `CG0`/`C` 2개는 Meeko macrocycle ring-closure 확장
   vocabulary이고, `SA`/`S` 3개는 neutral thioether를 `[SX2]`로 acceptor 처리하는
   Meeko와 형식전하 -1인 sulfur만 acceptor로 보는 Open Babel의 실제 semantics
   차이임을 확인했다. RDKit 2022/2025에서 6·12·24 iteration control도 동일했고,
   `7F5D_EUO` sulfur는 각각 0.21119588924581498·0.21034893344174249·
   0.21033550574606594 e였다. Open Babel 값 0.029021332114865777 e와 비교하면
   iteration 수보다 sulfone sulfur parameter-selection branch 차이가 지배적이다.
   이는 구현 원인 disposition일 뿐 과학적 정확도 판정이 아니다. neutral-thioether
   acceptor 선택과 methylsulfone charge 정확도·source SDF equivalence·receptor
   charge/type·unsupported chemistry·두 번째 CPU host·reviewer receipt가 남아 있다.
   다음 단계는 atom charge 자체를 oracle로 삼지 않고 molecular electrostatic field
   오차를 측정하는 quantum reference protocol과 임계값을 사전등록한 뒤, 두 번째 CPU
   host와 reviewer receipt를 수행하는 것이다.
   `claim_safe=false`는 유지한다.
   이 후속 단계의 첫 실행도 완료했다. installable
   `betelgeuze-engine-v2-posebusters-sulfur-qm-esp` 명령은 계산 전에 protocol을
   별도 등록하며, sulfur 4건과 308-case 전체 disposition, source SDF 고정 좌표와
   explicit hydrogen, neutral singlet RHF/6-31G* spherical basis, 공식 PySCF 2.14.0
   wheel·설치 dependency payload·single native thread, 1.4/1.6/1.8/2.0 배
   Lebedev-110 molecular-surface shell의 동일 가중치, 동일 charge site의 Meeko와
   Open Babel projection, 모든 metric·failure·claim gate를 QM 실행 전에 고정한다.
   protocol payload SHA-256은
   `0927260a16f1e09211fb601fade1725e21d35d221d04e69cfd2c624da7c06137`이다.
   production observation은 사전등록한 4/4건을 QM failure 없이 평가하고 나머지
   304건을 scope abstention으로 보존했다. global weighted ESP RMSE는 4건 모두
   Meeko가 Open Babel보다 낮았지만 차이는 작으며 descriptive label일 뿐이다.
   source-tree와 isolated installed-wheel exact 재실행은 observation payload
   SHA-256
   `402d1795f18b7eb0c87d8537f3b427fe116c0845bf1337b21e24752cef7e52e6`을
   재현했고, wheel 2회는
   `b4564648dbf3fcb681e0b73d1dcbcc2fd96ed10a0fe4a321149fe38545d0d73d`로
   byte 단위 일치했다. 정확도 통과 임계값은 사전등록하지 않았고 HF/6-31G*는
   정의된 reference이지 절대 oracle이 아니며 atom-centered charge는 observable이
   아니다. 따라서 이 4-case fixed-geometry ESP 결과로 neutral-thioether의
   `SA`/`S` hydrogen-bond semantics를 판정할 수 없다.
   `charge_accuracy_pass=null`, `scientifically_validated=false`,
   `benchmark_executed=false`, `claim_safe=false`를 유지한다.
   그 다음 과학 slice인 neutral-thioether donor-acceptor interaction-energy
   protocol도 사전등록 후 실행했다. prior QM/Vina receipt, Vina 1.2.7 exact AD4
   source, 공식 PySCF 2.14.0·PySCF-dispersion 1.5.0 wheel, 환경별 thioether model
   3개, methanol O-H donor 1개, S-H 거리 6개와 plane-normal control 1개, 모든
   complex/ghost geometry, B3LYP-D3(BJ)/def2-SVP Boys-Bernardi counterpoise,
   exact AD4 `S-HD`/`SA-HD` pair formula·weight, failure row와 판정 임계값을
   계산 전에 고정했다. production observation은 geometry 21개와 SCF 63개를
   failure 없이 완료하고 scope abstention 305건을 보존했다. 세 QM profile 모두
   minimum은 2.5 A, -4.758~-5.258 kcal/mol이었고 local O-H acceptor gate와
   AD4 `SA` profile-preference gate는 각각 3/3 통과했다. protocol·observation
   payload SHA-256은
   `f0b0d84551e63272509acaf967996496cc7100cd2a58b71392fe38bce7d8194c`,
   `30d9ceb83aed88fa45b7bc8c8282e6a50ce0299c9f54b21ce0c8885775c35fce`이다.
   source-tree와 fresh installed-wheel observation exact 재실행이 일치했고,
   wheel 2회는
   `bb47ad0c5dcb0a5b9d298d2ba7f423910c11bf03c13f1691c0ecbec9c6db6f56`로
   byte 단위 일치했다. 그러나 plane-normal control이 선택한 idealized
   lone-pair 방향보다 세 model 모두 0.551~0.784 kcal/mol 더 유리했다. 따라서
   방향성·일반 chemical acceptor semantics는 아직 판정하지 않는다. O-H donor
   1종·고정 gas-phase model 3개·isolated pair term은 representative chemistry나
   complete AD4 score가 아니다. 두 번째 CPU host exact 재현과 independent
   reviewer receipt가 있어야 세 `SA`/`S` case의 과학적 disposition을 열 수 있고,
   `scientifically_validated=false`, `claim_safe=false`를 유지한다.
   이 외부 evidence 단계를 위한
   `betelgeuze-engine-v2-posebusters-sulfur-reproduce` 계약은 구현했다.
   실행 전에 baseline/external host와 operator 신원, single-use nonce, exact
   Engine v2 wheel/source, QM/Vina binary와 shared runtime projection을
   사전등록한다. 결과 verifier는 308개 disposition, geometry 21개,
   counterpoise SCF 63개, 허용 오차와 모든 failure row를 다시 계산한다.
   reviewer 단계는 private key를 받지 않는 detached Ed25519 request와
   out-of-band trust anchor, 역할 분리, 만료·revocation·supersession을
   요구한다. 다만 실제 두 번째 물리 host 신원·실행 result·독립 reviewer
   receipt는 아직 없으므로 두 gate는 모두 닫히지 않았고 기존 chemistry,
   docking, benchmark, product claim도 바뀌지 않는다.
   다만 이 chemical gate를 현재 product Vina 경로의 blocker로 오해하지 않도록
   별도 default-Vina invariance protocol을 먼저 등록·실행했다. AutoDock Vina
   1.2.7 exact tag source는 PDBQT `S`와 `SA`를 모두 element sulfur로 변환한 뒤
   동일한 `XS_TYPE_S_P`로 매핑한다. default Vina scoring은 XS type을 사용하며 XS
   acceptor set에는 nitrogen·oxygen만 있고 sulfur가 없다. 세 neutral-thioether의
   exact Vina pose 60개에서 target type 두 글자만 `SA`에서 `S`로 바꾸고 공개
   `Vina.score()` component 8개를 비교했다. 60/60 pose의 모든 component가 exact
   binary64 일치했고 score failure는 0건, scope abstention은 305건이었다.
   protocol과 observation payload SHA-256은 각각
   `81f52bbf68518e1d09e0462f8124ac1a810c7cc502ff8923175703e62b28b57f`,
   `a08ced8bbe0dbecc503f8e5eedf96d239130d0dbced897427694afe61742d406`이다.
   source-tree와 isolated installed-wheel exact 재실행이 일치했고 wheel 2회는
   `fcbdc2df96c3b7df53f90e50e90688898147bf4665f2a816eb7d82382f547535`로
   byte 단위 일치했다.
   따라서 현재 default-Vina fixed-pose score에 한해서
   `bounded_default_vina_invariance_claim_safe=true`다. 그러나 docking search를
   재실행하지 않았고 complete AD4 scoring·chemical hydrogen-bond acceptor
   semantics를 판정하지 않았으므로 `scientifically_validated=false`,
   `benchmark_executed=false`, `claim_safe=false`는 유지한다. 완료한
   donor-acceptor interaction-energy receipt는 AD4/chemical-semantics의 별도
   bounded gate이며 default-Vina fixed-pose 결과의 의미를 바꾸지 않는다.
   그 exact preparation 위의 Vina 1.2.7 production receipt는 single-CPU seed·box·
   spacing·exhaustiveness·mode/energy 범위와 engine/dependency/source payload를
   고정하고 308개 disposition, generated PDBQT, canonical binary64 energy component
   5개를 보존했다. 준비된 18/308을 모두 실행·성공했고 engine failure 0건,
   preparation block 16건, chemistry abstention 274건, pose 355개를 기록했으며
   source-tree와 installed-wheel exact 재실행이 일치했다. receipt payload SHA-256은
   `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`이다.
   pinned build-tool wheel 2회도 SHA-256
   `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`로 byte
   단위 일치했다.
   별도 PoseBusters 0.6.5 generated-pose receipt는 그 exact chain을 입력으로 삼아
   308개 disposition과 pose별 `redock` typed report 133개를 보존했다. 355/355
   pose를 평가했고 non-RMSD binary test 전체 통과는 325/355, Vina-success 18건의
   direct symmetry-aware receptor-frame RMSD <= 2 A는 Top-1 10/18, Top-5
   16/18이었다. installed-wheel exact 재실행은 receipt payload SHA-256
   `9c680e1edd08bfa07c1c71164b696ae050f180c3a2bb04bc91fd5d163a965b86`을
   재현했고 pinned build-tool wheel 2회는 SHA-256
   `b0248a218aaea0ef3f00e65d6f77e077cdd81a4c7ac37a128edd7833e3ce49a8`로
   byte 단위 일치했다.
   이는 strict preparation을 통과한 18-case Vina subset의 validity·RMSD evidence일
   뿐 대표성 있는 docking benchmark가 아니다. 같은 입력의 GNINA 1.3.3과 Smina
   2019-10-15 실행 receipt도 308개 disposition을 모두 보존했다. 두 엔진 모두 준비된
   18건을 시도해 17건 성공했고, `7UAW_MF6`의 prepared AutoDock type `CG0` 미지원
   실패를 숨기지 않았다. GNINA는 340 pose, Smina는 336 pose를 보존했다. 이어지는
   PoseBusters 0.6.5 receipt에서 GNINA는 340/340 평가·physical-validity 304/340·
   execution-success 17건의 Top-1/Top-5 RMSD <= 2 A 15/17·16/17, Smina는
   336/336·312/336·10/17·15/17을 기록했다. installed-wheel exact 재실행은 각각
   receipt payload SHA-256
   `0959201d6165d82041447be820977de7ac8ba64b13d1f237ad5b8c914a290259`와
   `0590067f9c1731f6ebcbff36f54ba08d9265f32454b54fa03b7df0dbc328b930`을
   재현했다. 이는 17-case 조건부 결과다. 이어서 세 exact evaluation receipt를
   conservative observed-target cluster에 결합했다. receptor 첫 coordinate model의
   `ATOM` residue-label sequence, 최소 20-residue chain, 90% global edit-similarity
   link, connected component 규칙으로 308 case가 296 cluster가 됐고 multi-case
   cluster 11개·최대 크기 3·link 13개를 보존했다. Vina의 cluster coverage/complete
   coverage는 18/296·17/296, GNINA와 Smina는 각각 17/296·16/296이다. covered
   cluster의 명시적 any-member Top-1/Top-5 RMSD hit는 Vina 10/18·16/18, GNINA
   15/17·16/17, Smina 10/17·15/17이다. exact 재실행은 receipt payload SHA-256
   `34d782567e816206dcaf2be5207e424b8611a081c9ca6d51bc9500e42ec81e5e`와 file
   SHA-256
   `fc69398c600c032f7f5c18ca1fc8baedd51c93db0f933c2320d1f597265750aa`를
   재현했다. pinned-tool wheel 2회는 SHA-256
   `050d06e9fc49ef3c79bcaefbd8854de85fce0ce7fe4a56cc83418a460280a597`로
   byte 단위 일치했고 installed-wheel exact 검증도 같은 receipt를 재현했다. 이
   cluster는 biological target-family annotation이 아닌 near-identity
   proxy다. 세 엔진 모두 fit/training manifest가 없으므로 target-sequence와
   ligand/scaffold training leakage는 평가하지 못했고 `leakage_control_passed=false`다.
   이어서 official RCSB Data API 관측을 raw 응답 없이 정규화·고정하고, native ligand
   heavy atom과 6 A 이내인 protein chain을 exact `asym_id` 우선·exact
   `auth_asym_id` fallback으로 매핑했다. truncation·alias·removed-entry remap은 하지
   않는다. 308 case 중 mapping complete 306, UniProt annotation 299, Pfam annotation
   225를 보존했고 `6Z14_Q4Z` chain `J`는 unmapped, `7D6O_MTE`는 removed disposition으로
   남겼다. Pfam multi-label family 199개와 중복 없는 exact Pfam-set partition 149개에
   세 엔진의 모든 failure·abstention을 포함한 분모를 결합했다. snapshot payload/file
   SHA-256은
   `4d05e0127bb4c4dfedb5fa0a5f2e11d7de22aae481d34d3840676d04d367b51a`·
   `2287ffc895b28828ff39568f3ee0b98707b8160f04fa10196b469fe9ba722358`,
   target-family receipt payload/file SHA-256은
   `ce7d0f32054f05a328554fa04e38964768d2e734157aa9eca4ceb431c2a87076`·
   `164ef81d7e49dbf32aab6eef56325dfd2ee57e889304e7f3ac0dff7f11a36761`이며
   byte-exact 재실행이 일치했다. pinned-tool wheel 2회도
   `02d837ed5f624505a5a02bf1a5489f8aec1dcf0bacd15ef39b0fa6abf8526deb`로
   byte 단위 일치했고 isolated installed-wheel 검증이 두 receipt를 재현했다. 다만
   HTTPS 관측은 RCSB가 독립 서명하지 않았고
   Pfam coverage도 불완전하다. 다음 증거 slice는 외부 fit/training manifest를 확보해
   target-sequence·ligand/scaffold overlap을 결합하는 것이다. manifest를 확보할 수
   없으면 이 family receipt를 leakage-controlled 결과로 부르지 말고 charge/type
   검증과 두 번째 CPU host 재실행을 진행한다. calibration·reviewer 승인은 여전히
   없다.
   별도 installable pose-ranking intake는 세 evaluation receipt와 RCSB/Pfam receipt의
   caller-pinned root를 검증하고, 연결된 archive·preparation·execution payload/file
   identity를 다시 확인한 뒤 exact score component·RMSD label·physical-validity를
   `split_role=test`로만 결합한다. 현재 exact 재구성은 engine/case 924행, 성공 pose
   1,031행, 명시적 failure 872행을 보존하며 all-308 Top-1/Top-5 count는 Vina
   10/16, GNINA 15/16, Smina 10/15다. receipt payload/file SHA-256은
   `b6526c7407602721f2ec74f09c8b99d4ecdc7336e69417ed6321840663de9ea0`·
   `88b756cd3e7d460edefe8330dbae6141e72492953a1af4e71bb60b1146574813`,
   deterministic wheel SHA-256은
   `c8019fa070e8ca2fc598e26cbdf3c78394fcf9e0963ec656d736b3864681ac51`이며
   source-tree와 installed-wheel receipt가 byte 단위 일치했다. base intake의
   coordinate/scaffold 필드는 합성하지 않고 null로 유지한다.
   별도 installable pose/scaffold identity overlay는 exact archive·preparation·
   Vina/GNINA/Smina artifact와 RDKit 2025.09.6 payload/host identity를 다시
   결속한다. 성공 pose 1,031/1,031에 topology-aware 3-decimal coordinate SHA-256을
   부여하고 failure 872/872를 그대로 보존했다. start/reference scaffold는 308/308
   일치하며 229개 group, 반복 group 15개, 최대 21 case다. 275 case는
   Bemis-Murcko이고 33 case는 표준 Murcko라고 부르지 않는 명시적
   `acyclic_full_heavy_graph` fallback이다. generated/start chemistry와 cross-engine
   topology mismatch는 0이다. start/reference full chemistry는 305/308 일치하고
   나머지 3건은 독립 disposition 대기 상태다. overlay receipt payload/file
   SHA-256은
   `e7b92d0fc74b44f652c5196429812fe61165771906d9d487a13ec8719ac52995`·
   `fbf3fa34f974dc8bd35b6564a1c004931a9ea0177f25fd551769b91f4db089d8`,
   deterministic wheel SHA-256은
   `d3c51e79dc4783f859b7b2ff4a8f8499d42da0d6a4378035c3cf2114b751285e`이며
   installed-wheel exact 검증이 통과했다. 따라서 coordinate/scaffold identity
   blocker는 닫혔지만 complete Pfam assignment, fit manifest,
   target/ligand/scaffold leakage audit, 외부 재실행과 독립 review는 남아 있다.
   identity overlay 자체는 generic calibration partition을 만들지 않는다.
   그 다음 installable ranking-test-partition receipt는 ranking intake·identity
   overlay·observed-sequence cluster·RCSB/Pfam receipt를 exact 결속해 엔진별
   `split_role=test` partition을 materialize한다. Vina는 성공 355+실패 290=645행,
   GNINA는 340+291=631행, Smina는 336+291=627행이며 각 partition에 308 case가
   모두 남는다. 성공 1,031행은 coordinate identity를 사용하고 실패 872행은
   좌표가 아닌 domain-separated failure-observation identity를 사용한다. 21개
   ranking metric, 36개 sequence-proxy metric, 5,226개 RCSB/Pfam metric의
   numerator·denominator·95% Wilson CI를 다시 검증했다. 296개 sequence stratum은
   biological family가 아닌 leakage-control proxy이며 Pfam은 별도 225/308
   annotation이다. receipt payload/file SHA-256은
   `509a7f7c8fcae221be53d5d7e525e05c37a1314f6d17060c8ed6b68e8e4fc89e`·
   `581235213b161caeb41db441ca73428d669a7fa0c9a3ead3bba7632dfa63b1dc`,
   deterministic/installed wheel SHA-256은
   `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`이다.
   fit partition·fitting·leakage audit·외부 재실행·독립 review는 없고
   PoseBusters test label은 fit API에 전달하지 않으므로 calibration·과학·제품
   claim은 계속 닫힌다.
   그 test receipt만 입력으로 받는 installable external-ranking evaluator는
   label 평가 전에 source execution이 이미 사용한 Vina total energy 최소화,
   GNINA CNN pose score 최대화, Smina minimized affinity 최소화 정책을 고정하고
   source pose order 재현을 강제한다. 전체 308 case와 failure observation 872개를
   유지한 결과 scored-case coverage는 Vina 18/308, GNINA 17/308, Smina
   17/308이고 all-case Top-1/Top-5 count는 각각 10/16, 15/16, 10/15다.
   성공적으로 score된 pose에 한정한 tie-invariant average precision은
   0.287330(95% case-cluster bootstrap CI 0.174209–0.512214),
   0.668157(0.534293–0.886705), 0.304352(0.183486–0.541608)다. 이 조건부
   pose metric은 coverage·failure·source-bound physical-validity count와 함께만
   해석해야 한다. 296개 sequence proxy, exact Pfam-set/missing 150개 group,
   overlapping Pfam/missing 200개 group도 receipt에 남는다. receipt payload/file
   SHA-256은
   `509556b0bcd9ec35f9ff4b1860613f267b2a96d73b18de44b61288498a838137`·
   `3f4965ba07be36c6233514d2545c1db0f604bc4245552be2180bcdb780a43dc1`이다.
   이는 actual external-reference result이지만 external model training overlap,
   독립 외부 host 재실행·review, calibrated internal scorer 성능, 대표성 있는
   public benchmark와 docking product claim은 여전히 닫힌다.
   동일한 test partition에는 별도 installable internal-diagnostic ranking
   evaluator를 적용했다. test label을 읽기 전에 UFF receptor–ligand van der
   Waals, PDBQT-charge Coulomb, exact source-atom RDKit UFF strain delta,
   UFF overlap의 네 항과 unit weight·minimize 방향을 고정한다. preparation과
   일치하는 RDKit 2025.09.6·NumPy 1.26.4 runtime에서 source-success pose
   1,031/1,031을 scorer failure 0건으로 계산했고 upstream failure 872건도
   보존했다. Vina/GNINA/Smina scored-case coverage는 18/17/17 of 308,
   all-case Top-1/Top-5 count는 2/5, 3/5, 3/3이다. 성공 pose average
   precision은 0.113931(95% case-cluster bootstrap CI 0.056090–0.270781),
   0.169927(0.100789–0.262457), 0.106265(0.064622–0.224549)다. receipt
   payload/file SHA-256은
   `63a2f62cd465438f83e177b11ffd50483a2ff3f94c9399c308da2e8baee45b57`·
   `4e4acd968e2a32f4f6ff47b8412b9209b5afe6918bda2019fdc4e9e492a4f3b1`이다.
   deterministic wheel SHA-256
   `5378c25f700a3f775aca232e379ea9e56b93a75310daead5d7dfdae082d9800e`을
   checkout 밖에 설치한 exact verify도 같은 receipt를 재구성했다.
   이는 term-decomposed 실행 경로가 완결됐다는 증거이지 validated reference
   force field나 calibrated ranker 증거가 아니다. 외부 source score보다 AP가
   낮으므로 PoseBusters test label로 weight를 조정하지 말고, 다음에는 disjoint
   fit/validation corpus와 target·ligand·scaffold leakage audit를 먼저 고정한다.
   다음 독립-host 실행에는 installable external-ranking reproduction 계약을
   사용한다. 실행 전에 accepted baseline intake/test-partition/evaluation chain,
   정확한 wheel과 구현 source member, 서로 다른 baseline/external host·operator
   identity, single-use nonce를 work order에 고정한다. 외부 결과는
   archive-intake·strict preparation·RCSB/Pfam의 세 public-input root는 그대로
   사용하되 ranking intake·test partition·evaluation과 Vina/GNINA/Smina의
   execution/evaluation receipt·file root 6쌍을 모두 새로 만들어야 한다.
   verifier는 failure를 포함한 924개 engine×case row, 고정 score, Top-K,
   aggregate/family metric·CI, source-validity count를 전수 비교한다. 현재는 실제
   외부 host/operator identity와 custody evidence가 공급되지 않아 production
   work order/result를 만들지 않았다. same-host exact verify는 독립 재실행이
   아니며 physical-host·nonce custody review와 independent reviewer 승인은
   별도 gate로 계속 남는다.
   별도 rigid diagnostic은 lowest-index graph-matched native record로 pocket center를
   정의하고 seed orientation을 고정 회전한 뒤 모든 candidate의 geometry score·validity·
   receptor-frame symmetry-aware RMSD와 oracle-best generation gap을 보존한다. 초기
   diverse score Top-K에는 deterministic rigid coordinate descent를 적용하고 모든
   accept/reject trace를 보존한 뒤 다시 ranking한다. 이 geometry refinement는 힘장
   최소화가 아니다. 이 4-case는 개발에 사용됐으므로 disjoint scientific holdout이
   아니며 torsion·supported-force-field refinement·charge-aware physics·external
   baseline·독립 재실행 전에는 benchmark claim을 열지 않는다.
   별도 bounded molecular torsion materializer는 모든 source bond 행을 보존하고
   non-ring/non-terminal heavy single-bond bridge와 좁은 amide-like exclusion만
   구현했다. zero-angle coordinate reconstruction과 bond-length 보존은 검증하고,
   별도 failure-complete flexible 4-case diagnostic에서 receipt와 함께 사용한다.
   candidate 0의 zero-torsion seed baseline 뒤 deterministic uniform torsion을
   sampling하고, 1-2/1-3 pair를 제외한 고정 원소 반경 nonbonded self-overlap을
   ranking term으로 기록하며 최종 selection 전에 invalid pose를 제외한다. 그러나
   ring closure·torsion energy·bonded force-field strain·torsion refinement·독립
   conformer science를 제공하지 않는다.
9. 완료된 H5 parameter-origin/runtime-envelope record를 유지한다. 이 record는
   caller-supplied 값과 기존 reviewed Sage candidate identity를 분리하고 code-enforced
   execution admission을 scientific applicability와 분리한다. production parameter
   fitting·calibration 또는 validation study는 독립 승인 gate 전에는 시작하지 않는다.
10. 완료된 CPU reference energy/force contract-validation protocol을 유지한다.
   synthetic fixture/mutation/case identity, 사전 float64 threshold, failure-inclusive
   denominator와 H5 dependency, exact materializer·independent oracle source binding,
   signed independent-review attestation과 single-run authorization receipt 계약은
   고정하고 CPU execution-environment/result-receipt 형식도 고정하지만 actual
   attestation/receipt, trusted reviewer/operator key, production nonce reservation/root,
   production environment receipt·runner start/result receipt, kernel-enforced network
   isolation, external receipt authenticity가 없다. Energy-force Ed25519 post-result-review
   leaf 계약과 upstream 공개키 전용 Ed25519 chain은 구현됐지만 실제 receipt/review
   attestation/trusted key·independent 승인과 dependency-manifest 독립 재검증이 없으므로
   실행과 parameter-fitting proposal은 계속 fail-closed한다.
   공통 production-evidence base와 additive companion은 permit→status→review→authorization
   4-event exact raw-byte custody와 seq5 reservation commit-attestation primitive를
   제공하고 same-epoch quorum 및 adjacent epoch-transition continuity 검증기도
   구현했지만 실제 key/carrier/event/registry/proof를 provision하거나 external CAS,
   one-use permit·nonce·predecessor slot 소비, 외부 witness locking·independent journal
   agreement, successor uniqueness, realm-wide non-equivocation을 증명하지 않는다.
   다음 구현 slice는 이 test-only 증거를 승격하지 않고 외부 locking/journal 비교와
   실제 transition/registry proof를 결속한 뒤 process launch identity와 chain을
   environment 이후 전 단계에 연결해야 한다.
   별도 bounded CPU float64 minimizer는 deterministic backtracking, failure row와
   checkpoint/restart 계약까지 구현됐지만 독립 minimization reference·검증 protocol과
   reviewed parameter/applicability evidence가 아니므로 이 차단을 해제하지 않는다.
   별도 bounded per-term diagnostics는 frozen evaluator를 보존한 채 component force와
   non-periodic virial을 계산하지만 periodic cell-strain virial과 독립 reference가 없고
   자체 중앙차분 구현 evidence이므로 같은 과학 차단을 해제하지 않는다.
   별도 versioned improper·constraint 경로는 symmetric degree-relaxed position
   projection, constraint-tangent force, projected Armijo minimization과 exact
   checkpoint/restart까지 연결됐지만 atomic mass를 사용하지 않고 reviewed parameter·
   general assignment·독립 constrained-minimization evidence가 없으므로 같은 과학
   차단을 해제하지 않는다.
   별도 fixed-effective-radius polar GB 경로는 Still pair function의 bounded
   self/pair energy·exact force와 v2 결합 evaluator까지 구현됐지만 radius를
   geometry에서 추정하지 않고 nonpolar·salt/ion·PBC·MD 통합과 independent
   solvation·solvated-minimization evidence가 없으므로 명시된 제한 범위를 넘어
   승격하지 않는다.
   별도 CPU minimization validation protocol은 위 세 minimization lane의 ordered
   14-case·사전 10개 metric·source identity·failure denominator와 independent-reference
   분리 요구사항을 고정하고, exact materializer가 11개 fixture·14개 case를 결과 없이
   CPU float64 runtime input으로 투영한다. 별도 표준 라이브러리 독립 reference와
   artifact binding은 constraint/tangent-force projection·fixed-Born·bounded
   backtracking·fail-closed identity·exact checkpoint/restart를 구현하고 exact source와
   import 경계를 고정한다. 그러나 test-only 비교는 validation 결과가 아니며 독립 과학
   review attestation 계약은 author/reviewer identity 분리·ordered algorithm/limitation
   확인·외부 trusted key·bounded freshness를 고정할 뿐 실제 attestation이나 key를
   포함하지 않는다. 별도 execution-environment/result-receipt 계약은 CPU-only·network-
   disabled 환경과 ordered 14-case·10-metric·양쪽 구현 input identity·failure row 보존을
   고정한다. 별도 single-run authorization 계약은 verified review·pairwise-distinct operator·
   exact code/runner/dependency/receipt-contract identity·24시간 최대 유효기간·revocation·
   one-time nonce를 결속하지만 operator key·signed receipt·nonce reservation·environment/
   result receipt·runner 또는 관측값은 포함하지 않는다. 별도 local POSIX primitive는 raw
   signed review/authorization을 다시 확인하고 caller-provisioned mode-0700 root에
   `O_EXCL`·`O_NOFOLLOW`·mode-0600 canonical record·file/directory `fsync`로 nonce를
   한 번만 소비하며 release/delete API는 제공하지 않는다. 그러나 production root·key·
   signed artifact·reservation은 bundle하지 않는다. 별도 run-start primitive는 raw
   signed chain과 durable nonce를 다시 교차검증하고 실제 Linux x86_64 CPU process의
   Python·Torch·NumPy·GPU visibility·locale·seed·thread·determinism·logical argv·network
   namespace를 관측한다. 동일 operator와 exact authorization/root/namespace에 결속된 최대
   5분 network-isolation attestation을 검증한 뒤 separate private root에 `O_EXCL`·
   `O_NOFOLLOW`·mode-0600 canonical environment receipt·file/directory `fsync`로 한 번만
   기록한다. library는 network namespace나 kernel isolation을 만들지 않고 future bootstrap
   path만 고정하며 production key·attestation·root·receipt·runner를 bundle하지 않는다.
   따라서 review·실행 승인·production result receipt와 결과가
   없으므로 minimization validation 차단을 해제하지 않는다.
   별도 OpenMM Reference offline oracle은 product import와 분리된 lazy optional
   dependency로, frozen 27/59의 47개 지원 variant와 14-case의 8개 지원 operational
   trace를 같은 사전 max/RMS 기준으로 재평가하고 모든 N/A failure row를 보존한다.
   complete wheel/native/environment identity와 fixed-Born self/pair를 canonical receipt에
   결속하지만 현재 실행은 test-only development observation이다. 별도 installable
   native-minimization workflow는 8개 OpenMM L-BFGS endpoint와 6개 N/A failure 행을
   보존하고 동일 endpoint 좌표에서 Engine v2를 재평가한다. frozen configuration은
   `6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`다.
   2026-07-24 local receipt
   `7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`는
   same-coordinate mapping 8/8과 energy nonincrease 8/8을 통과했지만, final constraint
   projection 뒤 fixed-Born constrained 2건의 tangent-force 기준 실패로 6/8이며
   rejected다. 별도 installable failure-disposition workflow는 exact rejected
   materialization/native receipt를 입력으로 2-case/16-probe를 실행한다. v1 reporter
   관측은 endpoint 마지막 비트 차이로 자체 exact-baseline gate에서 rejected였고,
   v2는 probe와 threshold를 유지한 채 no-reporter control을 분리했다. v2
   configuration/actual receipt SHA-256은
   `ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`·
   `870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`다.
   두 alias 모두 projection 전 tangent force 통과·constraint residual 실패,
   projection 뒤 constraint residual 통과·tangent force 실패의
   `final_constraint_projection_tradeoff_observed`로 exact 일치했다. iteration
   64–1024와 optimizer tolerance `1e-8`–`1e-12`에서도 해소되지 않았다. 이는
   failure disposition만 완결하며 frozen 6/8 rejection, causal-root-cause blocker와
   S0 차단을 유지한다. endpoint·trajectory equivalence나 S0 승격을 주장하지 않는다. 별도 Ed25519 external
   result-review verifier는 두 Engine review와 두 OpenMM receipt, exact output/trace 및
   host/CPU/session/custody identity를 fail-closed로 결속하지만 실제 key·attestation은 없다.
   따라서 signed production receipt, 두 CPU host 재현, 외부 custody와 최종 human
   acceptance가 생기기 전에는 S0의
   `independent external implementation comparison` 종료 조건을 충족한 것으로 보지 않는다.
11. 과학적으로 검증된 CPU energy·force·minimization 이후 structure metric과
   torsion-aware docking으로 진행한다.
12. PBC·long-range·solvent·MD, production AI, ROCm/HIP, 제품 route는 각 선행
   gate가 닫힌 뒤 독립 capability로 진행한다.

## 6. V2-2 이후 요구사항

### V2-2 — 독립 CPU 힘장과 최소화

- bond, angle, proper, improper, constraint schema
- vdW, short-range electrostatics와 명시된 solvation 범위
- atom typing, charge·parameter provenance와 applicability domain
- 독립 parameter fitting/versioning
- deterministic minimization과 checkpoint/restart
- per-term energy·force·virial diagnostics

종료에는 finite-difference force, translation/rotation/permutation invariance,
parameter coverage, 독립 reference, minimization decrease/failure evidence가 모두
필요하다. 현재 reference physics, deterministic minimizer와 per-term numerical
diagnostics는 bounded unvalidated scaffold이며, checkpoint/restart·central-difference
force·non-periodic virial 구현 자체는 위 종료 evidence를 충족하지 않는다.
fixed-radius polar GB 구현도 명시된 provisional solvation 범위일 뿐 radius estimation,
nonpolar·salt/ion·PBC, parameter coverage와 독립 reference evidence를 충족하지 않는다.
frozen minimization validation protocol, exact result-free materializer, source-bound
독립 reference도 production 실행 결과나 independent scientific review evidence가
아니며, case·metric·runtime input/source identity와 test-only endpoint 비교만으로 V2-2
종료를 주장하지 않는다.

### V2-3 — 구조분석·도킹

정확히 정의된 quality/pocket/interface/mutation metric, conformer·torsion tree,
global search, local refinement, diverse top-k, symmetry-aware clustering,
pose validity와 독립 physics score를 구현한다. public holdout protocol과 threshold는
결과를 보기 전에 고정하며 모든 failure row를 denominator에 남긴다.
현재 parameter-bound chemistry-aware validity는 exact pose·problem·force-field
identity, Lorentz--Berthelot 기반 receptor--ligand 및 topology-exclusion-aware
ligand self clash, attractive/repulsive partial-charge Coulomb, signed strain을
한 결과에 결속한다. 다만 strain·repulsion 한계는 caller-declared unfitted
policy이고 aromatic-specific·declared stereo·metal/cofactor coverage, public
generated-pose calibration과 독립 검토가 없으므로 validated pose validity로
승격하지 않는다.
별도 reference-docking applicability assessment는 exact system·topology·problem·
config·parameter identity를 결속하고 invalid input, metal/cofactor, formal/partial
charge, parameter coverage, dtype/model/cell/capacity blocker를 첫 예외에서
유실하지 않고 함께 보존한다. scorer는 `admitted_diagnostic`에서만 생성하며
aromatic/stereo 입력은 실행되더라도 interaction coverage incomplete와 OOD로
남는다. 이 실행 admission은 scientific chemical domain이나 validated
refinement 승인이 아니다.

### V2-4 — PBC·용매·MD

differentiable image shift, explicit water/ion, validated PME 또는 조건부 FMM,
constraint solver, NVE/NVT/NPT integrator, trajectory/restart와 drift/distribution
진단이 필요하다. tiny reference 밖 direct Coulomb all-pairs는 금지한다.
현재는 caller-supplied mass·parameter를 쓰는 deterministic CPU `float64`
velocity-Verlet NVE, force 평가별 compact neighbor-list 재구축, full 3D
orthorhombic PBC wrapping, canonical-pair inverse-mass SHAKE와 RATTLE,
constraint residual·iteration provenance, binary64 trajectory chain, exact
checkpoint/restart, 그리고 중성 CPU `float64` orthorhombic cell에서 screened
Coulomb을 real·reciprocal·self·exclusion/1-4 correction으로 교체하는 bounded
direct-Ewald 선택 경로까지 구현됐다. 이는 constraint/mass assignment,
drift·Ewald convergence acceptance, 독립 SHAKE/RATTLE/Ewald 비교나 독립·두-host
재현 결과가 아니며 PME, net-charge background, 독립 승인된
thermostat/barostat·NVT/NPT 통계, triclinic PBC, CPU/GPU parity와 제품 승격은 계속
차단된다.
별도 bounded preparation은 exact Amber TIP3P/Joung--Cheatham Na+/Cl- source
snapshot을 고정하고 water/ion topology·parameter·intrawater exclusion·rigid-water
constraint·full orthorhombic PBC·중성화·molarity·clearance·canonical placement
trace를 생성한다. 중성/반대이온 case는 실제 direct-Ewald와 constrained-NVE
restart까지 실행된다. 다만 초기 lattice는 미평형이며 독립 source 전사 검토,
external energy/force parity, 물/이온 관측량, 두-host 또는 과학 acceptance receipt는
없다.
동일 force·constraint·PBC·explicit-particle stack 위에 constrained BAOAB
Langevin NVT와 molecular-centre isotropic Monte Carlo NPT를 제공하는 bounded
canonical-ensemble 경로도 구현했다. seeded counter RNG 위치, 가변 cell, 모든
barostat proposal/disposition, energy·coordinate·volume·finite-difference
molecular-pressure trace와 trajectory/barostat hash head가 canonical
pause/serialize/resume에서 보존된다. 별도 all-step 분석은 autocorrelation time,
effective sample size, confidence interval, target bias, constraint residual,
acceptance count/fraction, exact restart와 사전 선언된 모든 실패 metric을 기록한다.
이는 thermostat/barostat/statistics 구현 표면만 닫는다. 독립 integrator·pressure
비교, 검토된 burn-in/threshold, production-length 액체·ion 분포,
density/compressibility/heat capacity, 두-host 재현과 CPU/GPU parity는 계속
필수다.
또한 모든 evaluated frame과 실제 pause/resume 재실행을 요구하고 energy·momentum
max/RMS·slope, instantaneous kinetic temperature, 현재 constraint residual,
trajectory byte identity, exact restart, 실패 포함 사전 9개 metric 행을 기록하는
bounded NVE drift 분석 계약을 추가했다. 이는 관측 가능성 구현일 뿐 독립 검토된
threshold, external integrator 비교, 두 CPU host receipt 또는 accepted drift
evidence가 아니다.

### V2-5 — Production AI

license·split provenance가 있는 dataset, scalar residual-energy model,
TorsionTopologyGNN, bounded-window TemporalStateGNN, PINN release gate,
calibration·OOD abstention과 signed checkpoint/model card를 요구한다.

### V2-6 — ROCm/HIP

CPU reference가 freeze된 뒤 실제 AMD GPU에서 kernel별 value·gradient·ranking,
overflow, determinism, peak memory, scaling과 soak evidence를 수집한다.

### V2-7 — 독립 상용 로컬 제품

clean-machine offline install, upgrade/rollback, job recovery, 3D viewer/report,
tenant/path/secret isolation, signed manifest와 capability allowlist가 필요하다.
과학·benchmark·GPU·제품 gate를 통과하지 않은 기능은 고객 route에서 비활성화한다.

## 7. 검증과 승격 게이트

모든 capability는 다음 게이트를 독립 통과해야 한다.

1. 계약: schema, unit, identity, provenance, canonical hash, fail-closed
2. 수학: sparse bound, invariance/equivariance, parity, finite difference
3. 과학: parameter coverage, conservation, ensemble/pose/metric, uncertainty
4. benchmark: frozen public holdout, row/failure evidence, CI와 threshold
5. GPU: 실제 CPU/ROCm value·gradient·ranking·memory·scaling parity
6. 제품: 설치, 복구, 보안, 보고서, scope 표시와 customer shadow

모든 evidence는 input/result SHA-256, command, seed, Git commit, environment,
dataset/split/parameter/checkpoint version, 개별 row와 failure row, 사전 고정
threshold, uncertainty, reviewer와 supersession/revocation 상태를 포함해야 한다.

## 8. 현재 claim boundary

다음은 별도 reviewed evidence가 생기기 전까지 모두 false다.

- `claim_safe`
- `atom_site_identity_joined`는 declaration-only profile에서 false이며, bounded
  observation profile의 selected source identity join에서만 true
- `scientifically_validated`
- `benchmark_validated`
- `customer_execution_enabled`
- `scientific_validation`
- `public_benchmark_validation`
- `gpu_parity`
- `customer_execution`
- `commercial_readiness`

bounded source·topology·preparation graph test green은 parameterability,
scientific validity, docking accuracy, MD, GPU parity 또는 commercial readiness가
아니다.
고정된 CPU reference validation protocol도 실행 결과가 아니며 force/energy accuracy,
scientific applicability, minimization 또는 parameter fitting 승인을 뜻하지 않는다.
bounded deterministic minimizer와 bit-exact restart test도 독립 minimization 검증이나
과학적 applicability 증거가 아니다.
per-term central-difference force와 non-periodic configurational virial diagnostics도
independent reference, periodic pressure/stress 또는 과학 검증 증거가 아니다.

## 9. 제품 성숙도

| 상태 | 진입 조건 | 외부 제공 정책 |
|---|---|---|
| Scaffold | contract·unit test | 개발자 내부 |
| Internal alpha | capability 수학 gate | internal synthetic/curated input |
| Scientific beta | 과학 gate+frozen benchmark | 제한 평가자, claim 범위 명시 |
| Customer shadow | 실제 입력 병렬 평가 | 의사결정·자동 업무 사용 금지 |
| Release candidate | 보안·설치·복구·성능 gate | 명시 범위 pilot |
| Commercial release | capability 승인+운영 sign-off | 승인 capability만 활성화 |

## 10. 결정 기록

- 외부 molecular solver는 customer runtime이 아니라 offline oracle이다.
- v2 과학 core는 `betelgeuze_engine_v2/`가 소유한다.
- source token 보존과 scientific interpretation을 분리한다.
- AI는 sparse non-attention residual-energy 구조를 기본으로 한다.
- force는 scalar energy의 exact reverse-mode gradient다.
- conditional `O(N)`의 hard cap과 overflow를 숨기지 않는다.
- CPU reference를 먼저 고정하고 GPU parity는 실제 ROCm 장비에서 증명한다.
- 미승격 capability는 제품에서 기본 비활성화한다.

## 11. 관련 문서

- `config/independent_engine_v2_capabilities.yaml`: machine-readable 현재 상태
- `docs/engine_v2_status.md`: 현재 구현 요약
- `docs/roadmaps/engine-v2-scientific-evidence-roadmap.md`: evidence 단계와 승격 규칙
- `docs/engine_v2_public_api.md`: API 안정성·provisional boundary
- `docs/engine_v2_pr_overlap_matrix.md`: donor 폐기와 current-main 재구성 기록
- `docs/roadmaps/2026-07-repository-recovery-and-engine-roadmap.md`: 저장소 복구 결정

phase 완료 표시는 구현 코드, focused/failure 테스트, main CI, machine-readable
capability blocker와 필요한 row-level evidence가 함께 바뀔 때만 갱신한다.
