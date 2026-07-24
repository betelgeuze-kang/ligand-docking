# 리간드 도킹 및 분자동역학 납품 엔진

[English README](README.md)

이 저장소는 의도적으로 분리된 두 표면을 포함합니다.

1. **Independent Engine v2** — 버전형 분자 계약, 제한된 희소 기하,
   CPU 기준 AI·물리 합성 primitive, 엄격한 checkpoint, 제한형 PDB/SDF
   입력, 도킹 검색 scaffold, 실패 행을 보존하는 benchmark ledger입니다.
2. **레거시·제품 납품 스택** — validated runner, evidence gate, API,
   wetlab packet, CASP/CAMEO 준비, 제한형 로컬 납품 도구입니다.

V2 단거리 기하 경로는 밀도·cutoff·이웃/셀 용량·모델 폭·후보 예산이
고정될 때의 **조건부 제한 차수 `O(N)` 알고리즘 계약**을 갖습니다. 이는
저장소 전체나 장거리 물리의 실측 end-to-end `O(N)` 증거가 아닙니다.

## Engine v2 현재 상태

현재 구현 단계:

```text
v2_0_3_0a1_p0_release_line
```

`0.3.0a1` 정책은 레거시 HIP/ROCm 고객 경로를 명시적으로 비활성화합니다.
GPU parity와 제품 qualification 증거가 확보되기 전까지 Engine v2의 claim
범위는 CPU reference에 한정됩니다.

구현되어 GitHub-hosted CPU CI로 검증되는 범위:

- 정규 all-atom 상태, 검증 단계, SHA-256 identity
- 고정 용량 희소 radius geometry와 periodic image-shift gradient
- 정확한 좌표 미분을 갖는 scalar-energy AI 기준 모델
- matrix-free projection, torsion, temporal, physics gate primitive
- fail-closed CPU 오케스트레이터와 엄격한 runtime/checkpoint fingerprint
- Python 3.10–3.12용 독립 `betelgeuze-engine-v2` wheel
- 단일 모델 PDB와 단일 분자 SDF V2000 제한형 파서
- 독립 physics term registry 계약
- 이전 same-epoch witness quorum을 다시 검증하고 exact ordinal adjacency,
  terminal state root의 변경 없는 sequence-zero genesis 이관, 전체 transition
  context에서 유도한 checkpoint, 동일 statement에 대한 상이한 이전/다음
  Ed25519 quorum을 요구하는 verifier-only 인접 registry-epoch 전환 계약. 실제
  proof/key는 포함하지 않으며 successor uniqueness·witness locking·독립 journal
  일치·realm-wide non-equivocation·실행·모든 과학/제품 claim은 계속 미확립
- failure row와 exact checkpoint/restart identity를 보존하는 bounded
  deterministic CPU `float64` reference minimization; 과학·제품 승격은 없음
- force 평가마다 compact neighbor list를 재구축하고 full 3D orthorhombic PBC와
  좌표 wrapping, canonical pair 순서의 inverse-mass SHAKE 위치 보정과 RATTLE
  방사상 상대속도 투영을 선택적으로 제공하는 bounded deterministic CPU
  `float64` velocity-Verlet NVE. frame/checkpoint는 전체 constraint 설정,
  최대 위치·속도 잔차, 누적 반복 수, binary64 trajectory-chain identity와 동일
  runtime bit-exact 재시작을 결속함. 중성 단일 모델 CPU `float64`·full 3D
  orthorhombic cell에서는 선택적 bounded direct-Ewald reference가 frozen v1
  screened-Coulomb term에 더해지지 않고 이를 정확히 교체함. 명시적 alpha·
  reciprocal-index bound, conducting/tin-foil 경계, shifted real-space·reciprocal·
  self·exclusion·1-4 correction을 NVE config와 restart identity에 결속함.
  설치형 `betelgeuze-engine-v2-openmm-nve-trajectory` offline workflow는
  unconstrained ion-pair와 coupled-constraint water-like 16-step case를 고정하고,
  finite direct-Ewald 합을 OpenMM Reference에 독립 매핑해 매 step energy·force·
  coordinate·velocity, constraint, drift, native-checkpoint restart와 exact
  fail-closed 3행을 보존함. configuration SHA-256
  `2beca32683c0393666cc1c3b5a136bed3416f774b0db631133a04bb43928871e`의
  single-host 후보 관측
  `d60b15992c4179a93e2276d4da380554e3c69a7819f181347aacab11899140cd`는
  물리 2/2와 failure 3/3을 통과함. 이는 bounded implementation comparison일
  뿐이며, 일반 solute constraint/mass 자동 할당, 검증된 parameter, 승인된
  Ewald convergence·장시간 NVE drift, 일반 chemistry/solvent 독립 검증, PME,
  net-charge background, 독립 승인된 thermostat/barostat·NVT/NPT 통계,
  두-host review, triclinic cell·GPU parity·제품 route는 없음
