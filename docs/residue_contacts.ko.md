# 잔기별 기하학적 접촉 진단 (오프라인 v1)

`tools/analyze_residue_contacts.py`는 명시적으로 제공한 수용체와 포즈 좌표를
읽어 잔기별 최소 원자 거리, 거리 구간, 접촉 잔기 집합 및 지정한 포즈 쌍의
집합 차이를 계산한다. **화학 결합, 수소 결합, 염다리, 결합 친화도 또는
도킹 정확도 판정기가 아니다.** 기존 aggregate contact-retention 계산이나
product report의 interaction-fingerprint abstention을 대체하지 않는다.
랭킹, admission, 실행 엔진, scientific E/F 실험, GPU 및 제품 경로를 변경하지 않는다.

## 실행

소스 체크아웃에서 Python 3.10 이상 표준 라이브러리만 사용한다. 패키지 설치,
프로젝트 `__init__`, native 라이브러리 또는 네트워크가 필요 없다.

```bash
python -I -S tools/analyze_residue_contacts.py tests/fixtures/residue_contacts/synthetic.json
python -I -S tools/analyze_residue_contacts.py tests/fixtures/residue_contacts/synthetic.json --format text
python -I -S -m unittest discover -s tests/unit -p 'test_offline_residue_contacts.py' -v
python -I -S -O -m unittest discover -s tests/unit -p 'test_offline_residue_contacts.py' -v
```

기본 출력은 stdout의 JSON 한 개이며 파일을 수정하지 않는다. 입력이나 예산이
잘못되면 종료 코드 2, 고정된 오류 코드만 stderr에 출력하며 부분 결과는 출력하지
않는다. 텍스트 출력에서도 사용자 식별자는 JSON escape한다. 호출 가능한 함수는
`analyze_contacts(raw: bytes, *, limits=None)`이고 동일한 검증을 적용한다.
소스 파일을 `importlib.util.spec_from_file_location`으로 직접 로드할 수 있다.
`limits`는 아래 하드 제한을 낮출 수만 있는 딕셔너리이다. 값은 0 이상의 정수이며
boolean은 허용하지 않는다. 외부 상태와 입력 바이트를 변경하지 않는다.

## 입력 계약

완전한 작은 예시는 `tests/fixtures/residue_contacts/synthetic.json`에 있다.
모든 객체에서 아래에 없는 키는 거부한다. 중복 JSON 키도 거부한다.

| 위치 | 필수 필드 | 선택 필드 |
|---|---|---|
| 최상위 | `schema_version`, `coordinate_frame`, `units`, `receptor`, `poses`, `comparisons` | `settings` |
| `receptor` | `residues` | `atoms` |
| 각 residue | `residue_id` | `chain`, `resnum`, `icode`, `name` |
| 각 receptor atom | `atom_id`, `residue_id`, `element`, `xyz` | 없음 |
| 각 pose | `pose_id`, `coordinate_frame` | `atoms` |
| 각 ligand atom | `atom_id`, `element`, `xyz` | 없음 |
| 각 comparison | `comparison_id`, `initial_pose_id`, `final_pose_id` | 없음 |
| `settings` | 없음 | `cutoff`, `bin_edges` |

- `schema_version`은 `residue_contacts_input.v1`, `units`는 `angstrom`이다.
- 하나의 수용체를 모든 포즈가 공유한다. 각 pose의 `coordinate_frame`은 최상위와
  정확히 같아야 한다. 프레임 이름은 제공자의 선언일 뿐 물리적 일치 증명이 아니다.
- 포즈 ID와 잔기 ID 및 comparison ID는 각각 배열 내 유일한 불투명 문자열이다.
  원자 ID는 수용체 내부 및 각 포즈 내부에서 유일해야 한다. 서로 다른 포즈 간의
  원자 대응 관계는 추정하지 않는다. 잔기 참조/포즈 참조는 존재해야 한다.
- 잔기 식별은 `residue_id`만 사용한다. chain/resnum/icode/name은 설명용이며
  선택적 문자열 또는 null이다. `resnum`도 문자열이다. chain이나 insertion code가
  다른 동일 번호 잔기를 합치지 않는다. 빈 metadata 문자열은 허용한다.
- 식별자/label은 최대 128자이다. 빈 ID, 제어문자, surrogate는 허용하지 않는다.
- `xyz`는 정확히 세 개의 유한 실수/정수이다. boolean, NaN, Infinity는 거부한다.
  오버플로 방지를 위해 좌표와 설정 수치는 절댓값 `1e150` 이하여야 한다.
- element는 명시적인 label이다. 화학 원소 타당성/원자가/양성자화 상태를 추론하지
  않는다. **H를 포함한 모든 제공 원자를 포함**하고 자동 필터를 하지 않는다.
- `poses`에 기대했던 포즈를 반드시 나열한다. 실패/미제공 포즈는 `atoms: null`
  또는 atoms 키 생략으로 남겨야 분모에 보존된다. 목록에서 누락된 포즈를 도구가
  알아내거나 제조할 수는 없다.
- 비교는 `comparisons`에 명시한 방향성 쌍만 계산한다. 빈 배열도 허용한다.
  ID가 다른 여러 comparison에서 동일한 쌍을 명시할 수 있다. 자동 all-pairs는 없다.

## 거리와 결측값

