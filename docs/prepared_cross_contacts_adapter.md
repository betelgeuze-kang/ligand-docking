# 저장된 prepared-cross 단일 구조 → 접촉 분석 입력

`tools/project_prepared_cross_contacts.py`는 표준 라이브러리만 사용하는 읽기 전용
어댑터다. `betelgeuze.prepared_v2_cross_interaction/1.0.0`의 **이미 저장된 한
좌표 상태**를 `residue_contacts_input.v1`로 투영한다. 엔진, native 모듈, GPU,
에너지/힘 평가, 구조 최적화, 정렬, RMSD 계산을 호출하지 않는다.

## 의미와 범위

- `source_declarations.coordinate_frame_id`와 `prepared_state_id`가 두 분자의
  `provenance.metadata.state_declarations`에 명시적으로 일치해야 한다.
- 정확히 한 pose의 ID는 원본 `prepared_state_id`다. `comparisons=[]`이며,
  초기/최종 궤적, expected candidate 목록, 선택 순위, 유효성 또는 수렴을 만들지 않는다.
- `status=evaluated`는 원본의 선언일 뿐 도킹 성공 또는 refinement가 아니다.
  최신 8-candidate 실험이나 정확한 X0/x+ 실험으로 재해석하지 않는다.
- 명시된 수소를 포함한 모든 원자를 유지한다. 거리/접촉은 기하학적 진단일 뿐
  화학적 상호작용, 친화도, 검증된 과학/벤치마크/제품 성능을 의미하지 않는다.
- 이 도구는 원본 canonical 시스템 전체를 검증하는 validator가 아니다.
  관련 구조/식별 필드만 검증하며, 다른 필드는 허용하되 과학적 증거로 사용하지 않는다.
  에너지, 힘, 결합, 원자 charge/mass와 임의 metadata는 투영하지 않는다.

## 사용

```bash
python -S tools/project_prepared_cross_contacts.py SOURCE.json \
  --expected-sha256 EXPECTED_EXACT_SOURCE_SHA256
python -S tools/project_prepared_cross_contacts.py SOURCE.json \
  --expected-sha256 EXPECTED_EXACT_SOURCE_SHA256 --format receipt
```

기본 `--format contacts`는 접촉 분석기 입력 JSON만 stdout에 출력한다.
`--format receipt`는 작은 출처 영수증만 출력한다. 파일을 쓰거나 덮어쓰는 옵션은
없으며 호출자가 stdout을 보관한다. 잘못된 입력은 stdout 없이 종료 코드 2와
고정 오류 코드로 거부한다. 파일 경로/원본 값을 오류에 포함하지 않는다.

소스 SHA-256 인자는 필수이며 **정확한 바이트 일치**만 보장한다. 인증, 신뢰된
생산자, 측정 진실성을 보장하지 않는다. callable API는
`project_prepared_cross(raw: bytes, *, expected_sha256: str)`로
`(contacts_dict, receipt_dict)`를 반환한다. import 시 파일 I/O가 없다.

PR #607의 `tools/analyze_residue_contacts.py`가 설치된 체크아웃에서는 출력 파일을
그 도구에 입력하면 된다. 두 도구는 서로 import하지 않는다. 이 어댑터 자체는
main 기반 독립 변경이며 #607을 병합하거나 런타임 의존성으로 가져오지 않는다.

## 엄격한 검증 및 한계

- 소스 최대 32 MiB, JSON 중첩 64. UTF-8 오류, 중복 키, JSON NaN/Infinity 및
  `1e999` overflow를 거부한다. CLI는 최대 상한+1 바이트만 읽는다.
- 래퍼 schema는 `betelgeuze.engine_v2_canonical_system/1.0.0`, topology schema는
  `betelgeuze.all_atom_system/2.0.0`여야 한다.
- topology/coordinates 단위가 모두 `angstrom`이어야 한다. canonical cell 미제공
  필드 형태인 두 `cell_periodic: null`과 `cell_vectors: null`이 모두 필수다.
  여기서 null은 cell이 제공되지 않았다는 뜻이다. 투영은 Euclidean/no-PBC
  거리를 사용하며, 실제 분자계가 물리적으로 비주기적이라는 증거가 아니다.
  필드 누락을 비주기로 추측하지 않는다. 선택적 topology `cell_vectors`가 있다면 null이어야 한다.