- 설치형
  `betelgeuze-engine-v2-openmm-explicit-solvent-trajectory` offline
  successor는 deterministic materializer를 세 개의 exact 12 Å TIP3P/ion
  case, 4-step constrained NVE/OpenMM trace와 양쪽 restart, salted 3단
  timestep ladder, direct-Ewald reciprocal bound 2/3/4, exact fail-closed
  4행에 결속함. configuration SHA-256은
  `e40902895938a4d7848e5207d0fe29de1ecaa43ae600c9c9ed8f7b7d0ac6c1b5`임.
  single-host 후보 관측
  `d510c9c65625c00f7bd14c134c72e1ed5dab004764efc60c7fd96a9dae223157`은
  전체 물리-case metric에서 의도적으로 0/3을 유지함. OpenMM Reference
  SETTLE의 rigid-water 잔차 최대값 `4.67e-8 Å`이 frozen `1e-9 Å`
  threshold를 넘고, 두 입력은 charged pair가 cutoff equality에 놓여 force
  divergence도 드러냄. Ewald convergence와 negative row 4/4는 통과하지만,
  Engine timestep coordinate monotonic 검사는 `1.44e-11 Å` roundoff 규모에서
  실패로 남음. threshold 완화나 입력 변경 없이 모든 실패를 보존한 rejected
  diagnostic receipt이며, 승인된 explicit-solvent·Ewald·장시간 NVE·과학·
  제품·P2 evidence가 아님. 두 build는 wheel SHA-256
  `3c08913e23dceb49614f97cad03fe872c1a7d072cb15c7437760c566da452b70`으로
  byte-identical했고 설치형 command가 receipt를 재현함
- 설치형
  `betelgeuze-engine-v2-openmm-force-double-rattle-trajectory` development
  successor는 OpenMM Reference를 static force provider로만 쓰고, 별도
  stdlib-only binary64 구현에서 이전 constrained pair vector SHAKE와 projected
  current pair vector RATTLE로 적분함. fresh 13.5 Å·4-water/ion 입력 3개,
  force-active cutoff margin 최소 `0.25 Å`, 16 step과 양쪽 restart, 모든
  energy·force·coordinate·velocity·constraint·projection 관측 및 exact failure
  6행을 결속함. configuration SHA-256
  `ba2c1e99183cc124bb664745dfd1b4cbabbd2d4328cc35754e9e4da044606007`과
  single-host observation
  `cd0b849e206124e11996581c81dcc13da9d11ee3caa1c8176b5525dfead271a6`은
  물리 3/3과 failure 6/6을 통과함. receipt file SHA-256은
  `733af591c5366670a1aba79581648f064b8dccbd50d87b2080d139eb018329f0`임.
  두 build는 wheel SHA-256
  `32e5784ed210f9a62de015a71c18c3fe302f897761b4d740563afb04e9352cab`으로
  byte-identical했고 설치형 CLI가 receipt를 재현함. 그러나 threshold는
  exploratory 작업 뒤
  선택됐고 lattice는 미평형이며 integrator는 외부 독립 유지 구현이 아님.
  따라서 fresh holdout·두-host 재현·독립 review가 필요한 development
  evidence일 뿐이며, rejected SETTLE receipt를 대체하거나 liquid property·
  승인된 장시간 drift·PME·과학/제품 validity·P2 완료를 확립하지 않음
- OpenMM Force Fields Amber TIP3P/Joung--Cheatham Na+/Cl- source snapshot을
  고정하고 water/ion atom·residue·bond·angle·nonbonded value, intrawater
  exclusion, rigid-water SHAKE/RATTLE constraint, full 3D orthorhombic PBC,
  중성도, species molarity, 최소 거리 검사와 canonical placement trace를 실제
  생성하는 bounded deterministic CPU `float64` explicit-solvent preparation.
  중성화된 결과는 direct Ewald·constrained NVE·bit-exact checkpoint/restart로
  실행 검증함. SHA-256 순서 lattice는 minimization·equilibration된 액체가 아니며
  source 전사, 액체 물성·ion 거동·energy/force parity·두-host 재현·과학/제품
  사용은 계속 미검증
- constrained BAOAB Langevin NVT와 선택적 isotropic molecular-centre Monte
  Carlo NPT barostat를 제공하는 bounded CPU `float64` canonical-ensemble MD.
  domain-separated SHA-256 counter random stream, 가변 orthorhombic cell,
  SHAKE/RATTLE 전체 상태, barostat proposal/acceptance 행, energy·coordinate·
  volume·finite-difference molecular-pressure trace와 trajectory/barostat hash
  head를 checkpoint에 결속해 동일 runtime bit-exact restart를 보장함. 별도
  all-step 분석은 initial-positive-sequence autocorrelation, effective sample
  size, normal-approximation confidence interval, target bias, constraint
  residual, barostat acceptance, exact restart와 실패 metric 행을 모두 보존함.
  accepted equilibration/production protocol, 외부 ensemble 비교, 액체 물성,
  두-host 재현, CPU/GPU parity 또는 과학/제품 승격은 없음
- `trajectory_stride=1`인 fresh run과 실제 pause/resume 재실행을 요구하는 bounded
  all-step NVE drift 분석. 모든 energy·kinetic-temperature·linear-momentum·현재
  constraint residual·frame/coordinate/velocity digest 관측, energy·momentum의
  max/RMS와 energy-drift slope, 실패를 포함한 사전 9개 threshold/restart metric
  행을 보존함. caller-supplied threshold 통과는 독립 NVE acceptance 결과,
  두-host 재현, force-field 검증, 과학·제품 claim이 아님
- 모든 perturbation을 보존하는 bounded component-energy central-difference
  force와 non-periodic configurational virial diagnostics; periodic virial은 fail-closed
- 별도 versioned reference-forcefield 확장에 ordered-star harmonic out-of-plane
  improper energy·force와 bounded deterministic symmetric degree-relaxed
  equal-weight distance-constraint projection, tangent-force 수렴과 exact
  checkpoint/restart를 갖는 projected Armijo minimization을 구현; mass weighting·
  과학 검증·제품 활성화는 없음
- caller-supplied fixed effective Born radius를 사용하는 bounded non-periodic
  CPU `float64` polar Generalized Born transfer energy·exact force와 v2 결합
  evaluator, solvation parameter identity를 결속한 optional constrained
  minimization·exact checkpoint/restart를 구현; radius 추정·nonpolar·salt/ion·
  periodic solvent·독립 검증·과학/제품 승격은 없음