정렬, recentering, periodic boundary 조건을 적용하지 않는 유클리드 거리이다.
각 잔기에서 최소 `(distance, receptor_atom_id, ligand_atom_id)` 튜플을 선택한다.
따라서 동일 거리 tie도 결정적이다. 잔기/포즈/비교 출력은 각 ID 순으로 정렬한다.
입력 배열 순서 변경은 내용상 결과를 바꾸지 않지만 실제 바이트 digest는 바뀐다.
공유 좌표계 전체의 강체 변환은 수학적으로 거리를 보존한다. 일반 부동소수점
오차나 경계값 근처의 roundoff까지 없앤다는 주장은 아니다.

`cutoff` 기본값은 **8 Å**이고 `distance <= cutoff`가 접촉이다. 8 Å는 단순한
진단 기본값이며 화학적으로 검증된 기준이 아니다. `cutoff >= 0`이어야 한다.
`bin_edges` 기본값 `[2,4,8]`은 1~32개, 비음수, 엄격 증가 유한 수치이다.
구간은 `[0,e0], (e0,e1], …, (last,infinity)`이며 `bin_index`는 0부터 시작한다.
거리 0도 첫 구간에 포함된다. 각 결과에 실제 설정을 기록한다.

| 제공 geometry | 상태 | 거리 | contact 집합/개수 |
|---|---|---|---|
| atoms 키 생략 | `missing` | null | null |
| atoms가 null | `null` | null | null |
| atoms가 `[]` | `empty` | null (원자 쌍 없음) | null |
| 원자 존재, cutoff 내 쌍 없음 | `observed` | 실제 거리 | `[]` / 0 |

수용체 좌표가 missing/null이면 모든 포즈의 contact 결과도 unavailable이다.
수용체 원자 배열이 명시적으로 비어 있거나 특정 잔기에 원자가 없으면 해당
잔기 거리는 null, reason은 `empty_residue_atoms`, contact는 null이다.
빈 ligand의 reason은 `empty_ligand_atoms`이며 양쪽이 비어 있으면 이것이 우선한다.
알 수 없는 geometry는 `unavailable_geometry`이며 거리를 0으로 채우지 않는다.
빈 geometry는 접촉 부재를 입증하지 않는다. 모든 잔기에 수용체 원자가 존재하고
ligand 원자도 존재해야 `fingerprint_state`가 `complete`이다. 그렇지 않으면
`unavailable`이며 contact 집합/개수와 비교 결과는 null이다. 일부 잔기의 관측 가능한
거리/접촉 row는 유지하지만 완전한 fingerprint로 취급하지 않는다.

## 비교 및 다양성

- `gained_residue_ids = final − initial`, `lost_residue_ids = initial − final`.
- `shared_residue_ids = initial ∩ final`.
- Jaccard는 교집합 크기 / 합집합 크기이며 Jaccard distance는 `1 − Jaccard`이다.
- 양쪽 접촉 집합이 빈 경우 Jaccard와 distance는 **null**,
  reason은 `empty_contact_union`이다. gained/lost/shared는 알려진 빈 목록이다.
- 어느 쪽 fingerprint라도 unavailable이면 모든 비교 metric/list는 null,
  reason은 `unavailable_geometry`이다.
- `contact_set_diversity`는 supplied/available/unavailable 포즈 수와 이용 가능한
  서로 다른 접촉 집합 개수를 기록한다. 완전히 관측되었지만 cutoff 내 접촉이 없는 집합도 하나의 집합이며,
  available 포즈가 하나도 없으면 distinct 값은 null이다. 이 개수는 샘플링 충분성,
  구조적 다양성 또는 결합 양식 검증 지표가 아니다.

## 예산 및 출처

| 제한 키 | 하드 상한 |
|---|---:|
| `input_bytes` | 2,000,000 |
| `residues` | 10,000 |
| `receptor_atoms` | 50,000 |
| `poses` | 1,000 |
| `ligand_atoms` (모든 포즈 합계) | 50,000 |
| `comparison_pairs` | 5,000 |
| `distance_ops` | 5,000,000 |
| `output_rows` | 100,000 |
| `output_bytes` | 8,000,000 |

입력 바이트 제한은 파싱 전, count/연산/output-row 예산은 거리 계산 전에 검사한다.
연산 예산은 `receptor_atom_count × total_ligand_atom_count`이다. output-row 상한은
`residues × (poses + 3 × comparisons) + poses + comparisons`이며 비교의 세 잔기
목록 최악 크기도 포함한다. 거리 행렬을 만들지 않고 잔기별 최소값 하나를 유지한다.
직렬화 바이트 상한은 결과 생성 후 stdout 쓰기 전에 검사하며, callable도 JSON
직렬화 크기를 검사한다. 기본 한도 내 메모리 사용까지 8 MB로 제한한다는 뜻은 아니다.
어떤 예산 초과도 조용히 truncate하지 않는다. CLI는 input 한도 +1 바이트까지만 읽는다.

`input_sha256`은 **정확한 입력 바이트**에 대한 SHA-256이다. 서명, 인증, 원본 실험의
진실성 또는 과학적 검증을 뜻하지 않는다. 출력 schema는 `residue_contacts_output.v1`이다.
JSON은 timestamp/로컬 경로 없이 결정적으로 출력한다. scientific, benchmark, GPU,
product, customer, commercial 및 chemical/affinity/authentication claim은 모두 false이다.

작은 synthetic fixture와 unit test는 구현 계약만 확인한다. 실제 복합체, PDB/mmCIF
파싱, 정확도/성능 벤치마크, 통계적 보정, 검증된 force field 및 GPU 증거는 범위 밖이다.
