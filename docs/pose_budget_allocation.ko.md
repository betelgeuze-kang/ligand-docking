# 포즈 간 관측 예산 배분: 독립 합성 실험

## 범위

이 도구는 이미 관측된 에너지·상태·비용만 보고 다음에 진행할 포즈를 고르는 stdlib 제어기다. 분자 좌표 생성, 최적화, 실제 E/F, native/GPU 실행, 네트워크, 설치 또는 파일 쓰기를 하지 않는다. 기존 adaptive trajectory frames, streaming slot refill이나 fixed mixed64의 `result_dependent_allocation=false` 계약을 수정·대체·우회하지 않는다. 별도 experimental lane이며 기존 엔진 adapter는 구현하지 않았다.

실행 환경·분자·점수 정의가 같다는 것은 호출자의 선언이다. 해시는 바이트를 결속할 뿐 생산자를 인증하지 않는다. 화학 상태가 다른 분자의 에너지를 비교하면 안 된다. 낮은 에너지, 수렴, 올바른 결합 자세는 서로 다르다.

## 제어기 계약

`tools/allocate_pose_budget.py`의 `BudgetController(pose_ids, policy)`는 고정 ID 순서, 총 integer 예산, 최소 탐색량, 관측 window, exploration 주기, 점수 방향을 받는다. `request()`는 하나의 포즈에 비용 1을 예약하고 token을 반환한다. 동시에 하나의 요청만 허용한다. `observe(token, status, energy, actual_cost)`로 동일 token을 한 번만 정산한다. 미래 trace, reference RMSD, 목표 label 또는 다른 포즈의 미실행 결과는 입력이 아니다.

- `ok`: 비용 1과 유한 에너지가 필요하다.
- `failed`: 비용 0 또는 1, 에너지 없음. 포즈는 terminal이다.
- `exhausted`: 비용 0, 에너지 없음. 더 제공할 prefix가 없다는 terminal 표기이며 수렴 증명이 아니다.
- `interrupted`: 알려진 비용 0/1 또는 null. null이면 예약 1을 보수적으로 차감하되 known observation units는 0, unknown-cost upper bound는 1로 기록한다. 포즈는 terminal이다.

중단된 평가를 무료로 재시도하거나 unknown 비용을 실제 실행 횟수로 확정하지 않는다. 총 charged upper bound는 알려진 관측 비용과 unknown 상한의 합이다. 예약·잔여 예산을 분리하며 실제 알려진 비용이 예약보다 크면 거절한다. 현재 계약의 1-unit 호출보다 큰 engine 작업은 그대로 연결할 수 없다. 실제 호출비용을 보증하는 adapter가 먼저 필요하다.

최소 탐색 비용을 모든 포즈에 할당할 수 없는 예산 설정은 거절한다. charged floor는 unknown 비용 상한을 포함한 보수적 차감 기준이며 실제 관측 최소량을 보증하지 않는다. `charged_floor_complete_for_all_expected_poses`, `known_cost_floor_complete_for_all_expected_poses`, `successful_observation_floor_complete_for_all_expected_poses`를 별도로 보고한다. known 비용에는 실패한 관측 시도도 포함되므로 성공 관측 floor와도 다르다. 실행 도중 포즈가 실패하면 그 포즈가 최소량을 충족하지 못했다는 사실을 그대로 남긴다. terminal 포즈도 expected denominator에서 삭제하지 않는다. 모든 포즈가 일찍 종료되면 미사용 예산을 남기고 끝낸다. terminal이 아닌 포즈는 새 시도마다 양의 비용이 필요하므로 무한한 무료 재시도는 없다.

## 세 정책

1. `round_robin`: 최소량을 먼저 보장한 뒤 ready 포즈 중 charged allocation이 가장 작은 것을 선택한다.
2. `low_energy`: 공통 최소량 이후 마지막으로 관측된 에너지가 가장 유리한 포즈를 선택한다. `minimize`와 `maximize`를 명시한다.
3. `improvement_with_exploration`: 최소량 이후 매 네 번째 결정(정책값)에는 가장 적게 배분된 포즈를 선택한다. 나머지는 최근 window에서 best-so-far 에너지 개선량/charged 비용이 큰 포즈를 선택한다. 첫 점을 가상의 초기 에너지와 비교하지 않는다. 개선값이 모두 0 또는 계산 불가능하면 탐색 선택으로 돌아간다.

동률은 고정 pose ID 입력 순서로 해결한다. 최근 개선률은 부동소수점 관측값으로 계산하며 거의 같은 기울기를 동일하다고 강제로 취급하는 숨은 tolerance가 없다. 따라서 미세한 차이가 exploitation 우선순위에 영향을 줄 수 있다. 이는 실제 성능 장점이 아니며 합성 uniform 사례에서도 균등 배분보다 나쁜 결과가 나왔다. 결과를 보고 tolerance나 window를 변경하지 않았다.