- unsolvated·constrained·fixed-Born constrained·checkpoint·fail-closed 범위의
  ordered 14-case와 사전 10개 metric, 전 case failure denominator, exact 구현 source
  identity와 independent-reference 요구사항을 결과 전에 고정한 execution-disabled
  CPU minimization validation protocol, 그리고 11개 fixture·14개 case를 실제 CPU
  float64 v1/v2/fixed-Born runtime input·checkpoint pause plan·failure injection으로
  투영하되 physics를 평가하거나 결과를 수집하지 않는 exact materializer, 그리고
  constraint/tangent-force projection·fixed-Born·bounded backtracking·fail-closed
  identity·exact checkpoint/restart를 별도로 구현하고 source/import 경계를 고정한
  표준 라이브러리 독립 reference; test-only 비교는 구현 검증일 뿐 validation 결과가
  아니며, author/reviewer identity 분리·ordered review check와 limitation 확인·외부
  trusted reviewer 공개키·bounded freshness를 요구하는 Ed25519 독립 review
  attestation 계약, single-run authorization, local POSIX one-time nonce reservation,
  그리고 raw signed chain·durable nonce·실제 CPU-only deterministic process·network
  namespace를 다시 검증하고 최대 5분 operator-signed network-isolation attestation을
  확인한 뒤 별도 private root에 canonical mode-0600 secret-free 환경 receipt 하나를
  원자적으로 기록하는 run-start primitive, failure-inclusive bounded runner와 result
  writer까지 구현됨. stdlib-only bootstrap은 Engine v2/Torch/NumPy import 전에 Python
  executable·stdlib·OpenSSL·cryptography·NumPy·Torch의 실제 payload byte를 측정하고,
  run-start와 runner가 exact 6개 signed identity를 다시 측정함. bounded runner와
  atomic writer는 모든 evaluation의 canonical binary64 raw/evaluated 좌표, step별
  identity·좌표 digest, 전체 trace digest, 정확한 count와 accepted-energy ledger를
  operational·independent-oracle source별 complete ordered trace로 receipt에 보존함.
  exact bootstrap entrypoint는 bounded canonical request만 받고 package import 전에
  signed nonce·작성자·source·dependency를 결속하며, 고정된 외부 root-owned mode-0600
  trust store에서만 reviewer/operator 공개키를 다시 읽음. 같은 검증 프로세스에서
  environment receipt→14-case 고정 supervised subprocess→result receipt를 연결하고 worker도
  source·dependency·deterministic single-thread runtime을 평가 전에 재검증함.
  evaluation index·iteration·trial·outcome 정렬과 사전 coordinate/energy threshold,
  branch·rejection·count disposition, 3개 checkpoint case의 uninterrupted/paused/
  resumed digest를 결속하는 비교 계약도 runner·writer·result review에 연결됨.
  외부 acceptance threshold를 바꾸지 않고 선언된 constraint tolerance의 절반을 내부
  projection convergence headroom으로 사용하는 v2.1 protocol로 refreeze했으며,
  비-production 14-case 구현 점검은 fixed-Born 2건을 포함한 14/14 비교 row와 3개
  restart equality를 모두 통과함. 실제
  attestation·trusted key·production root/receipt·승인된 실행·독립 인간 result
  review·승인된 production trajectory 비교·과학 승격은 없으며, 외부 trust store와 signed
  artifact·private root·reserved nonce가 없으면 entrypoint는 fail-closed함
- exact synthetic case identity·사전 허용오차·failure row를 고정하고 실행 및
  parameter fitting 승인 gate를 닫아 둔 CPU reference energy/force 검증 protocol,
  그리고 결과를 수집하지 않는 exact fixture materializer와 source-bound
  표준 라이브러리 전용 analytic oracle, 구현 작성자/독립 reviewer identity 분리와
  외부 trusted reviewer key를 요구하지만 실제 review는 포함하지 않는 signed
  independent-review attestation 계약, 별도 operator identity·24시간 만료·외부
  revocation 목록·one-time nonce를 요구하지만 receipt는 포함하지 않는 single-run
  execution-authorization 계약. 두 artifact 모두 Ed25519를 사용하고 활성 verifier는
  정확히 32-byte 공개키 trust anchor만 허용하며 private/symmetric 검증 material을 거부함.
  그리고 27개 case·59개 variant 전체의 CPU 실행 환경과
  failure-inclusive 결과 receipt 형식을 고정하고 raw signed artifact 두 개를 다시 검증한 뒤
  POSIX `O_EXCL`/`fsync`로 one-time nonce를 로컬에서 소비하는 primitive, 이어서 전체
  chain과 실제 CPU-only deterministic process를 다시 검증하고 짧은 수명의 operator-signed
  network-isolation attestation을 확인한 뒤 secret-free 환경 receipt를 원자적으로 기록하는
  run-start primitive, 이어서 그 receipt와 exact code·source·dependency·artifact binding을
  다시 확인하고 one-time runner-start marker를 원자적으로 소비한 뒤 120초 평가 예산 안에서
  27개 case·59개 variant의 성공과 실패를 빠짐없이 메모리에 보존하는 제한형 CPU float64
  runner, 이어서 raw signed chain·live environment receipt·runner-start marker·exact
  observation을 다시 검증하고 private artifact root에 canonical mode-0600 receipt 하나를
  원자적으로 기록하는 failure-inclusive result writer. reader는 외부 exact receipt hash와
  revocation/supersession 입력을 요구하며 변경된 content는 외부 hash로 탐지하지만 receipt
  signature나 same-UID pathname/inode replacement resistance는 주장하지 않음. exact
  module entrypoint는 외부 trust store가 없으면 fail-closed함. 실제 trusted key,
  production receipt·reservation/
  artifact root·production nonce reservation·production 환경 receipt·runner start/result
  receipt·승인된 production 실행·independent result review·과학 acceptance는 포함하지 않음.
  별도 Ed25519 result-review 계약은 exact 14-case receipt를 전체 writer schema로 재검증하고
  모든 retained/missing metric, runtime/oracle/result hash, status/error, case별 iteration/backtrack
  budget 안의 정확한 비음수 count, retained energy metric과 일치하는 finite energy ledger,
  complete ordered operational/independent coordinate trace와 모든 trace/step disposition 및
  fail-closed disposition에서 accepted/rejected 결과를 결정함. 원본
  pre-execution review와 authorization의 Ed25519 chain으로 세 upstream 역할을 재검증하고,
  canonical JSON byte transport·필수 최신 revocation/supersession 입력·네 governance 역할의
  분리·caller-provided public key를 요구함. 실제 key, attestation, production receipt,
  reviewer approval 또는 과학 evidence는 bundle하지 않음
  `0.3.0a1` identity refreeze는 applicability record `1.2.0`
  (`cfc9d2a5f9ff4ee2539c3e15a8c0519788e26c447a71de4e994c53d4f78760a6`),
  energy/force protocol `1.2.0`
  (`0e34905c635b33b47a26cb459a93840166fc222c663d73af43d40d36814d7ee2`),
  artifact binding `1.2.0`
  (`b3341f3b98e29594cfcd727353553efa466116f275f5250c4ae944d624ef62b0`)을
  결속함. 이는 source/dependency 계보이며 production 결과나 과학 acceptance가 아님
