# 정체 후 재탐색 제어의 독립 합성 실험

## 범위: 분자 이동기가 아닌 제어 계약

이 변경은 관측된 에너지와 평가 비용으로 다음 `initialize/refine/restart/escape` 요청을 선택하는 표준 라이브러리 전용 제어기다. 좌표·결합·회전·torsion을 생성하거나 변경하지 않는다. 실제 도킹 엔진, Torch/RDKit, GPU, 네이티브 모듈을 import하거나 실행하지 않는다. **분자 구조 보존이나 실제 도킹 개선은 이번 실험에서 검증되지 않았다.**

기존 `betelgeuze_engine_v2/docking/guided_placement.py`의 `SourcePairedTorsionRescuePolicy`와 관련 allocation/proposal 기능을 대체하지 않는다. 기존 lane은 고정 후보의 source-paired 할당이며, 해당 [개발 A/B 문서](engine_v2_source_paired_torsion_rescue_development_ab.md)는 미승격 결론을 기록한다. `torsion_contact_refinement.py`의 실제 변환·refinement도 이번에 연결하거나 실행하지 않았다. 원자 대응과 허용 rotor·구조 보존을 검증한 기존 기능을 향후 adapter에서 사용할 수 있지만, 이 PR은 그 통합이나 실행 권한을 부여하지 않는다.

새 범위는 초기 후보 생성 이후의 **정체 관측 → 다음 행동 요청 → 비용 회계**다. 에너지가 낮다고 실제 결합 자세가 맞다는 뜻은 아니며, 잘못된 목적함수에서는 더 나쁜 과학적 결과를 더 잘 최적화할 수도 있다.

## API와 비용

`tools/stagnation_search_controller.py`의 `Controller`는 정책, 평가 예산, patience, 개선 최소량, 재시작 간격, 최대 행동 수를 받는다. 에너지는 낮을수록 좋은 동일 목적함수의 유한 스칼라다. 정책은 다음 세 가지다.

- continuation: 초기화 후 계속 refine.
- uniform_restart: 정해진 cycle 관측 수마다 restart.
- stagnation_escape: cycle 최저 에너지를 개선하지 못한 관측이 patience에 도달하면 escape.

`issue()`는 행동 ID, kind, 평가 허용량 1을 반환한다. 동시에 하나의 행동만 진행한다. 반환 dict 변경은 내부 pending 상태를 변경하지 않는다. pending 행동에는 1회분이 예약되며 완료 전 추가 발급을 거절한다.

`observe()`는 일치하는 ID와 status, 실제 평가 수, 선택적으로 에너지·수락 여부를 받는다. 잘못된 ID/형식/비유한 에너지/허용량 초과는 내부 상태를 변경하기 전에 `ContractError`로 거절한다. 이것은 호출자 계약 거절이지 분자 계산 실패가 아니다.

- ok: 평가 1회와 유한 에너지가 필수. accepted=false여도 평가 비용과 관측 기록을 보존한다.
- failed/unavailable: 평가 수는 0 또는 1, 에너지·수락은 금지. 평가 없는 제안 실패도 행동 슬롯을 소비해 무한 루프를 막는다.
- interrupted: 실제 비용을 모르므로 evaluations=None을 요구하고 예약량 1을 전부 보수적으로 차감한다. known_evaluations와 unknown_evaluation_allowance를 분리한다. 알 수 없는 비용을 실제 실행 1회로 위조하지 않는다.

같은 관측의 재전달은 거절한다. 이 버전은 재시작 가능한 직렬화·분산 작업 스케줄러가 아니며 외부 프로세스의 평가량을 강제로 제한하지 않는다. adapter는 평가 전에 allowance를 확인하고 실제 비용을 보고해야 한다. 한 번의 행동이 여러 E/F를 수행하는 실제 L-BFGS에 직접 연결할 수 없다. 먼저 한 호출 단위 adapter 또는 별도 다중호출 예약 계약이 필요하다. toy refine은 한 gradient step일 뿐이다. 실제 escape/restart 후에는 좌표와 에너지·gradient를 함께 갱신하고 이전 L-BFGS history/line-search 상태를 무효화하는 optimizer-state reset 계약도 별도로 검증해야 한다.

수락한 초기화·재시작·탈출은 cycle 기준을 새 에너지로 재설정하고 정체 카운터를 초기화한다. archive용 best_observed_energy는 모든 성공 평가의 최저값을 보존한다. rejected는 현재 상태를 바꾸지 않는다. 이는 화학적 타당성을 판단한 결과가 아니므로, adapter가 타당하지 않은 좌표의 에너지를 ok로 제출하면 안 된다.

## 고정 합성 실험

`tools/experiment_stagnation_search.py`는 controller와 별개인 1차원 analytic toy adapter다. 분자 primitive를 흉내 냈다는 주장을 하지 않는다. 아래 세 목적함수는 알려진 전역 하한 0을 갖는다.