- 좌표는 정확히 `{"$tensor":{"dtype":"float64","shape":[1,N,3],"values":[...]}}`.
  각 값은 단일 `$float_hex` 필드의 명시적 소문자 hex float 문자열이어야 한다
  (예: `-0x1.0000000000000p+0`). bool shape, 잘못된 길이, 숫자 직접 입력,
  `float.fromhex(token).hex() == token`이 아닌 손실/비정규 표현, NaN/Inf, 좌표 절댓값 `1e150` 초과를 거부한다.
- 원자/잔기/chain 인덱스는 0부터 순서대로 정확히 일치해야 한다. residue atom
  목록과 chain residue 목록은 각각 참조 관계의 정확한 순서 있는 partition이어야
  한다. 비어 있는 원자군/잔기군, 중복/누락/잘못된 참조를 거부한다.
- 원자 name/element, 잔기 name/sequence_number/insertion_code, chain_id가 필수다.
  원소와 이름은 추론하지 않는다. 원소 문자열은 보존하며 화학적 정합성은 검증하지 않는다.
  chain ID와 insertion code의 빈 문자열은 유효하며 그대로 보존한다.
- ID는 원본 인덱스 기반 `receptor:atom:00000`, `ligand:atom:00000`,
  `receptor:residue:00000` 형태(5자리 0-padding)다. 같은 residue label도 합치지
  않는다. 접촉 분석기 동률 순서는 거리 → receptor 원자 인덱스 → ligand 원자
  인덱스다. 잔기 이름/chain/sequence/insertion은 consumer metadata로 유지하며
  원자 이름은 검증하되 consumer schema에 필드가 없어 출력에 추가하지 않는다.
- 분자당 최대 50,000 원자/10,000 잔기, 최대 5,000,000 거리 연산, 투영 JSON
  2,000,000 바이트다. 접촉 분석기의 한계를 완화하지 않는다.
- 식별/label 문자열 최대 128자이며 제어 문자/단독 surrogate를 거부한다.
  원본 system/source ID는 최대 4,096자이고 경로일 수 있으므로 영수증에 직접
  노출하지 않고 UTF-8 바이트 SHA-256만 기록한다.

## 영수증과 직렬화

`serialize_json(value)`는 `sort_keys=True, ensure_ascii=True, allow_nan=False`,
구분자 `(',', ':')`인 compact JSON + 정확히 한 LF를 ASCII bytes로 만든다.
영수증 `projected_sha256`/`projected_bytes`는 **LF를 포함한 실제 contacts stdout**에
결합한다. 소스 digest는 재직렬화가 아닌 입력 원본 바이트에 결합한다.

원본 schema 및 status/saved-state/frame의 UTF-8 바이트 해시, 분자별 원자/잔기/chain 수, 제한,
거리 연산 상한, source/system ID의 해시와 원본의 declared source/system/coordinates
해시를 기록한다. `declared_*` 해시는 원본의 선언을 보존한 것이며 해당 canonical
serialization을 재계산/인증한 값이 아니다. 입력 전체 바이트 hash와 혼동하지 않는다.
영수증에는 원본 label/path 문자열이 직접 포함되지 않는다. 반면 contacts 출력은
필수 원본 state/frame 및 잔기 metadata를 보존하므로 익명화 도구가 아니다.
`unrelated_source_fields_interpreted=false`, `canonical_system_hashes_recomputed=false`도 명시한다.
run 전용 ID가 없는 source에 run ID를 만들어 붙이지 않는다. 정확한 입력 hash와
선언된 saved state만 식별자로 사용한다. 모든 promotion claim은 false다.

## 테스트

```bash
python -m unittest discover -s tests/unit -p test_project_prepared_cross_contacts.py -v
python -O -S -m unittest discover -s tests/unit -p test_project_prepared_cross_contacts.py -v
```

fixture는 tiny synthetic 관련-field fixture이며 완전한 과학 canonical-system
검증 예제가 아니다. CI는 이 fixture만 사용한다. 실제 입력/결과/개인 경로/실험
bundle은 커밋하지 않는다. parser admission과 합성 테스트 통과는 과학 검증이 아니다.
