# 2026-11-03 실제 redocking 개발 실행: 결과와 다음 변경의 근거

이번 실행은 고정된 개발 사례에서 실행 실패, 후보 품질, 최종 순위를 분리해 조사하기 위한 것이다.
Stage 1의 2개와 Stage 2의 32개 시도를 모두 수집했지만, Stage 2의 1개는 결과가 미관측이다.
따라서 분석 명칭은 `partial`이며, `claim_safe=false`, `primary_claim_eligible=false`를 유지한다.
세부 수치·사례별 결과·원본 해시는 [분석 JSON](redocking_development_stages_20261103.json)을 기준으로 한다.

## 1. 실행 범위와 소스

| 항목 | 고정값 또는 관측값 |
|---|---|
| 기준 main | `4c6e4b9fba670e325be37b538e054af88f65dc01` |
| 기준 tree | `a62bbf24c1b304eeeffef0c4ed7382eb0deb3beb` |
| 실행 head | `b41636642a93d22dba8ff6f7e67df5250d17647d` |
| 실행 tree | `1d2dc1515e2c150d510263b96132b7b973aabe0a` |
| GitHub Actions | [run 41651548827](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41651548827), attempt 1 |
| 실행 창 | 2026-11-03 14:13:21–15:00:07 UTC; 설치·작업 분기·집계를 포함 |
| 완료 상태 | 전체 run `failure`; [aggregate job 125997636848](https://github.com/betelgeuze-kang/ligand-docking/actions/runs/41651548827/job/125997636848)은 `success` |
| 사례 선택 | 사전에 고정한 역사적 순서: smoke index 0–1, development index 2–33 |
| 난수 | 사례당 1 seed, `2026072700 + global_index`; 반복 실행 없음 |
| EngineV2 | Python reference scorer, V7 경로, 준비 성공 시 64개 후보 슬롯, 최종 5개 pose |
| 외부 모드 | 동일 GNINA 1.3.2 바이너리로 Vina 모드와 GNINA 모드 실행 |
| 자원 상한 | CPU 1 설정, case wall 900초, 외부 subprocess 각 300초, 표본 RSS 6 GiB |

실행은 별도 개발 branch에서 수행했고 기준 main의 수치 소스는 변경하지 않았다.
4개 development shard는 start index 2, 10, 18, 26에서 각각 8개를 처리했다.
선정·seed·상한은 [개발 manifest][manifest]에 기록되어 있으며 결과를 보고 사례를 교체하지 않았다.
원본의 legacy `analysis_scope`는 수정하지 않고 별도 집계에서 `contaminated_development`를 명시했다.
이 32개는 이미 관측된 개발 집합이며 새 holdout이나 Fresh128 결과가 아니다.

## 2. 지표와 분모

RMSD는 PoseBusters 0.3.1의 고정 receptor-frame heavy-atom RMSD이며 성공 경계는 2 Å 이하이다.
`valid TopK`는 같은 pose가 RMSD 경계, geometric validity, chemical validity를 모두 만족하는 경우다.
`oracle`은 기록된 EngineV2 후보 중 RMSD 경계를 만족하는 후보가 있는 사례 수다.
`valid oracle`은 그중 동일 후보가 두 validity 조건까지 만족하는 사례 수다.
Stage 2 운영 지표의 분모는 항상 32이며 준비 실패와 미관측 사례도 포함한다.
미관측은 운영상 미회복으로 계수하되 엔진 실패 결과나 RMSD 값을 만들어 넣지 않는다.
JSON의 missing-observation bounds는 `[관측 성공/N, (관측 성공+미관측)/N]`이며 신뢰구간이 아니다.

## 3. Stage 1: smoke 2개

| 사례 | EngineV2 후보 / 최저 RMSD | EngineV2 valid Top1/3/5 | 외부 두 모드 valid Top1/3/5 |
|---|---|---|---|
| `5SAK_ZRY` | 64개 / 2.181 Å | 0 / 0 / 0 | 각각 1 / 1 / 1 |
| `5SB2_1K2` | 64개 / 4.302 Å | 0 / 0 / 0 | 각각 1 / 1 / 1 |

두 case 모두 정상 종료와 cleanup을 확인했으며 6개 엔진 receipt가 존재한다.
smoke의 목적은 실행·증거 수집 경로 확인이며 정확도 임계치를 다음 단계 입장 조건으로 쓰지 않았다.
이 2개를 Stage 2의 분모에 합쳐 성공률을 계산하지 않는다.

## 4. Stage 2: 고정 개발 집합 32개

| 엔진 표기 | 관측 row | 성공 row / 실패 row / 미관측 | valid Top1 | valid Top3 | valid Top5 |
|---|---:|---:|---:|---:|---:|
| EngineV2 | 31 | 28 / 3 / 1 | 1/32 (3.125%) | 3/32 (9.375%) | 3/32 (9.375%) |
| Vina 모드 | 31 | 29 / 2 / 1 | 16/32 (50.000%) | 23/32 (71.875%) | 23/32 (71.875%) |
| GNINA 모드 | 31 | 29 / 2 / 1 | 18/32 (56.250%) | 23/32 (71.875%) | 24/32 (75.000%) |

성공 row는 출력 계약을 완료했다는 뜻이며 RMSD 회복 성공을 뜻하지 않는다.
EngineV2의 oracle은 6/32, valid oracle은 3/32이다.
Vina의 validity를 적용하지 않은 Top5는 24/32로, valid Top5 23/32와 구분된다.
미관측 1개를 고려한 EngineV2 valid Top1 범위는 3.125–6.250%, valid Top5는 9.375–12.500%다.
전 사례의 세 엔진 결과가 갖춰지지 않아 paired-case bootstrap은 수행하지 않았다.

## 5. EngineV2 실패 분해

분류는 JSON의 상호 배타적인 첫 일치 규칙이며 정제 후 기록된 후보를 기준으로 한다.

| 분류 | 사례 수 | 관측의 의미 |
|---|---:|---|
| `no-close` | 22 | 기록된 후보 중 RMSD ≤ 2 Å가 없음 |
| `close-invalid` | 3 | 가까운 후보는 있으나 joint-valid인 가까운 후보가 없음 |
| `top5notTop1` | 2 | valid Top3/5 회복은 있으나 Top1 회복은 없음 |
| `success` | 1 | valid Top1 회복 |
| `prep` | 3 | `unsupported_large_ring_system`, 후보 생성 전 지원 범위 실패 |
| `unobserved` | 1 | `6YSP_PAL`의 전체 case 시간 제한, 엔진 receipt 없음 |

`no-close` 22개는 현재 후보를 재정렬하는 것만으로 회복할 수 없다.
다만 생성 직후 좌표와 정제 전후 RMSD가 모두 남아 있지 않아 생성 실패와 정제 중 손실을 분리할 수 없다.
`close-invalid`는 `6XM9_V55`, `6YQV_8K2`, `6Z4N_Q7B`이며 가까운 후보에 단백질 거리 검사 실패가 남았다.
Top1 순위 차이는 `6YQW_82I`, `6Z0R_Q4H` 두 사례에서 구체적으로 관측됐다.
전자는 최종 순위 3/4의 RMSD가 0.950/0.910 Å, 후자는 순위 3이 1.184 Å이며 모두 valid이다.
이 두 사례는 같은 후보 풀에서 점수 항과 최종 선택을 조사할 작은 회귀 fixture 후보이다.

## 6. 후보 수준에서 확인한 것

준비된 28개 사례의 64개씩, 총 1,792개 기록 후보가 모두 scorer 성공 상태였다.
이 중 geometric와 chemical을 함께 만족한 후보는 76개, RMSD ≤ 2 Å는 11개, 세 조건을 모두 만족한 후보는 5개다.
후보별 검사 실패 수는 중복 가능하며 `minimum_distance_to_protein` 1,705개, `volume_overlap_with_protein` 1,514개였다.
`internal_energy`는 562개, `internal_steric_clash`는 509개에서 실패했다.
기록된 정제 penalty는 1,780개에서 감소하고 12개에서 증가했으며, 감소한 후보 중 1,704개는 여전히 joint-invalid였다.
이 비교는 저장된 binary64 penalty의 전후 대소관계이며 물리적 E/F 감소나 RMSD 개선 측정이 아니다.
V7 penalty, ScorerV1 최종 점수, PoseBusters validity를 동일 목적함수로 취급하지 않는다.
현재 결과만으로 가중치 오류, gradient 오류, torsion 기능 부재 또는 line search 부재를 판정할 수 없다.
후속 계측에는 objective ID·rank-score ID·단위·실제 좌표 hash와 proposal/refinement/final lineage를 함께 묶어야 한다.

## 7. 시간 병목: 진단 비용과 엔진 시간을 분리

| Stage 2 관측 | 시간 또는 범위 |
|---|---:|
| 전체 32개 case wall 합계 | 7,104.363초 |
| 정상 종료 31개 case wall 합계 | 6,203.282초 |
| 관측된 EngineV2 전체 후보 diagnostic 합계 | 3,222.166초, 31개 row |
| 위 diagnostic / 정상 종료 case wall | 51.94% |
| timeout case wall / CPU | 901.081초 / 897.851초 |
| diagnostic 최대 관측 | `6XHT_V2V` 534.145초; 해당 case wall 773.024초 |

31개 diagnostic 관측에는 준비 실패의 실제 0초가 포함되며 timeout의 미관측 시간은 `null`이다.
51.94%는 완료 사례의 end-to-end 비용 구성에 대한 관측이며 timeout 구간의 비용을 배정한 값이 아니다.
여러 shard의 case wall 합계는 workflow의 실제 경과 시간이나 병렬 처리량과 다르다.
EngineV2 row runtime은 전체 후보 diagnostic 시간을 제외하므로 외부 row runtime과 단순 비율 비교하지 않는다.
동일 pocket 원천이더라도 pocket 기하와 검색 노력이 다르고, 외부 두 모드는 동일 바이너리를 공유한다.
따라서 이 결과로 공정한 speedup, 엔진 일반 성능 우열, 단일 함수의 실행 시간을 주장하지 않는다.

## 8. 시간 제한과 준비 실패의 실행 구조

`6YSP_PAL`은 materialization 후 첫 EngineV2 receipt 이전에 종료됐다. 표본 peak RSS는 433,225,728바이트였다.
로그는 case 시작 한 줄이며 EngineV2 pose와 세 엔진 receipt가 모두 없다.
[runner의 순서][runner-order]는 profile → EngineV2 결과·receipt → Vina 결과·receipt → GNINA 결과·receipt이다.
따라서 두 외부 모드는 시작되지 않았고, 세 엔진이 모두 timeout됐다고 해석하면 안 된다.
EngineV2는 [전체 후보 진단][runner-candidates]까지 끝낸 뒤 최종 pose를 쓰므로 pose 부재가 검색 미완료를 증명하지 않는다.
준비·검색·정제·진단 중 어느 구간이 900초를 사용했는지는 현재 증거로 확정할 수 없다.
준비 실패 3개는 `6M73_FNR`, `6YJA_2BA`, `6YR2_T1C`의 `unsupported_large_ring_system`이다.
반환 가능한 준비 실패 후에는 외부 모드 실행이 이어졌다.
`6M73_FNR`, `6YR2_T1C`에서는 외부 두 모드 모두 `external_pose_count_incomplete`를 기록했다.
`6YR2_T1C`의 외부 SDF는 각각 4개 레코드이며 [정확히 5개를 요구하는 계약][runner-external]을 충족하지 못했다.
외부 stdout/stderr가 보존되지 않아 왜 4개만 생성됐는지 확정할 수 없다.

## 9. 증거 감사와 한계

smoke와 4개 development 원본에서 materialization 34개, 실행 receipt 99개 및 성공 pose 460개의 hash 연결을 확인했다.
같은 합성 사전 검사 7개가 5개 실행 노드에서 각각 통과했다. 서로 다른 35개 테스트로 계수하지 않는다.
그중 3 Å 평행 이동 대조는 receptor-frame RMSD 3 Å, Kabsch RMSD 0 Å를 구분했다.
이는 실행·평가 계약 대조이며 실제 도킹 정확도나 모든 numerical 함수의 검증은 아니다.
`development-18` inventory의 임시 입력 복사본 4개가 artifact에 없어서 `full_inventory_pass=false`이다.
대응 원본 입력은 보존되어 크기·SHA256·materialization receipt가 일치하지만 inventory 완전성을 통과로 바꾸지 않았다.
5개 노드는 선언한 evaluator 버전이 같아도 payload와 evaluation-pipeline hash가 서로 다르다.
각 receipt와 해당 노드 preflight의 연결은 확인했으며 노드 사이 evaluator byte 동일성은 주장하지 않는다.
설정 로그 image `20261025.340.1`과 환경 기록 `20261026.341.1`을 함께 보존하고 차이의 원인을 추정하지 않는다.
표본 descendant RSS는 공유 페이지를 중복 셀 수 있고 cgroup 격리가 아니며 peak 합계를 동시 메모리량으로 읽지 않는다.
aggregate 성공은 부분 결과 보존 성공이다. Stage 2의 `execution_complete`와 `scientific_accuracy_complete`는 모두 false다.

## 10. 후속 PR과 통과 조건

| 순서 | 작은 변경 범위 | 먼저 고정할 테스트와 증거 |
|---|---|---|
| P0-A | 개발 adapter에서 case×engine 실행 단위와 상한 분리 | stdlib child로 timeout·강제 종료·cleanup·다음 엔진 실행을 검증; 미실행/실패/성공 receipt를 구분 |
| P0-B | 단계 시작/완료 journal 및 원자적 checkpoint | profile·준비·검색/정제·64후보 진단·Top5·receipt 경계에 중단을 주입; 부분 증거를 완전 receipt로 승격하지 않음 |
| P0-C | 환경 및 artifact 정합성 | 동일 wheel bytes의 설치 증거, 노드별 payload hash, inventory/업로드 목록 비교; 누락·변조·다른 evaluator를 거절 |
| P1-A | diagnostic 내부 비용 계측과 결과 보존 경계 | 기존 좌표 fixture로 직렬화·RMSD·validity·프로세스 비용 분리; raw 판정과 candidate ID 보존을 검사 |
| P1-B | 생성·V6·V7 trial·선택·최종 좌표 계보 | stable ID와 좌표 hash, objective/score/단위, 선택·거절 이유 연결; 추가 E/F 없이 저장된 lineage를 감사 |
| P2 | 두 ranking-gap 사례의 점수/선택 계약 | 보존 후보에서 항별 합계·안정적 tie-break·재점수 좌표 연결을 검사; 새 계수 튜닝은 별도 가설과 예산으로 분리 |

P0에서 frozen runner, 정확히 5개 출력, validity, source binding을 완화하지 않는다.
P1은 먼저 진단 비용이 발생하는 구간과 후보의 이동을 관측하며 검사를 생략해 빨라졌다고 보고하지 않는다.
수식 또는 optimizer 변경은 그 뒤 목적함수·gradient·단위 계약에 대한 fixture와 대조 조건을 정한 별도 PR에서 검토한다.
후속 독립 검증은 개발 수정과 검증 조건이 정리된 뒤 별도 단계에서 진행한다.

## 11. 저장된 증거의 재집계

[분석 도구](../../tools/analyze_redocking_development_evidence.py)의 `--help`에서 다음 CLI를 확인했다.
아래 명령은 저장된 artifact를 읽어 별도 JSON만 쓰며 엔진 import·네트워크·분자 계산을 수행하지 않는다.

```bash
python tools/analyze_redocking_development_evidence.py \
  --artifact-root /path/to/downloaded-stage-artifacts \
  --manifest config/redocking_development_stages_20261103.json \
  --output /path/to/analysis-partial.json
```

artifact root에는 `smoke`, `development-2`, `development-10`, `development-18`, `development-26`를 둔다.
원본 `raw/`, `attempt-*.json`, `preflight.json`, inventory와 합쳐진 `combined/`를 함께 보존한다.
`--require-complete`는 미관측이 남아 있으면 JSON을 보존한 뒤 exit 2를 반환하며 이번 자료는 그 조건을 통과하지 못한다.
상세 근거는 분석 JSON의 `artifact_audits`, `integrity`, `evaluator_provenance`, `development.cases`, `method`에 있다.

[manifest]: https://github.com/betelgeuze-kang/ligand-docking/blob/b41636642a93d22dba8ff6f7e67df5250d17647d/config/redocking_development_stages_20261103.json
[runner-order]: https://github.com/betelgeuze-kang/ligand-docking/blob/4c6e4b9fba670e325be37b538e054af88f65dc01/tools/run_engine_v2_public_redocking_300.py#L5187-L5368
[runner-candidates]: https://github.com/betelgeuze-kang/ligand-docking/blob/4c6e4b9fba670e325be37b538e054af88f65dc01/tools/run_engine_v2_public_redocking_300.py#L2994-L3059
[runner-external]: https://github.com/betelgeuze-kang/ligand-docking/blob/4c6e4b9fba670e325be37b538e054af88f65dc01/tools/run_engine_v2_public_redocking_300.py#L3931-L4044