- `OpenMM==8.4.0.post2`와 `Reference` platform으로 고정된 lazy offline 전용
  adapter. 지원되는 energy/force variant 47개를 모두 mapping하고 Engine-contract
  failure 12개를 N/A로 보존하며, 지원 minimization trace 8개의 모든 좌표를
  재평가하고 fail-closed trace 6개를 보존함. canonical receipt는 전체 OpenMM
  distribution·native/runtime identity, fixed-Born self/pair, 재계산한 nested error를
  결속함. 설치형 `betelgeuze-engine-v2-openmm-materialize` workflow는
  두 frozen matrix 전체를 실행하고 모든 성공/실패 행과 Engine iteration/rejection count·
  constraint/tangent-force metric·energy/coordinate trace·checkpoint equality를 하나의
  canonical mode-0600 no-overwrite artifact로 보존하며, 구조 검증 또는 exact
  re-execution을 제공함.
  private key를 받지 않고 `production_protocol_execution=false`·독립 검토 미완료·
  2-host 재현 미완료·`claim_safe=false`를 고정함.
  설치형 `betelgeuze-engine-v2-openmm-native-minimization` workflow는 지원되는
  8개 case에서 OpenMM L-BFGS endpoint를 실행하고 6개 expected fail-closed 행을
  보존한 뒤 모든 endpoint를 동일 좌표의 Engine v2로 다시 평가함. 현재 `1.3.0`
  configuration SHA-256은
  `9189afe3a01a7eb8ee2c26e8b233db6c2250a14317f8498e34303c1c2b4fdf51`임.
  2026-07-24 local receipt는 superseded `1.0.0` configuration
  `6465f726c408e6df2dd15d318a4cdfc57a8b2edd271ddaa578edcc336110017e`에
  결속되며, 동일 좌표 energy/force mapping 8/8과 energy
  nonincrease 8/8을 통과했지만 최종 constraint projection 뒤 fixed-Born constrained
  2건의 tangent-force 기준 실패로 endpoint health는 6/8이고 status는 rejected임.
  receipt SHA-256은
  `7e5b3454afc41f9954f71dfc3b0b274906323f15fd8ea6630bfcc1e95ce95b7c`임.
  endpoint·trajectory 동등성이나 S0 승격은 주장하지 않음. 설치형
  `betelgeuze-engine-v2-openmm-fixed-born-disposition` workflow는 이 exact rejected
  입력을 결속하고 2-case/16-probe의 frozen solver·projection 진단을 실행한다.
  v1 reporter 관측은 endpoint 마지막 비트를 바꿔 자체 exact-baseline gate에서
  거부됐고, v2는 probe·threshold를 바꾸지 않은 채 no-reporter bitwise control만
  분리했다. 현재 v5 configuration SHA-256은
  `6182cecaa21d5d191baacda1bc9cf7ae7d3cb9eb8b2ca0217757cb23af37c281`다.
  아래 historical receipt가 결속하는 v1/v2 configuration SHA-256은 각각
  `67f1a6025155d8f62cd3d1aa7da2803e229a4dce7871050db6c323f531f0b8c1`과
  `ac601f3cfedd68e24b6507778ea36c1676fb24cacf89c7c2fa73848bf3c68045`다.
  실제 receipt
  `870f1ea247da4b0232f22804298e75d554af511da18924a7ba49c1c703f003f2`는 두
  no-reporter control을 bitwise 재현하고 두 alias 모두
  `final_constraint_projection_tradeoff_observed`로 분류했다. projection 전에는
  tangent force `4.561743820542636e-09 kcal/mol/Å`가 통과하고 constraint residual
  `1.1016157942744798e-05 Å`가 실패하지만, projection 뒤에는 residual
  `1.9898749314961606e-11 Å`가 통과하고 tangent force
  `3.692322529338441e-04 kcal/mol/Å`가 실패한다. 64–1024 iteration과
  `1e-8`–`1e-12` optimizer tolerance에서도 해소되지 않았다. 이는 failure
  disposition evidence만 완결하며 causal root cause·endpoint acceptance·S0 승격은
  열지 않고 6/8 rejection을 유지한다. 별도 claim-closed
  `betelgeuze-engine-v2-openmm-constraint-stationarity` 후보는 내부 constraint
  projection을 `1e-14 Å`로 고정하고 tangent force가 엄격히 감소하면서 energy가
  best accepted energy보다 `1e-10 kcal/mol` 이내일 때만 numerical polish를
  허용한다. 후보/현재 동일좌표 OpenMM configuration SHA-256은
  `5642654a25a2d024f7cb8c1de024815f6bf6032b06f6c57509d7b784b708f708`과
  `69f5168dbf7bcaa9f4ff85f9e2e9f7800b8b21685110000a90c909d552eab6db`이다.
  historical single-host 후보 receipt
  `16a4db9ca59ad969c63bb896a8bc3cb3310e7b5cc5f5e94e9a3b2dbf59d79f70`는 적용
  가능한 constrained alias 4/4만 통과했고 superseded configuration
  `722d319c865eb15dd12296dee998b26332e2c1ad8edf3e5e6611914b960529d1`에
  결속된다. OpenMM Reference 대비 최대
  total-energy/force 오차는 각각 `1.07e-14 kcal/mol`,
  `2.40e-14 kcal/mol/Å`였다. Engine/OpenMM 모두 동일 좌표에서 기존
  `1e-8` tangent-force 기준을 통과했고 constraint residual은
  `8.66e-15 Å` 이하였다. 나머지 frozen 10행은 명시적으로 제외하며
  validation·S0·2-host·independent-review claim은 false다. 이어지는 별도
  `betelgeuze-engine-v2-minimization-stationarity-successor` 관측 경로는 frozen
  입력 14개를 모두 재사용한다. v1 4행은 기존 경로, constrained 4행은 새
  stationarity 알고리즘과 Torch/NumPy-free tuple oracle, fail-closed 6행은 기존
  exact disposition으로 실행한다. 현재 `1.3.0` configuration SHA-256은
  `edae2c0ff83761426185e5eb269b1e30ea5dd5446c93121eef94163af284c237`이다.
  superseded configuration
  `5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5`의
  single-host 후보 관측
  `18c6d617781e93c903332352d6f66e8eb2897e2c965035cd6f437d0324d3d1b9`는
  14/14와 operational/oracle checkpoint 3/3을 통과하고 전체 energy·coordinate·
  failure trace 및 4/4 OpenMM 동일좌표 후보를 결속한다. 단, production receipt,
  2-host 재현, 독립 review, native OpenMM L-BFGS repair, S0 claim은 계속 false다.
  별도 v7 Ed25519 verifier는
  두 Engine result-review chain, exact OpenMM materialization, component/trace
  receipt와 native endpoint receipt를 모두 새로 검증함. rejected endpoint에서는
  exact disposition receipt·configuration·physics projection·완결성·분류도 별도로
  결속하고, accepted endpoint에서는 이 failure-specific 입력을 금지함. 현재 6/8
  결과는 fixed-Born 실패 case ID 두 개를 보존한 서명된 `rejected` host review가
  되며 full external comparison을 accepted로 표시할 수 없음. host-review 계약
  SHA-256은
  `f7b57f08afd44e0ab7848c8ce75b08560d00cf381895aaeaf251e23cd3b81c7a`임.
  최종 v6 S0 bundle 계약은 정확히 두 host 입력을 새로 재검증하고 host·CPU·session·custody·
  artifact·nonce의 상이성과 commit·source·dependency·runtime·seed 및 energy-force·
  trace·native-endpoint physics projection의 exact equality를 요구함. 두 host 모두
  native endpoint health 8/8이고 실패 case ID가 없으며 failure-specific disposition
  path가 not applicable일 때만 모든 하위 역할과 분리된
  최종 human Ed25519 승인을
  검증함. S0 계약 SHA-256은
  `5eb28543fa9b11ac3559c20c72955c6c9c9adec757869975c71ef0207beee3a4`임.
  검증된 bundle도 frozen synthetic S0 protocol과 S1 진입만 열고 chemistry·
  fitting·benchmark·product·customer·broad scientific claim은 닫아 둠. 설치형
  `betelgeuze-engine-v2-s0-review` 명령은 secret-free detached signing request를
  검증하고 외부/HSM signer가 서명할 exact canonical byte를 내보낸 뒤, 반환된 서명을
  public key로 확인하고 attachment함. private-key option이나 기존 output overwrite는
  제공하지 않음. 실제 host evidence·trust key·최종 승인·외부 custody를 bundle하지
  않으므로 저장소의 static S0 decision은 false임
