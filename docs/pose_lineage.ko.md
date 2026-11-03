# 오프라인 pose lineage 분석 (연구용 sidecar)

초기 후보 → refinement 결과 → 최종 선택의 **같은 candidate ID**를 연결하는
작은 표준 라이브러리 도구다. 좌표, 엔진, GPU, RDKit, NumPy, 모델 또는 데이터셋을
읽거나 실행하지 않는다. 기존 benchmark gate를 대체하거나 승인하지 않는다.

## 실행

저장소 소스 체크아웃과 Python 3.10 이상만 필요하다. 설치된 제품 CLI는 아니다.
엔진 패키지의 `__init__`를 import하지 않도록 파일을 직접 실행한다.

```sh
python -S tools/analyze_pose_lineage.py tests/fixtures/pose_lineage_synthetic.json --format text
python -S tools/analyze_pose_lineage.py tests/fixtures/pose_lineage_synthetic.json --format json
python -S tests/unit/test_pose_lineage.py -v
python -O -S tests/unit/test_pose_lineage.py -v
```

출력은 stdout, 잘못된 입력은 일반적인 오류 메시지와 종료 코드 2다. 경로나 원시
예외를 오류에 출력하지 않는다. 도구 자체는 파일을 쓰지 않는다. 필요하면 사용자가
stdout을 로컬 파일로 redirect한다. 생성된 연구 결과는 저장소에 commit하지 않는다.
fixture의 수치는 전부 합성 예시이며 실험 결과가 아니다.

## 입력 계약 v1

`tests/fixtures/pose_lineage_synthetic.json`이 실행 가능한 완전한 예시다.
모든 객체는 명시된 필드만 허용한다. 누락 필드/추가 필드는 거부한다.

최상위 필드:

| 필드 | 의미 |
| --- | --- |
| `schema_id` | `betelgeuze.pose_lineage_export/1` |
| `unit` | 정확히 `angstrom` (자동 단위 변환 없음) |
| `threshold_angstrom` | 관측 전에 정한 양의 유한 임계값; 출력에 그대로 보존 |
| `top_k` | 정확히 `[1, 5]`; bool은 정수로 인정하지 않음 |
| `manifest` | 예상 case와 candidate ID의 전체 분모 |
| `cases` | 관측된 case의 부분집합; 빈 목록도 허용 |

각 manifest 행은 `case_id`, `candidate_ids`, `reference_id`, `frame_id`,
`mapping_id`, `method_id`를 가진다. candidate ID는 **case 내부에서** 유일하고
초기/정제 사이에 안정적이어야 한다. rank나 배열 위치로 ID를 추측하면 안 된다.
여러 자식 pose를 생성하는 branching/merging refinement는 v1 범위 밖이다.
`reference_id`는 없으면 `null`; 이 경우 해당 case의 모든 기하학적 성공/전이는
UNKNOWN이다. 나머지 식별자는 비어 있을 수 없다.

각 관측 case는 `case_id`, `candidates`, `selected_ids`를 가진다.
각 candidate는 `candidate_id`, `initial`, `refined`를 가진다.
초기와 정제 stage의 필드는 다음과 같다.

| 필드 | 허용값 및 의미 |
| --- | --- |
| `status` | `ok`, `failed`, `missing`, `not_attempted` |
| `metric` | 아래 metric 객체 또는 `null` |
| `validity` | `valid`, `invalid`, `unknown`: 외부 검사기의 선언 |
| `convergence` | `converged`, `not_converged`, `unknown`: 별도 선언 |

`ok`는 사용 가능한 pose 관측이라는 뜻이지 유효성 또는 force convergence의
증명이 아니다. 최대 평가 횟수에서 저장된 유효한 endpoint는 `ok`와
`not_converged`를 함께 가질 수 있다. 나머지 status에서는 metric이 `null`,
validity/convergence가 `unknown`이어야 한다. 실패했지만 마지막 좌표를
보존한 관측을 분석하려면 그 좌표의 가용성을 `ok`로, 수렴 상태는 별도로 선언한다.

metric 필드는 `rmsd_angstrom`, `reference_id`, `frame_id`, `mapping_id`,
`method_id`, `source_id`다. RMSD는 유한한 0 이상의 수이다. reference/frame/
mapping/method ID는 case manifest와 **정확하게 일치**해야 한다. 서로 다른
reference, atom correspondence, receptor frame 또는 metric 방법을 비교하지
않는다. case별로 서로 다른 reference는 허용한다. `source_id`는 측정/계산
출처 식별자이며 단계별로 달라도 된다. 값/출처는 모두 **선언된 것**이다.
이 도구는 외부 파일이나 source digest를 열어 인증하지 않는다.

`mapping_id`는 exporter가 이미 확정한 atom correspondence의 식별자다.
이름만 같다고 실제 원자 대응이 검증되는 것은 아니다. exporter는 동일한 원자
집합·대응·대칭 처리·비정렬 receptor frame 정책을 유지해야 한다. 도구는 atom
mapping, 대칭 탐색, ligand alignment, RMSD 계산 또는 clustering을 수행하지
않는다. 이를 보증할 수 없으면 metric을 `null`로 내보낸다.

