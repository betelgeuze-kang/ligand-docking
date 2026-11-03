# 저장 E/F 다중 간격 검산

## 범위와 기존 기능의 관계

`betelgeuze_engine_v2/physics/reference_diagnostics.py`에는 이미 전체 3N 좌표의 단일 간격·에너지 항별 유한차분 실행 진단이 있다. 이 도구는 이를 대체하거나 재실행하지 않는다. **이미 저장된** E/F 샘플의 좌표 결속, 전체 분모, 여러 간격의 일관성을 표준 라이브러리만으로 검사한다.

분자 엔진, Torch, RDKit, NumPy를 import하지 않으며 엔진 E/F 실행은 0회다. 결과가 일관되어도 힘장·분자 정확도·네이티브 설치·GPU·제품의 자격 검증을 완료했다는 뜻이 아니다. 기존 admission이나 promotion 필드를 바꾸지 않는다. 저장된 파일의 해시는 바이트 결속일 뿐 작성자 인증이나 실제 엔진 실행 증명이 아니다.

## 실행

저장 JSON의 정확한 바이트 SHA256을 사전에 구한 뒤 실행한다.

```sh
python tools/check_saved_force_differences.py input.json --expected-sha256 <64자리 SHA256>
```

stdout은 JSON 보고서, stderr는 경로·원본 label을 포함하지 않는 일반 오류다. 도구는 파일을 생성·변경하거나 네트워크에 접근하지 않는다. 종료 코드 0은 **보고서를 정상 생성했다는 뜻**이며 과학적 성공이 아니다. 코드 2는 잘못된 계약, 불일치한 해시, 접근 불가 또는 자원 한도 초과다. 호출자는 JSON의 `status`, `coverage_complete`, `axis_channel_counts`를 반드시 읽어야 한다.

## 입력 계약: saved_force_differences/1

작은 완전 합성 예제는 `tests/fixtures/saved_force_differences_synthetic.json`이다. 예제는 한 원자의 대각 이차함수이며 실제 분자·힘장이 아니다.

- `units`: energy `kcal/mol`, length `angstrom`, force `kcal/mol/angstrom`만 지원. 단위 자동 변환 없음.
- `force_convention`: `minus_energy_gradient`만 지원. gradient를 force로 자동 추측하지 않는다.
- `context`: model, chemical_state, frame, frozen_environment, engine 문자열. model에는 파라미터·설정 식별, frozen_environment에는 고정 수용체·환경 식별을 포함할 책임이 입력 생산자에게 있다.
- `context_sha256`: context를 키 정렬·ASCII·구분자 `,`/`:`의 canonical JSON으로 직렬화한 SHA256. 각 샘플에도 같은 값을 넣는다. 원본 문맥 문자열은 보고서에 되풀이하지 않는다.
- `atom_ids`: 움직이는 원자의 고정 순서. 이 목록의 모든 원자에 대해 x/y/z가 필수다. 고정 원자는 이 목록 밖에 둘 수 있지만 고정 환경은 context에서 결속해야 한다. 실제 분자의 모든 원자가 포함되었는지는 이 도구가 독립 인증하지 않는다.
- `expected_terms`: 검증할 총에너지/성분 채널의 사전 선언 목록. 채널 이름만으로 물리적 의미를 추론하지 않는다. 성분 E는 같은 성분의 F와 비교해야 한다.
- `steps`: 양수이며 엄격히 감소하는 3~6개 h. 모든 h가 검증 창이다. 결과를 본 뒤 가장 좋은 h를 골라 통과시키는 기능이 없다.
- `baseline`: coordinates `[N][3]`, geometry_sha256, energies `{채널: 수}`, forces `{채널: [N][3]}`. 빠진 채널은 UNKNOWN이다. 좌표·힘의 잘못된 모양은 계약 오류다.
- `samples`: atom_index, axis(0/1/2), h, sign(-1/+1), status, context_sha256. status가 `ok`이면 전체 coordinates, geometry_sha256, energies가 필수다. `failed`/`unsupported`/`not_attempted`는 수치 필드를 싣지 않는다. 누락 샘플도 예상 분모에 남긴다.

geometry_sha256은 `[N][3]`의 각 수를 float64로 해석한 `float.hex()` 문자열 배열을 canonical JSON으로 직렬화한 SHA256이다. 좌표는 JSON 유한 수이고 bool은 허용하지 않는다. 샘플은 baseline에서 지정한 한 좌표만 float64 `x + sign*h`로 바뀌어야 한다. 나머지는 `float.hex()` 수준에서 같아야 한다. 따라서 임의 최적화 끝점이나 다른 축 변경을 stencil로 받아들이지 않는다. 저장된 좌표가 실제 평가된 좌표였다는 주장 자체는 생산자의 책임이다.

## 정책과 판정

policy 필드는 force_atol, force_rtol, stability_atol, stability_rtol, roundoff_fraction, energy_resolution, domain이다. 절대 허용오차는 양수, 상대 허용오차는 0 이상 1 미만, roundoff_fraction은 0 초과 1 이하, energy_resolution은 0 이상이다. domain은 `smooth`, `unknown`, `nonsmooth` 중 하나다. 숫자는 사용자가 사전에 고정해야 하는 정책이며 이 도구는 그 과학적 적합성을 인증하거나 자동 조정하지 않는다. 정책 해시는 제출된 내용만 결속하며 실제로 결과를 보기 전에 정책을 등록했는지 증명하지 못한다.