- 결정론적 제한형 torsion/rigid 도킹 후보·검색 scaffold. 별도 receipt-bearing
  molecular-graph materializer는 ring이 아니고 양쪽에 heavy atom이 둘 이상인
  heavy-atom single-bond bridge만 선택하며 좁은 amide/sulfonamide/phosphoramidate
  pattern은 제외한다. seed bond length/angle은 보존하지만 full resonance perception·
  ring closure·torsion energy·검증된 conformer generation은 아니다. 후보별 score-term
  receipt와 cross LJ·screened Coulomb·signed ligand internal strain delta·
  VDW-overlap penalty를 분리하는 명시 파라미터 CPU `float64` 진단 scorer,
  identity overlap audit와 실패 포함 all-case/target-family bootstrap 평가를
  갖춘 fit-only pairwise ranking calibration 계약. pose-level 평가는 동점 순서에
  독립적인 average-precision PR-AUC를 성공적으로 scoring되고 label된 pose에서
  계산하고, scoring 실패가 사라지지 않도록 전체 pose coverage/failure denominator와
  deterministic case-cluster bootstrap 구간을 함께 보존함. 별도의 claim-closed
  confidence evaluator는 raw top-1/runner-up score margin의 logistic proxy에 대해
  Brier·fixed-bin ECE·reliability bin·threshold abstention/coverage/risk와 동점
  group을 분리하지 않는 selective-risk curve를 전체 및 family별로 기록함. 실패 및
  성공 pose가 하나뿐인 case는 abstain하지만 all-case/all-pose 분모에 남음. disjoint
  probability-calibration fit이나 독립 검토된 threshold는 없으므로 confidence claim을
  열지 않음
