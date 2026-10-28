# 고정 후보의 접촉 다양성 선택 비교

## 연구 범위

이 도구는 기존의 점수 순위·direct RMSD 선택에 **기하학적 잔기 접촉 다양성 조건 하나**를 더한 효과를 비교하는 실험용 stdlib 분석기다. 기본 선택 정책으로 채택하라는 권고가 아니다. 후보 생성, 최적화, 점수 산출, strain admission, 원자 매핑, RMSD/접촉 계산을 새로 수행하지 않는다. 분자 엔진·native·Torch·RDKit를 import하지 않는다.

기존 `betelgeuze_product/cpu_refinement_v1_2/selection.py`는 score 방향에 따른 정렬, 정확한 좌표 중복 제거, receptor-frame direct RMSD의 greedy 다양성 선택을 이미 제공한다. upstream의 strain·수렴·성공 조건도 그대로 둬야 한다. 본 도구는 소스에서 확인한 정렬·선택 규칙을 supplied evidence에 적용하지만, 기존 실제 selector와 나란히 실행한 통합 동등성 검증은 **수행하지 않았다**.

## 실행과 파일

checkout에서 설치 없이 실행한다. 입력의 바이트 해시는 실행 전에 계산한다.

```sh
python -I -S tools/compare_contact_diversity_selection.py input.json --expected-sha256 <SHA256>
python -I -S tools/run_contact_selection_synthetic.py tests/fixtures/contact_selection_synthetic.json --expected-sha256 5e4174ac18cd21f8fe3da494e7ffab0c2e33631f4c692b532ae273ca0f7e1f03
python -m unittest discover -s tests/unit -p test_contact_diversity_selection.py -v
python -O -S -m unittest discover -s tests/unit -p test_contact_diversity_selection.py -v
```

실험 runner는 자신의 디렉터리에 있는 고정된 선택기 파일만 읽는다. 입력이 지정한 Python 코드·모듈·명령을 실행하지 않는다. 두 CLI 모두 stdout JSON만 출력하며 입력/결과 파일을 쓰지 않는다. 종료 코드 0은 보고서 생성 성공이고, 2는 잘못된 계약·해시·접근·예산 오류다. 과학적으로 좋은 후보를 찾았다는 종료 코드가 아니다. 공개 오류에는 파일 경로나 입력 내용을 싣지 않는다.

## 선택 입력과 증거의 한계

스키마는 `contact_selection_input/1`이다. 작은 합성 예제의 `selection_input`을 참고한다. root에 reference RMSD, target label, 임의 추가 필드를 넣으면 거절한다.

- `context`: chemical_state, frame, atom_mapping_sha256, receptor_sha256. 화학 상태·원자 대응·수용체 digest는 제공자가 선언한 공통 문맥이다. **수용체 digest를 실제 원자 좌표나 #607 출력에 독립 대조하지 않는다.** 문맥 해시가 다른 실행의 혼용을 자동 증명하거나 방지하는 인증은 아니다. 실제 생산자에게 같은 수용체/화학 상태/원자 순서를 보장할 책임이 있다.
- `score_descriptor`: model, units, minimize/maximize 방향. 서로 다른 분자·미세상태·점수 모델 간 점수를 섞어 정렬하지 않는다. 이 도구가 해당 모델의 물리적 적용성을 판단하지는 않는다.
- `expected_candidate_ids`: 원래 기대한 모든 후보 ID. candidate가 누락돼도 분모에서 없애지 않는다.
- `candidates`: eligible/ineligible/failed/unknown 상태. eligible은 유한 score, proposal_index, baseline/refined variant, coordinates_sha256 및 selection_eligible/pose_valid/validity_complete가 모두 true여야 한다. 이 선언을 재검증한 것은 아니다. 나머지 상태는 ID·상태만 허용하며 모두 동일하게 선택 대상에서 제외하고 상태별 수에 남긴다.
- `rmsd`: metric=`direct_rmsd_in_receptor_frame`, frame, atom_mapping_sha256, 모든 eligible 쌍의 거리. 각 쌍은 양쪽 candidate ID·coordinate digest와 유한 비음수 Å 거리를 담는다. 방향을 바꾼 중복 쌍은 거절한다. 같은 좌표 digest이면 거리는 0이어야 한다. 좌표 자체를 받지 않으므로 실제 RMSD를 재계산하거나 metric의 참값을 증명하지 않는다. 프레임/매핑 표기가 일치하는지만 검사한다.
- `contact_report`: PR607의 `residue_contacts_output.v1` 출력에서 settings/residues/poses와 식별 필드를 소비한다. 같은 report에 담긴 공통 frame/settings/residue IDs를 사용한다. report 전체의 canonical SHA256을 `contact_report_sha256`과 비교한다. 이 해시는 producer authenticity가 아니다.
- `contact_bindings`: candidate ID → report pose ID → candidate coordinate digest를 명시한다. 이는 제공자의 연결 선언이다. #607 출력에는 per-pose coordinate digest가 없으므로 실제 접촉 계산의 좌표를 독립 증명하지 않는다.

본 도구는 #607 전체 report의 재검증기가 아니다. nearest_by_residue의 모든 거리와 contact를 다시 계산하지 않으며 그 상세 행의 정합성을 전수 검사하지 않는다. 사용되는 contact IDs/개수/상태/geometry_state의 명백한 모순, 잘못된 residue 참조, 동일 좌표의 상충하는 observed fingerprint는 거절한다. 정상 provenance가 필요한 실제 사용자는 upstream의 정확한 입력·출력과 별도 검증을 확보해야 한다. 합성 fixture의 fingerprint는 **직접 선언한 합성 집합**이지 실제로 #607을 실행해 얻은 분자 결과가 아니다.