- convex: (x−0.75)²
- planted_double_well: (x+1)²[(x−1)²+0.15]
- periodic_wells: 1−cos(3x)+0.05x²

고정 fixture는 3함수 × 20개 paired seed × 3정책이며, 각 실행에 **120회의 joint analytic energy/gradient 호출**을 배정한다. 이는 실제 엔진의 energy-only/force-only 시간이나 비용과 동등하지 않다. 초기 평가, 거절된 refine, restart, escape를 모두 센다. 성공을 빨리 달성해도 조기 종료하지 않는다.

정책은 patience=8, 개선 최소량=1e-5, 균등 재시작 간격=20, 최대 행동=240으로 사전 고정한다. adapter 영역은 [-3,3], gradient step=0.025, 1회 이동 최대0.25, escape 이동은 [-2,2] 균등이다. refine은 uphill을 거절하지만 평가 비용은 차감한다. escape/restart는 새 상태를 수락하며 기존 최저점은 별도 archive에 보존한다. 이 수락 규칙은 물리적 시간 적분이나 볼츠만 표본추출이 아니다.

난수는 seed·행동 종류·해당 행동의 발생 인덱스를 SHA256으로 결합한 counter-keyed stream이다. 같은 seed의 초기 좌표는 세 정책에서 같고, 같은 종류의 k번째 재시작도 정책 실행 순서와 독립이다. 정책이 다른 행동을 선택하면 이후 경로가 달라지는 것은 의도한 실험 차이다. 기계적 좌표-bin 수는 실제 basin 식별자가 아니다.

정답 좌표, 성공 threshold, basin 라벨, 미래 관측은 controller에 전달하지 않는다. 성공은 실행 후 best objective≤1e-4로 계산한다. 알고리즘은 그 threshold를 사용해 행동을 정하거나 중단하지 않는다. fixture를 결과를 보고 바꾸면 새 실험이며 기존 결과를 대체하면 안 된다.

## 실행과 시험

checkout에서 다음과 같이 실행한다. 생성된 stdout 결과를 저장한다면 저장소 외부 개인 작업공간에 둔다.

```sh
python -S tools/experiment_stagnation_search.py tests/fixtures/stagnation_search_protocol.json --expected-sha256 a5d5e7b8bfa65c9a177665dae357f6e85d50f4cb3642fa6cea3463b6f9287b25
python -m unittest discover -s tests/unit -p test_stagnation_search_controller.py -v
python -O -S -m unittest discover -s tests/unit -p test_stagnation_search_controller.py -v
```

성공 시 stdout JSON, 종료코드0이며, 실험 실행 성공을 뜻할 뿐 새 정책 우월성을 뜻하지 않는다. 잘못된 입력·해시·접근 오류는 원본 경로 없는 일반 stderr와 코드2다. 프로토콜64KiB, seed200개, 총 joint 호출600,000회, 출력16MiB로 제한한다. controller 자체는 budget100,000회, action200,000개까지이며 단일 프로세스/OS sandbox가 아니다. Python API는 호출자 계약용이며 비신뢰 JSON은 CLI/load_protocol을 사용한다.

## 사전 고정 첫 결과와 해석

동일 fixture 첫 실행의 성공수(20개 seed 분모)는 continuation / uniform_restart / stagnation_escape 순서로 다음과 같다.

| 목적함수 | continuation | uniform_restart | stagnation_escape |
|---|---:|---:|---:|
| convex | 20/20 | 1/20 | 20/20 |
| planted_double_well | 12/20 | 16/20 | 15/20 |
| periodic_wells | 7/20 | 12/20 | 12/20 |

총 180회 실행은 모두 정확히120 joint 호출을 사용했으며 합계21,600회다. 실패·미완료0. 원시 실행 결과는 이 PR에 포함하지 않는다. 이는 작고 선택된 analytic 사례의 기술통계이지 일반화된 벤치마크나 통계적 우월성 증명이 아니다. 정체 탈출은 이 다중최솟값 예에서 continuation 대비 성공수를 늘렸지만, double-well에서 균등 재시작을 이기지 못했고 periodic에서는 동률이었다. 무조건 재시작은 convex에서 불리했다. 결과를 좋게 만들기 위한 seed·함수·파라미터 변경은 하지 않았다.

전체 결론은 **한 정책이 항상 낫지 않다**이다. 실제 분자 적용 전에는 검증된 좌표 변환 adapter, 같은 모델의 E/F, 고정 분자군과 평가예산, 물리 타당성 및 별도 reference 기반 평가가 필요하다. 실제 분자 E/F 실행, GPU parity, 엔진 admission, 도킹 정확도·상업성 검증은 모두 미수행이다.