- failure-inclusive rigid-body public diagnostic. 가장 낮은 record index의 graph-matched
  native reference centroid로 redocking pocket 하나를 정하고, seed conformer에 고정된
  non-identity rotation을 적용한 뒤 pose를 생성한다. 모든 candidate의 원소 반경 기반
  geometry score를 계산하고 초기 diverse score Top-K에 deterministic rigid coordinate
  descent를 적용한 뒤 다시 ranking한다. 모든 accept/reject trace·validity·무정렬
  receptor-frame symmetry-aware RMSD·Top-1/Top-5·oracle-best generation 진단과
  search/refinement/evaluation 실패 행을 기록한다. 이 정련은 힘장 최소화가 아니다.
  torsion sampling·supported-force-field refinement·charge-aware physics·fitted score·
  disjoint holdout·external baseline·claim-grade benchmark 결과는 없음
- 별도 failure-inclusive flexible 4-case diagnostic은 case별 all-bond torsion receipt를
  포함하고 candidate 0은 zero torsion, 이후 candidate는 결정론적 independent uniform
  torsion으로 생성한다. 1-2/1-3 pair를 제외한 고정 원소 반경 ligand nonbonded
  self-overlap 항을 더한 뒤 같은 validity/RMSD·Top-K rigid refinement를 적용한다.
  최종 score-order diversity selection에서는 invalid pose를 제외한다. torsion energy·
  bonded-force-field strain·torsion refinement·힘장 refinement·holdout 지위·도킹
  claim은 없음
- fail-closed 비실행 same-input 외부 baseline work-order 계약. frozen 4-case source에
  대해 준비된 receptor/ligand PDBQT의 exact byte를 검증하고 preparation tool/version·
  executable·configuration·container 및 pocket definition과 Vina/GNINA/Smina binary
  identity를 결속한다. 세 엔진에는 동일한 prepared hash·native-defined receptor-frame
  center·22.5 Å cube·seed·exhaustiveness·mode 수·CPU 1개를 전달한다. native 좌표는
  box center에만 쓸 수 있고 ligand preparation에는 쓰지 않았다는 선언을 요구한다.
  prepared file이나 엔진을 bundle하지 않고 binary를 실행하지 않으며, 결과 검증·
  통계적 holdout·독립 재실행을 완료하지 않음
- caller-provisioned PDBbind v2020 fit·CASF-2016 evaluation·논문판 308-case
  PoseBusters Benchmark를 위한 claim-closed 공개 split provenance 계약. 공식 source·
  citation·access·license·endpoint·case count를 고정하고, PoseBusters 공식 308-ID
  파일은 raw SHA-256과 canonical case-ID projection으로 결속한다. case별 exact
  receptor/ligand/scaffold/protein-chain-set identity·release date·target family·
  cofactor·지원/미지원 chemistry disposition을 기록한다. exact Smith-Waterman/
  BLOSUM62 tool receipt는 모든 evaluation/fit protein chain pair 중 최대 identity와
  similarity stratum을 보존한다. 최종 link는 generic fit/evaluation leakage audit와
  report의 all-case·target-family 분모를 다시 검증한다. PDBbind 약관을 대신 승인하지
  않고 dataset을 bundle하지 않으며 sequence 비교·benchmark 실행·결과·독립 검토는
  포함하지 않음
- 설치 가능한 public-ranking file chain. 세-way corpus intake는 canonical
  PDBbind-fit·CASF-validation·PoseBusters-test manifest와 세 sequence receipt를
  검증하고, calibration-partition intake는 PDBbind/CASF score partition의 모든
  성공·실패와 leakage 분모를 보존하며, training-view는 PDBbind 성공행만 그대로
  fit 입력으로 쓰되 제외된 실패행을 disposition으로 남긴다. 그 위의
  `betelgeuze-engine-v2-public-ranking-fit-validation`은 이 실행의 validation 관측
  전에 모든 후보와 bootstrap 설정을 workflow-local canonical manifest로 동결한다.
  각 후보는 PDBbind에만
  fit되고 CASF는 failure-inclusive all-case/all-pose·target-family·confidence
  interval 평가와 PR-AUC→Top-1→Top-5→candidate-ID 선택에만 쓰인다. 후보나 primary
  metric 하나라도 미완료면 선택하지 않는다. selection-policy SHA-256은
  `1905b14e37da44293483b9b31a06b2653849b2e986dc75b9e4ad53aa0bc4b9d9`이며
  PoseBusters test score partition은 API에 존재하지 않는다. 두 build는 wheel SHA-256
  `d338d81d14d08ca7c07f74629ac2b98f94d389f651e44e2b143fb487bfcf4bd3`로
  byte-identical했고 설치형 CLI/import를 checkout 밖에서 검증했다. genuine
  licensed PDBbind/CASF 입력이 없어 production receipt·test 결과·calibrated
  confidence·독립 재현/review·과학/도킹 claim은 모두 열리지 않는다. 외부 timestamp/
  signature custody가 없으므로 독립적으로 사전 등록됐다는 claim도 열리지 않음
