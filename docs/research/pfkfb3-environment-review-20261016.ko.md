# PFKFB3 lig_38: 힘장 출처와 결정 환경 점검

작성일: 2026-10-16 UTC. 이 문서는 외부 보존 연구 보고서의 전사이며 아래 캠페인 파일명은 저장소 파일 링크가 아니다. 범위: 공개 1차 출처, 보존된 입력·결과의 읽기 전용 검토와 좌표·파라미터 대수 계산. 새 에너지/힘 평가 0회, 최적화 0회, 설치 0회. 기존 입력·실행 결과는 수정하지 않았다.

## 핵심 결론

이번 점검에서 새로운 파라미터 변환 버그는 발견하지 못했다. 반면 정확한 실험 구조 6HVI/GV5와 현재 고정·건조 수용체 모델 사이에는 구체적인 환경 차이가 있다. 특히 결정의 pyrophosphate(POP)가 리간드에서 2.747 Å 떨어져 있지만 준비된 계에 없다. 이것이 위치 오차의 원인이라는 인과적 결론은 아직 내릴 수 없다.

이미 저장된 성분별 에너지는 원래 준비 좌표에서 비구속 최소점으로 이동할 때의 에너지 이득이 주로 단백질–리간드 정전기 항에서 나온다는 점을 보여준다. 이 확인을 위해 새 단일점 계산을 반복할 필요가 없다.

## 1. 기존 결과 재사용: 무엇이 이동을 보상했나?

아래 값은 기존 observation JSON의 16진수 부동소수점 값을 읽어 계산했다. 단위는 kcal/mol이고, 차이는 각 끝점에서 원래 준비 좌표 값을 뺀 것이다.

| 항목 | 원래 준비 좌표 | 비구속 끝점 cold-start-84 | 원래 대비 차이 | shape 해제 끝점 | 원래 대비 차이 |
|---|---:|---:|---:|---:|---:|
| 리간드 내부 | 227.295184 | 240.176238 | +12.881054 | 217.921195 | −9.373988 |
| 단백질–리간드 LJ | −62.340909 | −44.506743 | +17.834166 | −28.488993 | +33.851915 |
| 단백질–리간드 Coulomb | +21.648637 | −197.250795 | −218.899432 | −205.610203 | −227.258840 |
| 합계 | 186.602912 | −1.581300 | −188.184212 | −16.178001 | −202.780913 |

비구속 끝점은 내부 에너지와 LJ가 모두 불리해졌음에도 Coulomb 감소가 이를 상쇄한다. 해제 끝점도 가장 큰 이득은 Coulomb 감소다. 이는 **현재 선언된 모델의 에너지 선호**에 대한 설명이며, 누락된 물/POP의 인과 효과나 올바른 용매화 구조를 검증한 것은 아니다. shape 구속 실행의 총에너지에는 별도의 구속 항이 포함되므로 그대로 비교하면 안 된다.

재현 파일(캠페인 루트 기준):
- `physical-run-attempt2/initial-observation.json`
- `cold-start-84/endpoint-observation.json`
- `release-shape1000/endpoint-observation.json`
- 보조 요약: `strain-diagnosis-components.json`

## 2. 실제 결정과 누락된 주변 성분

공식 6HVI PDB의 같은 비대칭 단위 내 최소 중원자 거리다. 리간드와 주변 성분 모두에 기존의 수용체 전용 강체 정렬을 적용하면 이 거리는 변하지 않는다. 결정 대칭 이웃은 이번에 분석하지 않았다.

| 주변 성분 | GV5와의 접촉 | 거리 Å | 점유율/대체 위치 | 해석상의 주의 |
|---|---|---:|---|---|
| POP A602 | O3–N3 | 2.747226 | 양쪽 1.00 / blank | B factor 22.53/27.13 Å². 가까운 누락 파트너지만 기능·양성자화·인과 효과는 미확정 |
| DMS A605 | C2–C19 | 2.988492 | 양쪽 1.00 / blank | 접촉 DMS 원자 B factor 57.50 Å² |
| HOH A702 | O–O1 | 약 2.146 | 양쪽 1.00 / blank | B factor 39.16/47.75 Å². 매우 짧은 O–O 거리이므로 검증된 수소결합이라고 부르면 안 됨 |
| HOH A907 | O–N2 | 약 3.148 | 1.00 / blank | 수소 방향·양성자화는 직접 관측되지 않음 |
| F6P | 전체 중원자 최소 | 31.968078 | — | 리간드와 직접 근접하지 않음 |
| citrate FLC | 전체 중원자 최소 | 14.211670 | — | 현재 10 Å cross cutoff 밖 |

공식 결정에는 물 373개와 POP/F6P/FLC/DMS가 있다. 반면 고정된 OpenFF 준비 자료의 `cofactors_crystalwater.top`은 `SOL 362`만 선언한다. 현재 모델은 그 362개 물도 포함하지 않는다. POP 누락은 현재 어댑터의 단순 누락이 아니라 준비 자료 단계부터 존재하는 차이다.

결정 조건은 pH 7.5, 결정화 277 K, 회절 수집 100 K이며, 기록된 결정화 용액은 0.16 M monosaccharides, 30% GOL_P4K, 0.1 M MOPS/HEPES다. 1.96 Å X선 구조에서 리간드 수소는 직접 관측되지 않았다. CCD와 준비 SDF의 중성 화학 그래프 일치가 실험적 양성자화 검증을 뜻하지는 않는다.