## 세 정책과 동일 분모

모든 정책은 동일 admitted 후보와 점수 정렬 `(score 방향, proposal_index, candidate_id, variant)`를 사용한다. 선택된 좌표 digest와 같은 후보를 중복으로 제거한다. rejected 후보의 digest를 selected-set에 넣지 않는다. 기존 순서를 따라 coordinate 중복 → RMSD 조건 → K 용량을 판정하고 contact arm에만 추가 조건을 적용한다.

1. energy_only: 중복을 제외하고 점수가 좋은 순서로 최대 K개.
2. energy_rmsd: 선택된 모든 후보와 거리가 rmsd_min_angstrom 이상인 후보만 수용. `<`가 탈락 조건이므로 경계는 포함한다.
3. energy_rmsd_contact: 위 조건과 함께 모든 선택된 후보와 Jaccard distance가 contact_distance_min 이상이어야 한다.

Jaccard distance는 `1 - |A∩B|/|A∪B|`다. 빈 집합과 비어 있지 않은 집합은 거리 1이지만, 두 집합이 모두 비었으면 정의되지 않는다. 후자를 0이나 1로 만들지 않고 해당 결정을 `contact_comparison_unknown_empty_union`으로 기록하며 전체 contact arm 상태도 unknown으로 둔다. 단순 거리 접촉은 화학적 상호작용·친화도 증거가 아니다.

원래 후보가 missing/unknown이면 알려진 후보로 선택 결과를 만들 수 있어도 모든 arm의 상태는 unknown이다. RMSD 쌍이 하나라도 누락되면 RMSD를 쓰는 arm 전체를 unknown으로 두고 선택하지 않는다. 필요한 fingerprint가 누락/비관측이면 contact arm 전체가 unknown이며 baseline의 후보를 줄이지 않는다. 원래 admitted cohort를 complete-case subset으로 바꿔 성공률을 높이면 안 된다.

K는 **최대 출력 용량**이다. 조건을 만족하는 후보가 부족하면 K보다 적게 반환하고 unfilled_slots를 남긴다. 정책 위반 후보로 조용히 채우지 않는다. 따라서 세 정책이 항상 같은 개수의 결과를 낸다고 주장할 수 없다. evidence가 없어 선택을 못 한 경우에도 빈 슬롯이 생기므로 상태와 슬롯 수를 함께 읽어야 한다.

## 고정 합성 실험과 음성 결과

`contact_selection_synthetic.json`은 첫 실행 전에 다음 SHA256으로 고정했다.

`5e4174ac18cd21f8fe3da494e7ffab0c2e33631f4c692b532ae273ca0f7e1f03`

정책은 K=2, RMSD 최소 0.5 Å, contact distance 최소 0.5다. 이 값은 합성 제어 사례용이지 화학적 최적값이 아니다. 결과를 본 뒤 thresholds나 case를 바꾸지 않았다. helpful / harmful / no-effect / underfill / missing-contact / empty-union / missing-candidate의 7개 사례를 모두 보존한다.

첫 두 사례는 **동일 선택 입력에 서로 다른 평가 label**을 붙여 정보 누출과 tradeoff를 시험한다. 서로 독립인 두 분자처럼 세면 안 된다. 선택을 끝낸 뒤 runner가 별도 evaluation의 target IDs를 읽는다. runner는 selector에 labels/case ID를 전달하지 않는다.

관측 결과:

- helpful 사례: contact 조건이 목표 후보를 보존했고 baseline은 보존하지 못했다.
- harmful 사례: 같은 선택이 다른 목표 label에는 불리했다.
- no-effect 사례: 선택이 같았다.
- underfill 사례: contact 조건으로 1개만 반환하고 목표를 잃었다.
- missing-contact, empty-union, missing-candidate 사례는 contact 결과를 unknown으로 유지했다.
- 고정 전체 7개 중 energy-only/RMSD는 보존 4, 미보존 2, unknown 1; contact는 보존 2, 미보존 2, unknown 3이었다.

이 숫자는 손으로 구성한 정책 시험의 빈도이며 도킹 성능 추정이 아니다. 관측 분모도 다르므로 비율로 바꿔 우열을 비교하면 안 된다. 접촉 다양성은 도움이 될 수도 있고 적절한 후보를 버릴 수도 있어 **기본 정책 채택을 정당화하지 못한다**. 실제 분자 자료를 이용한 독립적인 고정 후보 실험이 추가로 필요하다.

## 자원·상태·출시 경계

입력/출력 각각 4 MiB, JSON 깊이 24, 후보 256, pair 32,640, residue 10,000, contact IDs 합계 100,000으로 제한한다. Python API는 파싱된 계약 입력용이며 비신뢰 바이트는 load_bytes/CLI를 사용한다. 이 한도는 OS RSS/process-tree sandbox가 아니다.

scientific_validation, producer_authenticity_verified, rmsd_recomputed, upstream_admission_recomputed, chemical_interactions, whole_selector_integration_equivalence, receptor_identity_independently_verified, contact_geometry_recomputed, full_contact_report_validated는 모두 false다. 실제 E/F 실행은 0회다. 실제 도킹 정확도·GPU·상업적 성능을 주장하지 않는다. 기존 엔진·selection 기본값·admission은 변경하지 않는다.