- 설치 가능한 extraction-free PoseBusters 308 archive intake. caller가 제공한 공식
  Zenodo ZIP과 논문판 308-ID 파일의 exact hash·size를 요구하고, 2,570개 ZIP entry와
  428개 case directory를 hard bound 안에서 검사한다. path traversal·중복·암호화·
  미지원 압축·symlink·size/count·metadata identity 위반을 fail-closed하고, 선택된
  모든 case의 필수 artifact 4개를 CRC streaming해 정확히 308개 성공/실패 행과
  1,232개 artifact identity를 mode-0600 no-overwrite canonical receipt로 기록한다.
  exact 재실행 검증을 지원하지만 fetch·약관 승인·압축 해제·pose 생성·scoring·
  benchmark를 수행하지 않고 archive/receipt를 bundle하지 않으며 `claim_safe=false`
- 설치 가능한 extraction-free PoseBusters 308 corpus audit. exact intake를 다시
  실행하고 전 case parser·heavy labeled-graph·raw directional bond·raw aromatic
  bond·원소/formal charge·ligand capacity·metal·non-water cofactor inventory와
  Wilson 95% 구간을 기록한다. aromaticity/atom stereo를 인식하거나 parameter를
  할당하지 않고 pose 준비·생성·scoring·외부 엔진·benchmark를 실행하지 않음
- 설치 가능한 extraction-free PoseBusters 308 native-geometry preflight. exact
  intake와 corpus audit를 다시 실행하고 전 case fixed-radius receptor/ligand overlap,
  topology-excluded ligand self-overlap, native/start heavy-bond delta, 미지원 원소,
  target CCD residue-name의 receptor 잔존 여부를 기록한다. native ligand는 crystal-
  pose positive control이고 start SDF는 pose가 아닌 generated conformer다. chemistry
  인식·힘장 strain·generated-pose validity·도킹·scoring/ranking·외부 oracle·benchmark를
  수행하지 않음
- 설치 가능한 extraction-free PoseBusters strict external-input preparation
  receipt. provisional chemistry 범위 34건에만 pinned Meeko 0.7.1/RDKit
  2025.9.6 default를 적용하고 unmatched residue를 삭제하지 않으며, 308건 전체의
  prepared/failure/abstention 행을 보존한다. local exact 재실행은 private receptor/
  ligand PDBQT pair 18건, strict failure 16건, chemistry abstention 274건을 기록했다.
  native 좌표는 box center에만 사용하며 외부 엔진·generated pose·validity oracle·
  scoring·benchmark는 실행하지 않음
- 설치 가능한 failure-inclusive PoseBusters Vina 1.2.7 실행 receipt. exact strict-
  preparation receipt와 private artifact tree만 입력으로 받고 single-CPU search
  configuration·engine payload·implementation source를 고정하며 generated PDBQT와
  Vina energy component 5개를 canonical binary64로 보존하고 exact 재실행을 지원한다.
  local ignored-state production receipt는 준비된 18건을 모두 실행·성공하고 engine
  failure 0건, preparation block 16건, chemistry abstention 274건을 308-case 분모에
  보존했으며 pose 355개를 기록했다. receipt payload SHA-256은
  `37b3df7c4c14d739d9fca3970dc73293a48909372314a8dfe1da5bcd956694ae`이다.
  source-tree와 installed-wheel exact 검증이 모두 같은 receipt를 재현했고 pinned
  build-tool wheel 2회도 SHA-256
  `68380b90af9ac286a70e264cb2603288ae5a2d639f32f27b1ae376bdaebc6228`로 byte
  단위 일치했다.
  generated-pose validity·symmetry-aware RMSD·GNINA/Smina same-input 결과·target-
  family/leakage 분석·독립 외부 검토는 아직 없으므로 docking benchmark나 제품
  claim이 아님
- 입력 case마다 정확히 하나의 성공/실패 행을 갖는 benchmark manifest
- frozen four-case PoseBusters contract cohort의 bounded offline materializer.
  caller가 제공한 seed/reference SDF byte를 검증하고 multi-record의 모든
  parse·match·failure 행을 보존하며, seed 좌표는 사용하지 않는다. 원자번호·전하·
  isotope·aromatic·directional V2000 stereo로 표지한 graph identity와 제한된
  stereo-preserving symmetry mapping을 생성하고, ligand-only alignment 없이 모든
  일치 reference pose에 대해 receptor frame의 heavy-atom RMSD 최솟값을 계산한다.
  installable `betelgeuze-engine-v2-public-materialize` 명령은 symlink가 아닌 로컬
  입력 root에서 receptor/seed/reference 12개 파일을 모두 검증하고 case별 성공·실패를
  누락 없이 담은 canonical no-overwrite suite receipt를 출력한다. exact per-case
  materializer source는 protocol v1.1에 결속된다. 이 명령은 network fetch·pose 생성·
  pose validity·scoring을 수행하지 않으며 데이터·도킹 실행·benchmark 결과·독립 검토·
  과학/제품 claim은 포함하지 않는다

이 표면은 calibrated docking, MD, free energy, GPU 또는 고객 제품 기능이
아닙니다. 현재 모든 V2 capability는 `claim_safe=false`,
`customer_execution_enabled=false` 상태입니다.

먼저 읽을 문서:

- `docs/engine_v2_status.md`
- `docs/engine_v2_public_api.md`
- `config/independent_engine_v2_capabilities.yaml`
- `docs/entrypoints.md`