`selected_ids`는 관측된 refined `ok` 후보의 순서 있는 ID 목록이다. 반복 ID나
없는 ID를 거부한다. `null`은 선택 결과 미관측, `[]`는 명시적으로 아무것도
선택하지 않았다는 뜻이다. 목록의 1-based 위치가 `selected_rank`다. 점수로
재정렬하지 않으며 동점 처리도 추측하지 않는다. Top1/5는 이 **선언된 선택 목록**의
앞 1/5개에 대한 요약이다. 전체 raw score ranking의 Top1/5라고 주장하지 않는다.

## 결측값과 전이 해석

- manifest에 있지만 관측 행이 없는 case/candidate는 `missing`으로 채운다.
  실패·누락·미시도 후보는 모두 분모에 남는다. 빈 manifest/빈 후보 domain은 거부한다.
- 후보의 성공은 `validity == valid`이고 선언된 RMSD가 임계값 이하일 때다.
  convergence는 성공 계산에 넣지 않으며 출력에 별도로 보존한다.
- `failed`/`not_attempted`는 사용 가능한 성공 pose가 없는 것으로 센다.
  `missing`이나 필요한 metric/validity 미관측은 UNKNOWN이다. reference 없는
  case에서는 실패/미시도라도 기하학적 결론은 UNKNOWN을 유지한다.
- case coverage는 성공 후보 하나라도 관측되면 YES이다. 모두 알려진 실패일 때만
  NO이고, 성공 없이 미관측이 있으면 UNKNOWN이다. 따라서 관측된 hit와
  coverage completeness는 다르다. `status_counts`와 원래 행을 함께 읽어야 한다.
- 후보별/케이스별 initial→refined 전이는 `recovery`, `loss`, `retained`,
  `no_success`, `UNKNOWN`이다. 초기 성공 pose가 정제 실패로 사라진 것도
  가용성의 loss에 포함된다. 이것은 정제 알고리즘의 인과적 책임을 증명하지 않는다.
  실패/미시도에 의한 loss는 측정된 RMSD 악화라는 뜻도 아니다. 원래 stage status와
  metric을 함께 확인해야 기하학적 악화와 관측 가용성 손실을 구분할 수 있다.
- `selection_loss`는 refined 성공 후보가 관측됐지만 선언된 Top1에 성공이 없을 때
  true이다. 선택 결과나 필요한 성공 판정이 미관측이면 `null`이다.

JSON의 미확정 bool은 `null`; 텍스트에서는 UNKNOWN이다. 원본 bytes의 실제 SHA-256을
`input_file_sha256`으로 출력한다. 이는 **입력 export bytes의 결합**일 뿐 원본 실험
출처 인증, 전자서명 또는 독립 검증이 아니다.

## 기존 계약과 경계

설계 확인 기준 main: `feba36dc7cbc137a0177b2e45346a836dcae1e08`.

- `tools/build_engine_v2_stage0_development_gate_ledger.py`의
  `no_oracle_candidate`, `oracle_but_top5_miss`, `top5_but_top1_miss`,
  `top1_invalid`는 기존 authenticated gate의 범주다. 여기서는 그 gate를
  재구현하거나 그 범주로 인증된 판정을 생성하지 않는다.
- `betelgeuze_engine_v2/benchmark/global_orientation_development_metrics.py`의
  fixed 64-slot, 2 Å, Top1/5, 결측 보존 구분을 참고하되 이 sidecar는 가변
  manifest의 일반적인 로컬 연구 export다. fixed64 metric과 수치가 같다고
  상호 교환 가능한 receipt가 되는 것은 아니다.
- `tools/build_engine_v2_source_paired_failure_atlas.py`의 historical 9-case
  authenticated archive 분석을 대체하지 않는다.

엔진/생성기/benchmark authority/패키지 초기화에는 변경이 없다. 출력의
`source_authentication_performed`, `scientifically_validated`,
`benchmark_gate_authority`, `causal_inference`는 항상 false다.
실데이터 docking 정확도, affinity, force-field 타당성, 수렴성, 제품 적격성 또는
외부 실행 권한을 입증하지 않는다.

## 자원 제한 및 검증 범위

UTF-8 JSON 최대 4 MiB, 중첩 최대 16, 최대 256 cases, case당 최대 1024 후보,
총 최대 16384 후보다. 식별자는 1..128자의 제한된 ASCII 문자
`A-Za-z0-9_.:/+-`이며 첫 문자는 영문/숫자다. 중복 JSON key, bool 수치,
NaN/Infinity/overflow, 음수 RMSD, 불일치 mapping/frame/reference/method를 거부한다.
이 제한은 입력 크기/개수 제한이며 프로세스 RSS 메모리나 실행 시간의 강제 quota는
아니다. OS 수준 자원 격리나 작업 실행 관리자를 제공하지 않는다.

단위 테스트는 표준 `unittest`이며 `-S`, `-O -S` 양쪽에서 실행한다.
합성 fixture, fail-closed 입력, 분모, 결측, 전이, CLI만 검증한다.
전체 저장소/엔진 테스트나 실제 과학적 검증이 아니다.
