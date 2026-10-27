# 명시된 결합각·평면 RMS 정책 검사

이 도구는 입력에서 지정한 원자와 경계값만 평가하는 독립적인 stdlib 진단기다. 기존 `betelgeuze_product/cpu_refinement_diagnostics_v1/geometry.py`의 결합각 측정이나 `docking/validity.py`의 bond/clash/chirality 검사를 대체하지 않는다. 새 범위는 **명시된 각도 구간의 정책 판정** 및 **명시된 그룹의 최적 평면 RMS 이탈 판정**이다.

## 주장하지 않는 것

화학 결합·방향족·혼성화·수소·전하·입체화학·원자 매핑을 자동 인식하지 않는다. 자동 보정, 에너지/힘 계산, 최적화, native/RDKit import, 네트워크, 파일 쓰기를 수행하지 않는다. 전체 분자 타당성, 결합 친화도, 도킹 정확도, 엔진 admission을 판정하지 않는다. 입력 정책의 출처 표기는 제공자의 선언이지 인증이 아니다. 체크의 SATISFIED를 화학적 PASS로 바꾸지 않는다.

PoseBusters의 [공식 API 문서](https://posebusters.readthedocs.io/en/latest/api.html)는 RDKit distance-geometry bounds를 이용한 기하 검사와 SMARTS로 선택한 평면 그룹의 검사를 구분한다. 본 도구는 이 개념을 참고했지만 RDKit, SMARTS, 그 논문의 검증 세트를 실행하지 않았으며 **PoseBusters 동등성/PB-valid를 주장하지 않는다**. 특히 본 도구의 RMS 거리와 최대 평면 이탈은 서로 다른 지표다. 문헌: Buttenschoen et al., Chemical Science 2024, DOI [10.1039/D3SC04185A](https://doi.org/10.1039/D3SC04185A).

## 실행

저장소 checkout에서 설치 없이 실행한다.

```sh
python -I -S tools/check_declared_geometry.py tests/fixtures/declared_geometry_synthetic.json
cat tests/fixtures/declared_geometry_synthetic.json | python -I -S tools/check_declared_geometry.py -
python -m unittest discover -s tests/unit -p test_check_declared_geometry.py -v
python -O -S -m unittest discover -s tests/unit -p test_check_declared_geometry.py -v
```

성공적인 보고서 생성은 stdout JSON 한 줄, 종료 코드 0이다. 결과에 VIOLATED/UNKNOWN이 있어도 보고서 생성 자체는 성공이다. 잘못되거나 지원하지 않는 입력은 stderr의 INPUT_ERROR와 종료 코드 2이며, 이를 분자 정책 위반으로 세면 안 된다. 입력 bytes의 SHA-256은 보존 확인용이며 진실성·출처 인증이 아니다.

## 입력 계약

`betelgeuze.declared_geometry/1` 스키마, `units={"coordinates":"angstrom","angles":"degree"}`, 문자열 `frame_id`, `state_id`, `atoms`, `expected_checks`를 사용한다. 알 수 없는 필드·JSON 중복 key·NaN/Infinity·bool 숫자·중복 atom/check ID는 거절한다. 좌표는 공통 직교 좌표계이고 PBC/정렬/단위 변환은 지원하지 않는다. 원자 행은 `id`와 세 좌표 `xyz`만 갖는다.

각도 체크의 원자 순서는 `[외측, 중심, 외측]`이다. `kind="angle"`, 서로 다른 원자 3개, `bounds=[최소각, 최대각]`(degree, 0~180 포함), `policy={id,version,source}`를 제공한다. 출처가 있는 bounds는 호출자가 화학 상태에 맞게 마련해야 한다. 합성 예제의 89~91도 범위는 합성 직각의 시험값일 뿐 범용 화학 범위가 아니다.

평면 체크는 `kind="plane_rms"`, 서로 다른 원자 4~32개, `max_rms_angstrom`, 같은 policy 메타데이터를 제공한다. 세 점은 항상 평면을 정의하므로 유효한 평면성 시험 선언으로 받지 않는다. 임의 그룹이 실제 평면 구조여야 하는지 이 도구는 판단하지 않는다. 큰 그룹에서 RMS는 한 원자의 큰 이탈을 희석할 수 있다.

정책/threshold 생략 또는 null은 해당 기대 행을 UNKNOWN으로 남긴다. 좌표가 없는 원자 ID를 참조해도 기대 행을 지우지 않고 MISSING_COORDINATES로 기록한다. 잘못된 정책 타입·역전 bounds는 INPUT_ERROR다. 체크하지 않은 원자/성질은 미검증이며, 선언 manifest가 완전하다고 인증하지 않는다.

## 수학과 수치 보류

각도는 두 팔을 정규화한 뒤 `atan2(norm(cross), dot)`로 계산한다. 0/180도는 측정 가능하지만 화학적으로 적절하다는 뜻은 아니다. 길이가 1e-12 Å 이하인 팔은 DEGENERATE_ANGLE로 보류한다.

평면 지표는 중심화 좌표의 population covariance 최솟값 고유값 제곱근이다. 좌표 스케일을 정규화한 뒤 3×3 대칭 Jacobi 반복을 최대 64회 수행한다. 최소 고유값이 중복되어 평면 법선이 유일하지 않아도 RMS 최솟값은 정의되므로 계산할 수 있다. 점/선에 가까워 2차원 범위가 없는 그룹은 DEGENERATE_PLANAR_GROUP이다. rank 검사 비율은 1e-12이며, extent가 1e-12 Å 이하인 그룹도 보류한다. 이것들은 수치 도메인 정책이지 화학 허용범위가 아니다.

수학적 경계는 inclusive다. 하지만 경계 근처의 부동소수점 판정은 자동 통과시키지 않는다. 각도 경계와 1e-10도 이내이면 NUMERIC_BOUNDARY다. 평면은 정규화 최소 고유값과 `(bound/scale)^2` 차이가 `128*machine_epsilon + 2*최종 offdiagonal residual` 이하이면 NUMERIC_BOUNDARY다. 이 guard는 보수적 보류 정책이지 증명된 전체 오차 상한이 아니며, 결과에 `guards_are_certified_error_bounds=false`를 명시한다. 정확히 0 RMS를 요구하는 경계 또한 보류될 수 있다. 경계를 넓혀 SATISFIED로 만드는 숨은 tolerance는 없다.

실질적인 음수 고유값·미수렴은 NUMERIC_UNRESOLVED다. roundoff 규모의 음수는 RMS 계산에서 0으로 clip하지만 raw normalized eigenvalues는 보존하며, 그 경계 판정은 guard로 보류한다. 입력 좌표의 양자화/실험 불확실성이나 잘못된 매핑은 이 수치 guard가 보증하지 않는다.

## 상태·분모

각 기대 체크는 SATISFIED / VIOLATED / UNKNOWN 중 하나와 측정·정책·원인을 갖는다. requested/satisfied/violated/unknown을 분리한다. UNKNOWN이 하나라도 있으면 coverage_complete=false다. 빈 expected_checks는 전체 통과가 아니며 coverage_complete=false다. `all_declared_constraints_satisfied`는 비어 있지 않고 모든 선언 행을 평가하여 만족한 경우에만 true이며, whole_molecule_validity_assessed와 chemical_identity_verified는 항상 false다. 하나의 위반과 다른 미검증을 하나의 PASS로 축약하지 않는다.

## 실행 한도와 증거 범위

최대 입력 1 MiB, JSON 깊이 24, 원자 10,000개, 체크 2,000개, 평면 그룹 32개, 좌표 절댓값 1e6 Å, 출력 4 MiB이다. CLI는 이 예산을 지키지만 hard RSS/process-tree sandbox를 제공하지 않는다. Python API의 `evaluate()`는 byte parser를 대체하지 않는다. 불신 JSON은 `parse_bytes()` 또는 CLI로 넣는다.

본 PR의 검증 자료는 작은 합성 도형뿐이며 실제 분자·엔진 결과는 포함하지 않는다. 일반적인 화학 타당성이나 정확도 개선 증거가 아니다. 실제 사용에는 검증된 원자 대응, 화학 상태, 정책 출처와 독립적인 다른 validity 검사가 필요하다.