## 저장소 구성

| 영역 | 역할 |
| --- | --- |
| `betelgeuze_engine_v2/` | 독립 V2 계약, 분자 상태, 희소 기하, AI·수학 primitive, strict ingest, physics registry, 도킹·benchmark scaffold |
| `packaging/engine-v2/` | 독립 `betelgeuze-engine-v2` 배포 metadata |
| `core/`, `betelgeuze_engine/` | 레거시 물리·runtime·호환 표면. V2 wheel이 암묵적으로 import하지 않습니다. |
| `api/`, `betelgeuze_product/` | validated-runner 제품 API와 납품 orchestration |
| `tools/` | gate, manifest, bundle, benchmark/accounting, 운영 command |
| `tests/` | V2, 레거시 runtime, API, evidence, 납품 gate 테스트 |
| `config/` | capability 정책, target preset, threshold, runtime profile, gate 설정 |
| `docs/` | 아키텍처, 주장 경계, reviewer entrypoint, 납품 runbook, wetlab 문서, roadmap |
| `casp17/` | CASP17 로컬 operator/review scaffold와 상태 문서 |

## Independent Engine v2 빠른 시작

```bash
python3 -m venv .venv-v2
source .venv-v2/bin/activate
python -m pip install --upgrade pip
python -m pip install "build>=1.2,<2" numpy==1.26.4
python -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
python tools/build_engine_v2_wheel.py --output-dir dist-engine-v2
python -m pip install --no-deps dist-engine-v2/*.whl
python -m pip check
```

기계 판독 가능 상태 확인:

```bash
python - <<'PY'
from betelgeuze_engine_v2.capabilities import capability_snapshot
import json
print(json.dumps(capability_snapshot(), indent=2, sort_keys=True))
PY
```

루트 API는 `ENGINE_API_VERSION`으로 관리됩니다. V2-G의 `io`, `docking`,
`benchmark`, registry, runtime submodule은 배포 버전 `1.0.0` 전까지
provisional입니다. 자세한 정책은 `docs/engine_v2_public_api.md`에 있습니다.

## 모노레포 개발 환경

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

표준 V2 집중 테스트:

```bash
python -m pytest -q \
  tests/unit/test_engine_v2_contracts_molecular.py \
  tests/unit/test_engine_v2_sparse_geometry_features.py \
  tests/unit/test_engine_v2_ai_core.py \
  tests/unit/test_engine_v2_periodic_energy.py \
  tests/unit/test_engine_v2_orchestrator_contract.py \
  tests/unit/test_engine_v2_runtime_checkpoint_contracts.py \
  tests/unit/test_engine_v2_packaging_guards.py \
  tests/unit/test_engine_v2_bounded_scaffolds.py \
  tests/unit/test_engine_v2_post_merge_state.py
```

`.github/workflows/ci-engine-v2-main.yml`은 관련 PR과 V2 관련 `main` push에서
Python 3.10, 3.11, 3.12로 같은 계약을 재검증합니다.

## 제품 API (`/simulate`)

HTTP 제품 표면은 **validated-runner ligand HTVS와 backmapping scoring만**
지원합니다. 범용 MD 및 Engine v2 고객 실행은 의도적으로 지원하지 않습니다.

```bash
pip install -r requirements-api.txt
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

승인된 `runner_profile_id`가 없으면 요청은 fail-closed 됩니다.

## 로컬 evidence와 납품

`data/`, `runs/`, trajectory, checkpoint, 로컬 bundle, log, cache 같은 생성·민감
산출물은 GitHub에서 제외됩니다. Clean clone에는 소스, 테스트, schema,
lightweight figure, template이 들어 있지만 로컬 evidence gate나 과학 성능을
증명하지는 않습니다.

제한형 납품 검토는 다음 문서부터 시작합니다.

- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `docs/local_delivery_bundle_schema.md`
- `docs/broad_claim_unlock_roadmap.md`

필요한 산출물이 재생성되거나 검토된 bundle로 제공되기 전까지 로컬 evidence
validator는 의도적으로 fail-closed 됩니다.

## CASP17 및 운영 lane

변경 가능성이 큰 CASP17 상세 상태는 다음 문서에서 관리합니다.

- `casp17/WORKBENCH.md`
- `casp17/CASP17_CURRENT_STATUS_REPORT.md`
- `casp17/CASP17_WIN_TIER_GOAL.md`

이들은 로컬 준비·operator review 표면이며 제출, leaderboard, win-tier 증거가
아닙니다.

## 주장 경계

현재 허용되는 표현:

- V2-G 제한형 CPU 기준 계약과 scaffold가 구현되고 테스트됐습니다.
- 독립 wheel은 Python 3.10–3.12의 clean environment에서 설치됩니다.
- strict ingest는 source hash를 기록하고 화학을 조용히 추론하지 않습니다.
- docking·benchmark ledger는 실패 candidate/case를 제거하지 않고 보존합니다.
- 제한형 로컬 납품 주장은 별도의 evidence gate와 검토된 로컬 산출물을 따릅니다.

추가 증거 없이 허용되지 않는 표현:

- calibrated docking 정확도 또는 광범위한 virtual screening 성능
- 검증된 force field, MD, MM/GBSA, FEP, binding free energy
- CUDA/ROCm/HIP parity 또는 가속
- wetlab-proven hit
- 자동 scorer/router/platform 승격
- 광범위한 상업용 신약개발 플랫폼

구현, 과학 검증, 공개 benchmark, 제품 qualification은 서로 다른 단계입니다.
소스 수준 테스트가 green이라고 해서 이 단계들이 하나로 합쳐지지 않습니다.