1차 출처: [RCSB 6HVI](https://www.rcsb.org/structure/6HVI), [공식 PDB 좌표와 실험 조건](https://files.rcsb.org/download/6HVI.pdb), [공식 mmCIF](https://files.rcsb.org/download/6HVI.cif). 로컬의 기존 `crystal-reference/download-manifest.json`과 `integrity-verification.json`에 출처·무결성 기록이 있다.

## 3. 파라미터·1–4·torsion 점검

- 리간드 권위 입력은 고정 커밋 `fe6f96916b2e28f9c14398d77c838d6515e931b0`의 완전한 standalone `lig_38.top`이다. 주석은 ParmEd 3.2.0 생성임을 기록한다. 현재 어댑터는 그 전하·질량·결합·각·dihedral·명시적 pair를 사용한다.
- TOP은 combination rule 2, nrexcl 3, 명시적 pair, Coulomb 1–4 factor 0.83333을 선언한다.
- 111개 명시적 pair를 독립적으로 대수 확인했다. sigma는 산술 평균과 최대 4×10⁻⁹ nm 차이, epsilon은 기하 평균의 0.5배와 최대 4.53×10⁻¹⁰ kJ/mol 차이다. 명시적 epsilon에 0.5를 다시 곱하면 이중 축소가 된다. 현재 구현은 그렇게 하지 않는다.
- 모델에는 exclusion 255개, bond 54개, angle 90개, proper Fourier row 135개, ordered improper row 63개가 있다. 기존 독립 검증은 그래프 거리 기반 exclusion 및 source dihedral multiset 보존을 확인했다.
- Fourier 코드에서 signed coefficient와 원래 원자 순서를 보존한다. 소스 phase는 모두 0°/180°이므로 dihedral 부호만 뒤집는 것은 해당 cosine 에너지를 바꾸지 않는다. 음의 coefficient 자체는 오류가 아니다.
- TOP/ITP 전하는 26개 원자에서 차이가 있으나 최대 차이는 1.2×10⁻⁷ e로 반올림 규모다.
- 공식 OpenFF 1.0.0의 a11은 138.3188636899°다. 관찰된 큰 C–C–H 평형각은 upstream parameter에 실제로 존재하며 degree 변환 버그가 아니다.
- 같은 공식 offxml은 AM1-BCC, Lorentz–Berthelot 혼합, LJ 1–4=0.5, Coulomb 1–4≈0.833333을 명시한다. 다만 해당 준비 파일을 생성한 정확한 toolkit/backend 실행 이력까지 재구성한 것은 아니다.

1차 출처: [공식 OpenFF 1.0.0 offxml](https://raw.githubusercontent.com/openforcefield/openff-forcefields/main/openforcefields/offxml/openff-1.0.0.offxml), [GROMACS topology 규칙](https://manual.gromacs.org/current/reference-manual/topologies/topology-file-formats.html), [GROMACS nonbonded 규칙](https://manual.gromacs.org/current/reference-manual/functions/nonbonded-interactions.html), [고정 benchmark 자료](https://github.com/openforcefield/protein-ligand-benchmark/tree/fe6f96916b2e28f9c14398d77c838d6515e931b0/data/2020-07-06_pfkfb3).

## 4. 버그와 근사, 미확정 사항의 구분

**확인된 변환 버그:** 이번 점검에서는 없음. 이것은 독립 엔진과의 전면 수치 검증을 완료했다는 뜻은 아니다.

**명시적 모델 근사:** 고정·건조 단백질, dielectric 1, screening 0, 일반 내부 nonbonded 및 cross의 8–10 Å switching, 용매/PME/주기 경계/결정 packing 부재. 단백질 내부 에너지는 좌표 고정 시 상수이므로 빼는 것 자체가 리간드 최적화 오류는 아니다. 단백질을 움직이지 못하게 하는 제한이 실질적인 근사다.

**준비 상태:** 준비 단백질은 아미노산 415개와 ACE/NME cap을 가진다. 히스티딘 9개 중 253/414는 HD1, 나머지 134/138/229/242/258/387/441은 HE2를 가진 중성 tautomer로 준비되어 있다. 실험적으로 입증된 수소 위치가 아니다. 결정에는 미모델링 서열도 있으며, N말단 등의 준비 변경은 원래 결정과 구별해야 한다.

**미확정 출처:** receptor atomtype/default table은 [Hahn 2024 공개 archive](https://zenodo.org/records/10495732)의 Amber99sb*-ILDN 계열이다. 원래 준비에 사용된 테이블과 정확히 동일한지는 아직 확정되지 않았다. 나중에 출판되었다는 사실만으로 불일치라고 판단해서는 안 된다.

## 5. 다음 판별 작업과 종료 조건

우선 새 E/F 없이 위의 기존 성분 기록과 후속 완료된 단일 변경 fused-plane 결과를 함께 해석한다. 원래/비구속/해제 끝점의 에너지 항을 재계산하는 작업은 중복이므로 제안하지 않는다.

그 다음 환경 대조를 설계한다면 POP와 물을 즉흥적 점전하로 추가하면 안 된다. 공식적으로 뒷받침되는 화학 상태, 원자 매핑, 수소 배치와 일관된 힘장 파라미터를 먼저 확보해야 한다. 확보되지 않으면 환경 복원 에너지 대조는 보류한다. 현재의 Coulomb 우세와 POP의 근접은 이 검토를 우선할 근거지만, dielectric을 결정 RMSD에 맞춰 조정하거나 결정 좌표에 맞춰 힘장 값을 fitting할 근거는 아니다.

이 보고서의 범위는 여기까지이며 기존 캠페인 데이터의 수정이나 새로운 계산 실행을 포함하지 않는다.
