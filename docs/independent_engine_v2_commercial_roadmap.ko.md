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
완료한 상태다. Production receipt와 independent result review는 포함하지 않는다.
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
| `v2_frozen_public_benchmark_protocol` | PoseBusters 공식 저장소 고정 commit의 packaged PDB example 4건에 대해 external receptor/reference/ligand-identity-seed SHA-256, MIT·RCSB CC0 license metadata, seed 좌표를 무시하는 fixed-receptor-frame 2 Å symmetry-aware direct RMSD·bounded validity endpoint, all-case failure denominator와 scorer source SHA-256을 고정한 protocol definition | raw data bundling·network fetch·benchmark 실행/결과/발표 승인, ligand-only alignment, 통계적 대표성, PoseBusters Benchmark 동등성, 법률 판단, 과학/benchmark/product 승격 |
| `v2_h5_reference_physics_parameter_applicability_record` | caller-supplied explicit parameter origin, 구현된 5개 energy term·mixing/switch/pair semantics, code-enforced topology·neighbor·orthorhombic-PBC·capacity admission, 7개 runtime source SHA-256을 고정한 H5 record | production parameter set, Sage-to-runtime value binding, OFFXML parsing·assignment, scientific chemical applicability, fitting·calibration·force/energy validation, physics/customer 실행 승인 |
| `v2_bounded_cpu_reference_minimization` | single-model CPU float64 입력과 caller-supplied explicit parameter에 한정한 deterministic force-steepest-descent, Armijo backtracking, iteration/backtrack/displacement/neighbor hard bound, failure-inclusive evaluation row, source/topology/parameter/config identity와 exact little-endian binary64 좌표를 결속한 checkpoint/restart | production parameter set·assignment, general chemistry/applicability, improper·constraint·long-range·solvation, 독립 minimization reference/validation, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_reference_term_diagnostics` | unchanged frozen evaluator의 5개 component energy를 single-model CPU float64의 모든 `6N` plus/minus perturbation에서 중앙차분해 per-term force를 만들고 analytic total force 합계·component net force를 검증하며, non-periodic 입력에 `sum((r-r_center) outer F)` configurational virial·대칭성·uniform-strain derivative를 제공 | independent scientific reference, parameter/applicability validation, pressure/stress, periodic cell-strain virial, improper·constraint·long-range·solvation, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_reference_improper_constraint_extension` | frozen v1 evaluator·parameter source를 변경하지 않는 별도 versioned schema에서 ordered-star `asin` out-of-plane harmonic improper energy·autograd force와 simultaneous equal-weight degree-relaxed Jacobi distance projection을 제공하고, single-model CPU float64에서 초기 상태와 모든 trial을 제약면에 투영한 뒤 bounded iterative tangent-force projection과 실제 projected displacement Armijo 감소를 적용하는 constrained minimization·exact checkpoint/restart를 제공; position/force iteration·pair correction·capacity hard bound, minimum-image PBC distance, 모든 nested residual/failure row와 identity digest를 보존 | reviewed parameter·general improper/constraint assignment와 coverage, atomic-mass-weighted constraints, independent force·constraint·constrained-minimization validation, long-range vacuum electrostatics·fixed-radius polar GB 이외 solvation, MD integrator 연계, 과학·benchmark·product/customer 승격 |
| `v2_bounded_cpu_fixed_born_polar_solvation` | Still DOI `10.1021/ja00172a038`의 `sqrt(r² + alpha_i alpha_j exp(-r²/(4 alpha_i alpha_j)))` pair function을 고정하고, exact topology·v2 charge-parameter fingerprint·caller radius-source SHA-256에 결속된 전 원자 fixed effective Born radius로 non-periodic single-model CPU float64 polar dielectric-transfer self/pair energy와 autograd force를 계산하며 v2 energy/force 결합 evaluator와 solvation fingerprint를 결속한 optional constrained minimization·exact checkpoint/restart를 제공; 512 atom·130816 pair hard bound와 minimum-distance admission 적용 | effective Born radius geometry 추정·reviewed radius/charge parameter와 applicability, nonpolar solvation, salt·explicit ion, PBC solvent, MD 통합, independent solvation·solvated-minimization reference/validation, 과학·benchmark·product/customer 승격 |
| `v2_cpu_reference_minimization_validation_protocol` | unsolvated v1·constrained v2·fixed-Born constrained v2·checkpoint/restart·identity/applicability failure의 ordered 14-case, CPU float64 사전 10개 metric, all-case failure denominator, exact minimizer/evaluator source SHA-256와 independent-reference import 분리 요구사항을 결과 전에 고정한 execution-disabled protocol; 별도 exact materializer와 source-bound 표준 라이브러리 독립 reference를 구현하고, HMAC-SHA256 independent-review attestation·CPU-only network-disabled execution-environment/failure-inclusive result-receipt·single-run authorization 계약을 고정함; 별도 local POSIX atomic reservation primitive가 raw signed review/authorization을 재검증하고 caller-provisioned mode-0700 root에 `O_EXCL`·`O_NOFOLLOW`·mode-0600 canonical record·file/directory `fsync`로 one-time nonce를 소비하며 release/delete API는 없지만 실제 key/attestation/authorization receipt/production root/reservation/runner/result는 bundle하지 않음 | 실제 independent scientific review와 attestation/trusted key, signed authorization receipt·trusted operator key·production nonce reservation/root, trusted environment receipt·run-start·runner, production result receipt·independent result review, reviewed parameter/applicability, validation 실행·결과·parameter fitting·과학/제품 승격 |
| `v2_cpu_reference_energy_force_validation_protocol` | 7개 synthetic fixture profile·20개 mutation contract·27개 ordered pass/fail-closed case·19개 float64 metric·H5 dependency·failure-inclusive denominator를 고정하고, 59개 deterministic CPU float64 variant의 exact materializer, frozen reference evaluator source, evaluator/protocol/third-party import를 금지한 standard-library analytic oracle, signed independent-review attestation, operator-signed single-run authorization, CPU execution-environment/result-receipt schema, oversized payload를 path 생성 전에 거부하는 local POSIX atomic nonce reservation, live CPU process와 짧은 수명의 signed network-isolation attestation을 재검증해 mode-0600 environment receipt를 기록하는 run-start primitive, source-only Python import와 Git replacement-ref 거부를 포함한 root-owned absolute Git read-only preflight로 실제 clean HEAD·signed runner source·frozen evaluator/materializer/oracle·dependency를 다시 확인하고 one-time start marker를 소비하며 manifest와 materialization/evaluator/oracle을 고정 supervised child에서 실행해 native stall까지 parent hard deadline으로 중단하고 모든 성공·실패를 메모리에 보존하는 120초 제한 CPU float64 runner, trust key를 받지 않는 bounded canonical stdin과 저장소가 bundle하지 않는 고정 `/etc` root-owned mode-0600 외부 trust store만 사용하는 exact module entrypoint, raw signed chain·live environment·runner-start·exact observation을 재검증하고 metric/status·filename/embedded nonce·special-file read를 fail-closed하며 실패 행 전체를 mode-0600 canonical receipt 하나에 원자적으로 보존하는 result writer/verifier를 유지 | 실제 independent scientific review와 independent result review, trusted reviewer/operator key 또는 production trust store/receipt bundling, production reservation/artifact root와 실제 nonce/environment receipt/runner start/result receipt, kernel-enforced network isolation과 same-UID replacement resistance, externally authenticated receipt signature, production validation result collection, reviewed runtime parameter values, scientific holdout/applicability, energy/force/minimization validation, parameter fitting·제품 승격 |

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
관측 전에 고정한다. harmonic bond/angle, proper torsion, Lennard-Jones,
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
reviewer key, HMAC-SHA256 integrity와 최대 30일 validity를 요구한다. 저장소는 trusted
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
최대 5분의 HMAC-SHA256 network-isolation attestation을 외부 trust anchor로 검증한 뒤
private artifact root 아래 mode-0600 canonical environment receipt 하나를 `O_EXCL`과
file/directory `fsync`로 기록한다. 실제 path와 secret-bearing argv는 기록하지 않고,
library 자체는 network namespace를 만들거나 kernel isolation·same-UID resistance를
확립하지 않는다. production key·attestation·root·receipt는 bundle하지 않으며 생성된
receipt도 production validation execution, fitting 또는 과학 주장을 승인하지 않는다.
별도 bounded runner는 persisted receipt와 live process, validation dependency import
전에 실행되는 stdlib-only `-I -S -B -X pycache_prefix=/dev/null` bootstrap,
replacement ref를 비활성화·거부하는 root-owned absolute Git read-only preflight가 증명한
clean HEAD·bootstrap과 runner를 함께 묶은 signed runner source·frozen evaluator/materializer/oracle
source·dependency를 다시 확인하고 nonce별 mode-0600 runner-start marker 하나를
`O_EXCL`·file/directory `fsync`로 소비한다. Frozen manifest는 marker 소비 전 supervised
preflight child에서 만들고 남은 budget을 다시 확인한 뒤에만 marker를 소비한다. 이후 CPU float64 27개 case·59개 variant는 고정 case worker에서
순서대로 평가한다. Parent의 120초 hard deadline은 Torch/native stall도 worker kill로
중단하며 worker 내부 POSIX timer는 보조 경계로 유지한다. threshold failure, expected fail-closed row,
unexpected evaluator failure와 미관측 metric까지 canonical in-memory observation에 모두
보존한다. exact process command는 absolute checked-out bootstrap path만 사용하며
`PYTHONPATH`·user-site override와 `sitecustomize`·`.pth` 실행을 무시하고 root-owned
read-only dependency root만 허용한다. Package initializer import 전에 bounded canonical
stdin의 external operator HMAC, signed commit/source와 clean checkout을 검증하며 reservation/artifact root는
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
별도 frozen receipt 계약은
CPU-only·network-disabled Linux 환경, Python 3.10–3.12, Torch 2.6.0, NumPy 1.26.4,
empty GPU visibility, deterministic seed/thread/argv/dependency와 confined artifact path를
고정하고 27개 case·59개 variant·19개 metric 전체의 failure-inclusive 결과 형식을
고정한다. 그러나 production environment receipt·runner start, durable observed value 또는
result receipt는 포함하지 않는다. 따라서 독립 과학 review·independent result review·
author separation attestation·signed authorization은 아직 없다. synthetic 값은 parameter-fit data가 아니며 scientific parameterized-force-field
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
8. 완료된 four-case public benchmark protocol/manifest의 exact source·license
   metadata·endpoint·failure denominator·scorer identity를 결과 실행·발표 없이
   유지한다.
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
   isolation, external receipt authenticity와 independent result review가 없으므로
   실행과 parameter-fitting proposal은 계속 fail-closed한다.
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
   signed artifact·reservation은 bundle하지 않는다. 따라서 review·실행 승인·production result receipt와 결과가
   없으므로 minimization validation 차단을 해제하지 않는다.
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

### V2-4 — PBC·용매·MD

differentiable image shift, explicit water/ion, validated PME 또는 조건부 FMM,
constraint solver, NVE/NVT/NPT integrator, trajectory/restart와 drift/distribution
진단이 필요하다. tiny reference 밖 direct Coulomb all-pairs는 금지한다.

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
