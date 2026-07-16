# Independent Engine v2 독립 상용화 장기 로드맵

기준일: 2026-07-16

문서 상태: current-main canonical planning reference; 비실행·비주장 문서

현재 단계: V2-0 독립 CPU 스캐폴드와 V2-1의 bounded source-contract 조각을
구현한 상태다. V2-1 all-atom preparation, V2-2 과학 힘장, V2-3 도킹,
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
| `v2_bounded_mmcif_modified_residue_declarations` | `_pdbx_struct_mod_residue`의 source-declared modified polymer component를 label asym·sequence·component identity와 결속 | atom-site observation·parent chemistry·modification nature·auth/model/insertion semantics·preparation |
| `v2_bounded_mmcif_nonpoly_identity` | nonpoly component/entity/asym/instance alias identity | atom-site join·role·chemistry·topology |
| `v2_bounded_mmcif_nonpoly_component_declarations` | selected component atom과 optional component bond source row | element·charge·aromaticity·stereo·bond order·topology |
| `v2_bounded_mmcif_nonpoly_component_roles` | `_entity.type`, `_chem_comp.type`, component element·formal-charge composition으로 source water와 단원자 metal/nonmetal ion 경계를 보수적으로 분류 | general ligand·cofactor·nonpoly modified-residue 역할, metal coordination chemistry, ion/metal preparation |
| `v2_bounded_mmcif_struct_conn_declarations` | selected 23-field `_struct_conn` row의 nonpoly instance·component atom identity join | connection type·symmetry·order·covalence·coordination·topology |
| `v2_bounded_mmcif_nonpoly_atom_site_observations` | exact 21-field `_atom_site`에서 selected nonpoly instance·component atom과 `_struct_conn` endpoint observation join | coordinate numeric value·geometry·occupancy·B-factor·formal charge·topology |
| `v2_bounded_mmcif_nonpoly_coordinate_values` | selected `Cartn_x/y/z` 원문 spelling·finite binary64 값·exact bit pattern 결속 | coordinate unit·geometry quality·distance·clash·occupancy·B-factor·formal charge·topology |
| `v2_bounded_mmcif_nonpoly_atom_site_scalar_values` | occupancy·B-factor·formal charge의 known/unknown/not-applicable 상태와 bounded numeric value 결속 | occupancy population·B-factor quality·charge chemistry·altloc·topology |
| `v2_bounded_mmcif_nonpoly_canonical_topology` | component SING/DOUB/TRIP/QUAD/AROM bond와 identity-symmetry `covale` Bond, 별도 `metalc` coordination edge | 비identity symmetry·hydrog·disulf·DELO/PI/POLY·원소/charge/aromaticity chemistry |
| `v2_bounded_mmcif_nonpoly_neutral_coh_preparation` | neutral acyclic C/O/H component의 single/double bond graph, 명시적 0 formal charge, fixed-valence hydrogen completion과 instance별 failure-complete parameterability report | hydrogen 좌표·reviewed parameter·`AllAtomSystem`·charged/aromatic/stereo/extended-element/cyclic/pH/tautomer/intercomponent preparation |
| `v2_bounded_mmcif_nonpoly_preparation_corpus` | SHA-256으로 고정한 exact ASCII 26-case synthetic contract corpus와 51-axis executable coverage ledger; supported 16·explicitly unsupported 24·not implemented 11 | real-world supported corpus·parameter fitting·V2-1 종료·과학/benchmark/product 승격 |

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

bounded topology capability는 component bond order·aromatic flag·E/Z stereo를
명시적으로 교차검증한다. `_struct_conn`의 identity-symmetry `covale`만 explicit
order로 canonical Bond를 만들고 `metalc`는 Bond가 아닌 coordination edge로
남긴다. 비identity symmetry, `hydrog`, `disulf`, DELO/PI/POLY는 fail-closed다.

bounded preparation capability는 neutral acyclic C/O/H와 single/double component
bond로 범위를 고정한다. source element·formal charge·nonaromatic·stereo 상태를
교차검증하고 fixed neutral valence로 hydrogen-completed chemical graph만 만든다.
모든 instance는 실패 원인을 보존하는 parameterability report를 가지며,
hydrogen 좌표·reviewed parameter source·`AllAtomSystem`이 없으므로 항상
`parameterable=false`다. 이는 pH-dependent protonation, tautomer selection,
과학적 chemistry validation 또는 실행 가능한 all-atom preparation이 아니다.

bounded preparation corpus는 26개 입력과 기대 결과를 개별 SHA-256으로 고정한다.
지원 그래프 3개, intercomponent preparation 차단 1개, 명시적 미지원 chemistry
18개, upstream policy 차단 2개, invalid-source 2개를 모두 실행하고 failure row를
denominator에서 제거하지 않는다. 51-axis coverage ledger는 16개 supported,
24개 explicitly unsupported, 11개 `not_implemented`로 분류하며 unclassified
row는 0이다. 이 분류 완전성은
기능 완전성이나 과학적 corpus coverage가 아니다. 따라서
`parameter_fitting_allowed=false`, `v2_1_exit_ready=false`를 유지한다.

nonpoly atom-site의 explicit `label_alt_id` 입력은 현 observation profile이
dot/question marker만 허용하므로 chemistry preparation 전에 fail-closed된다.
corpus는 이 입력과 안정 error code를 고정하지만 conformer를 선택하거나 occupancy
population, missingness 또는 altloc chemistry를 해석하지 않는다.

PDB·SDF V2000 bounded ingest도 존재하지만 general PDB/mmCIF/SDF/SMILES,
biological assembly, multimodel execution·ensemble semantics, general missingness,
coordinate-bearing hydrogen
completion, general protonation, tautomer, aromaticity, general ligand/cofactor와
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
   failure-complete parameterability report를 유지한다. 좌표·parameter·
   `AllAtomSystem`, pH·tautomer·aromatic/charged chemistry는 계속 분리한다.
6. 완료된 첫 contract layer로 exact ASCII 26-case synthetic supported/failure
   corpus와 51-axis coverage ledger를 유지한다. expectation mismatch, input hash
   drift, coverage row 누락과 evidence signal 누락은 모두 fail-closed다.
7. 다음으로 11개 `not_implemented` row를 작은 capability별로 닫고,
   licensing·provenance가 명시된 real-world supported/failure corpus를 추가한다.
   우선순위는 general ligand/cofactor 역할, assembly/insertion/missingness 정책,
   coordinate-bearing hydrogen,
   parameter provenance와 canonical `AllAtomSystem`이다.
8. 위 gap과 real-world corpus가 닫히기 전에는 V2-2 parameter fitting·validation을
   시작하지 않는다.
9. 과학적으로 검증된 CPU energy·force·minimization 이후 structure metric과
   torsion-aware docking으로 진행한다.
10. PBC·long-range·solvent·MD, production AI, ROCm/HIP, 제품 route는 각 선행
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
필요하다. 현재 reference physics는 bounded unvalidated scaffold다.

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