## CLI와 입력

```sh
python -I -S tools/allocate_pose_budget.py observed_receipts.json
python -I -S tools/compare_pose_budget_policies.py tests/fixtures/pose_budget_synthetic.json
python -m unittest discover -s tests/unit -p test_pose_budget_allocation.py -v
python -O -S -m unittest discover -s tests/unit -p test_pose_budget_allocation.py -v
```

관측 CLI의 입력 schema는 `pose_budget_observations/1`이다. 정확히 `schema`, `context`, `pose_ids`, `policy`, `observations`를 포함한다. context는 model/chemical_state/energy_unit 문자열이다. policy는 strategy/total_budget/minimum_floor/window/exploration_interval/score_direction이다. 각 observation은 token/pose_id/status/energy/actual_cost를 포함한다. 제어기가 요청할 순서와 다른 pose/token은 거절한다. 모든 제공된 receipt를 재생한 뒤 가능한 다음 요청 1개를 예약해 보고한다. 원본 context 문자열은 출력에 반복하지 않고 digest만 표시한다.

stdout JSON과 종료코드 0은 보고서가 생성됐다는 의미이지 과학적 성공이 아니다. 잘못된 입력은 경로·원문 exception을 노출하지 않는 stderr와 코드 2다. JSON 중복 key·비유한 값·과도한 깊이·정의되지 않은 필드는 거절한다. API는 이미 파싱된 객체용이며 byte limits는 CLI/`load_bytes()`에 적용된다.

입력 2MiB, JSON 깊이 24, 포즈 128, 예산 100,000, window 2~32, floor 1~32, 출력 16MiB를 제한한다. 에너지 절댓값은 1e100 이하다. 정책 한도는 OS RSS/process-tree 보안 격리가 아니다.

## 동결 합성 비교

fixture SHA256 `074b43c3fb028bfd186a559841ad99836a012dc8efab3ebcf03692fc900cba82`를 결과 관측 전에 고정했다. runner는 정확한 fixture 바이트 해시를 요구한다. 8개 scenario, 3정책, 포즈 4개, 예산 ceiling 64, floor 2, window 4, exploration 주기 4다. 미래 prefix와 평가용 marker는 runner에만 있으며 controller에 전달하지 않는다. target marker를 바꿔도 선택 이력이 같다는 시험을 포함한다.

curve의 여섯 값은 start/slope/delay/plateau/length/failure_step이다. step번째 합성 에너지는 `start - slope * max(0, min(step, plateau)-delay)`이다. trace 길이를 넘으면 exhausted, 지정 failure step은 비용 1의 failed다. interruption fixture는 실제 관측 비용이 알려지지 않은 중단을 모델링한다. 성공적으로 공개된 step만 marker 관측으로 센다. 관측되지 않은 표식은 주어진 관측 prefix 안에서 보이지 않았다는 뜻일 뿐, 중단·누락·미실행 구간에서 실제로 실패했거나 도달할 수 없다는 증거가 아니다. `unobserved_marker_is_failure=false`를 명시한다.

이 비교는 **합성 관측 prefix 재생과 모델링한 E/F 비용**이다. 실제 엔진 E/F 호출도, 별도 에너지+힘 함수 평가 횟수도 아니다. 모든 포즈의 prefix가 다른 포즈를 언제 실행하든 동일하다는 분리 가능성을 가정한다. batch coupling, 적응적 restart 또는 shared optimizer state로 미래가 바뀌는 상황에는 이 재생 결과를 적용할 수 없다. 미기록 suffix를 외삽하지 않는다.

고정 사례: uniform, early productive, delayed payoff, low-energy decoy, early plateau, flat ties, failure/exhaustion/interruption, all exhausted. 도움·악화·동일·미사용 예산이 모두 남아 있으며 seed나 사례 제외, 사후 정책 튜닝은 하지 않았다.

합성 marker 도달 사례 수는 균등 5/8, 낮은 에너지 우선 2/8, 개선률+탐색 5/8이다. 개선률 정책은 균등보다 2사례에서 도움, 2사례에서 악화했다. **전체 우월성을 보이지 않았다.** 각 정책의 8사례 합계 charged 상한은 456, known observation units는 455, interruption unknown 상한은 1이다. all-exhausted 사례는 8/64만 사용하며 나머지 7사례는 charged ceiling 64에 도달한다. unknown 비용이 있는 사례는 실제 동등 계산량을 증명하지 않는다. 이 hand-constructed marker 비율은 분자 도킹 성공률이 아니다.

실제 적용에는 고정한 같은 분자·시작점·엔진을 각 정책으로 실행하고 실제 호출비용·실패·정답 회복을 별도로 측정해야 한다. 현재 scientific_validation은 false이며 엔진·GPU·제품·상업 자격을 승격하지 않는다.