- force/stability 절대 허용오차는 force 단위이며 상대 허용오차는 무차원이다.
- energy_resolution은 생산자가 선언한 샘플당 절대 에너지 불확실성 크기다. 0이라고 선언해도 float 산술 위험 proxy는 계산한다.
- smooth 선언은 유효한 미분 구간을 생산자가 확인했다는 조건이다. cutoff 경계, 제약 투영, 불연속 PBC 재배치, 정의되지 않은 선형각·dihedral 등에는 이를 무심코 선언하면 안 된다. 도구는 force field를 보지 않으므로 이 조건을 독립 증명하지 못한다.

실제 저장 좌표에서 a=x_plus-x0, b=x0-x_minus를 구한다. 둘 다 양수여야 한다. float 반올림 때문에 a와 b가 다를 수 있으므로 다음 비균일 3점 식을 쓴다.

```
g = [b * (Eplus-E0)/a + a * (E0-Eminus)/b] / (a+b)
F_fd = -g
```

a=b=h이면 중앙차분 `(Eplus-Eminus)/(2h)`의 음수와 같다. x+h가 x와 같아지는 작은 h는 영미분이 아니라 해상도 부족이다.

각 h에서 `abs(F-F_fd) <= force_atol + force_rtol*max(abs(F),abs(F_fd))`를 기록한다. 인접 h의 FD 값은 stability 정책으로 비교하며, 마지막 h의 좌우 일방미분 차이도 같은 stability 정책으로 검사한다. 이것은 cusp에서 중앙미분만 우연히 0이 되는 함정을 줄이지만 유한 샘플로 모든 미분 가능성을 증명하지 않는다. 작은 h의 일방 기울기 차이는 정상 곡률에도 생길 수 있으므로 UNKNOWN은 힘이 틀렸다는 뜻이 아니다.

float ULP와 energy_resolution에서 만든 roundoff proxy가 허용오차 예산의 roundoff_fraction을 넘으면 UNKNOWN이다. 이 proxy는 엔진 오차의 엄밀한 상한이 아니다. 부동소수점 중간 계산이 유한하지 않거나 h별 결과가 안정적이지 않아도 UNKNOWN이다. 수렴비 4를 강제로 요구하지 않는다. 정확한 이차함수·영미분·roundoff 구간에는 그 비율이 적용되지 않을 수 있다.

각 원자·축·채널 결과:

- `consistent_under_supplied_policy`: 모든 h의 증거가 있고 해상도·stability·좌우 기울기 조건과 F 비교를 만족.
- `inconsistent_under_supplied_policy`: 충분한 stencil 및 stability 조건에서 F 비교가 정책 밖. 어느 에너지 모델이 과학적으로 맞다는 판단은 아니다.
- `unknown`: 누락·실패·미지원·불분명한 domain·해상도·안정성 문제.

전체 결과는 UNKNOWN 행이 하나라도 있으면 UNKNOWN이며 관측된 불일치 수는 별도로 유지한다. 모든 축의 신호가 force 허용오차보다 작으면 전체 결과는 UNKNOWN으로 남긴다. 영미분인 개별 축은 일관적으로 기록할 수 있지만, 상수함수나 지나치게 넓은 정책만으로 전체 자격을 얻지 못한다. 하나의 정보성 축이 있다고 모든 영미분 축의 구현 민감도가 검증되는 것은 아니다.

`coverage_complete`는 필요한 성공 샘플과 채널이 모두 있다는 의미이며 수치 안정성/과학적 타당성 성공과 다르다. 총힘·norm·평균 오차로 성분별 실패를 상쇄하지 않는다. 총에너지와 성분 힘의 합산 관계, 물리적 병진·회전 불변성, ligand+fixed receptor의 총힘 0 여부는 이 도구의 검사 범위가 아니다.

## 자원 한도와 검증 경계

입력 16MiB, JSON 깊이 32, 원자 최대128, 채널 최대8, h 최대6, 샘플 최대4096, 좌표 비교 최대2,000,000, 출력8MiB. 조합에 따라 더 작은 입력에서도 거부될 수 있다. 이 수치는 단일 프로세스의 입력/출력/연산 계약이며 OS 전체 RSS 격리 보증이 아니다. Python API의 analyze는 이미 파싱된 입력 계약용이고, 비신뢰 바이트에는 load_bytes 또는 CLI를 사용한다.

실제 molecular E/F 평가, 원본 비공개 결과, force field 파라미터는 이 PR에 포함하지 않는다. 테스트는 부호·축 교환·성분 상쇄·누락·좌표 결속·큰 에너지 offset·cusp·반올림·CLI 실패 등 합성 사례다. 실제 적용에는 같은 엔진/모델/좌표의 새 저장 stencil 자료가 필요하며 현재 실제 엔진 qualification은 `not_performed`다.

공식 수치미분 문서도 h 감소에 따른 절단오차 감소와 지나치게 작은 h에서의 subtractive cancellation을 구분한다. 이 도구는 SciPy를 실행하거나 그 기본 허용오차를 가져오지 않는다.

- https://docs.scipy.org/doc/scipy/reference/generated/scipy.differentiate.derivative.html
