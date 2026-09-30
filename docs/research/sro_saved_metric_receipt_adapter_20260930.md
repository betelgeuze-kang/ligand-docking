# 저장 SRO metric receipt 형식 adapter — 2026-09-30

종료된 R2의 고정 exporter는 JSON뿐 아니라 JSONL·log·lock을 포함한 전체
`actual_receipt_refs`를 내보낸다. 원래 `recovery_protocol.py`의
`evaluate_saved_results`는 모든 참조를 `json.loads`로 읽으므로 JSONL에서
`Extra data`가 발생한다. 새 adapter는 전체 원본 참조를 먼저 인증한 뒤
JSON 전용 metric 입력을 별도 파일로 제공한다.

기존 prospective packet, generator, recovery protocol, frozen campaign/source는
수정하지 않는다. 공개 함수는
`project_saved_metric_input(saved_results_ref, export_receipt_ref, output)`이며
stdlib만 사용하고 evaluator를 import하거나 호출하지 않는다.

## 입력과 출력 계약

입력 pin은 `{path, sha256, bytes}`의 정확한 형태다. 호출자가 제공한 신뢰된
pin이 인증의 신뢰 경계다. 파일은 canonical 절대 경로와 regular file이어야
하고, 선언 크기는 256 MiB 이하로 제한한다. `O_NOFOLLOW`로 열고 파일의
`st_size`가 선언 크기와 같은지 **읽기 전에** 확인한다. 열린 파일과 경로의
device/inode/size/mtime/ctime 및 SHA-256을 대조한다.

반환값은 다음 세 pin이다.

| 키 | 출력 파일 | 목적 |
|---|---|---|
| `projection_ref` | `saved-metric-input.json` | 원래 evaluator에 넘길 JSON 전용 참조 목록 |
| `validation_receipt_ref` | `full-reference-validation.json` | 전체 실제 참조와 control/source 참조의 인증 기록 |
| `omission_manifest_ref` | `non-json-reference-omissions.json` | projection에 포함하지 않은 참조와 이유 |

출력 디렉터리는 새로 생성하며 frozen campaign archive 밖에 있어야 한다.
기존 파일이나 디렉터리를 덮어쓰지 않는다. 원본 artifact를 삭제하지 않는다.

## 인증과 projection 순서

1. `saved-recovery-results.json`과 sibling `export-receipt.json`의 pin·역할을
   확인한다. 고정 protocol SHA, source-development authority와 새 계산 0회
   선언을 유지한다.
2. parent exporter source SHA
   `b27c623d2fff44375f917d779894a4a1406a08072785389fa1c2d513b563611d`와
   `source/campaign_supervisor.py`의 역할 경로를 확인한다. campaign의
   plan/review 및 driver/oracle source·spec의 실제 pin과 역할을 확인하고,
   review의 plan/driver 연결·사례 시작 전 timestamp를 대조한다.
3. schema `/2`에서는 campaign·plan·export·campaign-start의 operational
   revision과 연결을 확인한다. resume·budget reset·protocol/source role 변경은
   허용하지 않는다. schema `/1`과 `/2`를 영수증에 구분해 기록한다.
4. rich 4-case 상태·순서·work와 legacy export 사례 집합을 대조한다.
   시작된 사례의 terminal pin과 전체 actual 목록을 모두 raw 크기·해시로
   인증한다. legacy 결과의 목록도 parent campaign 목록과 정확히 일치해야 한다.
5. **모든 actual 참조의 raw 인증 후** JSON과 JSONL 내용을 검사한다.
   JSON receipt는 object여야 하며, 중복 키·비유한 JSON 숫자·overflow를
   거부한다. JSONL은 각 줄에 같은 검사를 적용하고 끝나지 않은 줄·빈 레코드를
   거부한다. log·lock·source는 해당 명시적 역할에 따라 raw bytes를 인증한다.
6. 경로 역할 allowlist로 JSON receipt만 projection의 `actual_receipt_refs`에
   남긴다. 그 밖의 case/endpoints/work/gates/authority/좌표 결과 필드는
   원본과 동일하게 보존한다. 필수 completed JSON receipt 누락을 거부한다.
7. 전체 pin을 다시 읽어 전후 동일성을 확인한 후 세 결과 파일을 게시한다.

분류는 내용에 대한 판단이나 성공 여부에 따라 바뀌지 않는다. JSONL·log·lock은
비JSON 형식이라는 이유로 projection에서만 제외한다. 원래 exporter가 legacy에서
생략한 rich-only 실패 사례는 새 legacy 결과로 만들지 않는다. 해당 사례의
JSON도 전체 validation receipt와 omission manifest에 남는다. source 참조는
control reference validation과 source provenance에 pin·역할로 보존한다.

전체 원본 legacy 참조 수, campaign 전체 참조 수, 사례별 원본/JSON 수,
형식별 수와 제외된 legacy 형식별 수를 기록한다. rich 4-case 상태와 legacy
completed 사례만 있는 결과는 별도로 유지하며 미시작 작업은 unknown으로 남긴다.

## 검증 의미와 한계

parent saved binding이 export보다 먼저 확인됐다는 근거는 고정 exporter가
게시한 export receipt와 그 source/plan/review/campaign 연결이다. 이는
**인증된 parent의 saved-binding 주장**이며 parent 전체 lineage·물리 검증을
adapter가 다시 수행했다는 뜻이 아니다. source pin은 source를 실행한 기록이나
독립 force 검증을 대신하지 않는다. adapter는 분자 구현·native·OpenMM을
실행하지 않으며 새 force/score/graph/optimizer 관측을 만들지 않는다.

호출자는 `projection_ref` 내용을 원래 `evaluate_saved_results(packet, submitted,
review)`에 넘겨야 한다. 원래 full packet/review 검사, 평가 전용 reference의
RMSD 정책, 정해진 `0.001` force·`1e-8` same-math gate는 그대로 적용된다.
이 adapter는 packet 검사를 대체하거나 권한·source role·허용오차를 바꾸지 않는다.

## Synthetic 검사

전용 테스트 **27 passed**, 0.63초. 테스트 fixture의 모든 데이터와 실행 source는
synthetic이며 실제 ligand·reference·control·protected 본문을 읽지 않는다.
고정 source SHA는 fixture 안에서만 명시적으로 대체하며 source를 실행하지 않는다.

Mutation 범위는 hash/bytes/body, 중복 JSON 키와 비유한 숫자, 중복 참조,
case status/work/authority/endpoint policy, 경로·receipt 역할 주입, JSONL
내용/hash 불일치, 필수 JSON 누락, 전후 참조 변경, create-only 출력 및
schema `/1`·`/2` 구분이다. oversized declared bytes와 사전 `st_size` 불일치도
읽기 전에 거부한다.

최초 검사에서 강화된 사전 size 거부를 테스트가 hash 거부 문구로 기대해
1건 실패했다. 같은 길이의 synthetic 좌표 본문 변조로 수정해 해시 거부를
직접 검사했고 최종 검사가 통과했다. 실제 frozen export 및 원래 evaluator와의
통합 검증은 root의 별도 기록에 속한다.
