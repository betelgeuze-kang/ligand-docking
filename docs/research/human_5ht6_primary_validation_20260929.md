# 5-HT6 실험 원문 대조와 서비스 검증 자료 점검

현재 고정 모델은 이 사후 진단의 실제 Ki 30개를 모두 활성으로 예측했다. 기존 기준인 Ki <= 1,000 nM보다 약한 **6개를 모두 놓쳤다**. 새 학습이나 기준 변경은 하지 않았다. 이 결과는 독립 평가가 아니지만, 현재 모델을 고객의 활성/비활성 판단에 사용하기 어렵다는 구체적인 실패 사례다. GPU 가속으로 해결되는 문제도 아니다.

## 이번에 확보하고 대조한 자료

기존 5개 논문의 30개 실험 행은 그대로 유지했다. 이번에는 [Biomolecules 논문](https://doi.org/10.3390/biom13010012)의 [공식 보충자료 ZIP](https://mdpi-res.com/d_attachment/biomolecules/biomolecules-13-00012/article_deploy/biomolecules-13-00012-s001.zip)을 확보하고, 그 안의 62쪽 PDF와 기존 논문의 대응 관계를 검증했다. 새 측정 행을 30개에 추가한 작업은 아니다.

| 확보 파일 | 바이트 | SHA-256 |
| --- | ---: | --- |
| 공식 보충자료 ZIP | 3,273,743 | `57fdb4cfc9f52391fa3770daf4799d68db98f3dbb5a0e59f223a8e62bcb55f74` |
| 추출한 supplementary PDF | 3,586,798 | `5b34bf7db08a28bf27cf4f151d116b05ccbdb6cf43b0253ec4fb9bc38a6ce19e` |
| SB-258585 PubChem 식별 응답 | 262 | `376c75688a3087730348870ad6fd63f8f4c73b5c15a5e955db81cb7a2c0e3a5f` |

원문 4-6쪽의 3a-l 이름·분자식·순도, 9쪽 Table 1의 Ki와 SEM, 보충자료 58쪽의 결합시험 방법을 PDF 화면으로 대조했다. 대상은 human 5-HT6를 발현하는 HEK293 막의 방사성 리간드 경쟁 결합시험이다. Table 1은 세 독립 실험의 평균과 SEM이고, 각 농도는 triplicate로 측정했다고 보고한다. 이것은 저자들이 발표한 실험 요약값이며, 원시 반복 측정값이나 새로 수행한 실험은 아니다.

결합시험의 pH는 확인한 방법에 기재되어 있지 않다. 원문 다른 절의 pH 7.4는 microsomal stability 조건이므로 여기에 옮기지 않았다. cAMP 기능시험의 Kb와 다른 표적의 Ki도 같은 endpoint로 합치지 않았다. Table 2에서 3e와 3g의 SEM이 Table 1과 다른 문제는 그대로 기록했다. 원시 결합곡선·반복값은 확보하지 못해 오차나 curve fitting을 독립 재산출하지 못한다. 중성 SMILES는 문헌에 대응시킨 계산 입력이며, 실제 시험 중 미세상태나 7XTB 수용체 상태의 동등성은 확인되지 않았다.

## 기준물질을 포함했을 때 달라진 독립성 판정

Table 1의 SB-258585 8.9 nM는 이 논문의 새 측정이 아니라 reference 20, Hirst et al. 2000의 인용값이다. [PubChem CID 3248571](https://pubchem.ncbi.nlm.nih.gov/compound/3248571)의 구조 식별 응답과 연결해 **문헌 내 비교행의 메타데이터 검사에 포함하고, 새 실험/모델 진단 분모에서는 제외**했다.

기존 30개 후보에 이 한 행을 더하면, 동일한 168,175-node 문맥과 동일한 정책에서 31개 중 22개가 `blocked_identity`, 9개가 `identity_clear_review_required`가 된다. 차단 22개는 실험 행 21개와 인용 기준물질 1개다. Biomolecules 12개 모두 예약 자료가 1,336개 있는 135,187-node component에 연결된다. 3a에서 예약 자료까지의 최단 경로는 `document -> canonical -> document -> scaffold` 네 단계다. 경로 해시는 `8284d91790f5d10ac484f61b2808d7522a14366a83cc8f5535cc38ed35ea2088`이다.

이것은 현행 정책의 문헌·화학 메타데이터 연결이며, 신규 12개의 직접 중복이나 화학적 동등성을 뜻하지 않는다. 공통 기준물질 때문에 크게 연결되는 정책 자체의 과잉 연결 가능성도 남는다. 이번 결과에 맞추어 기준물질을 빼거나 정책을 완화하지 않았다. 정책 변경이 필요하면 별도 과학적 근거로 관계 유형을 검토하고, 아직 결과를 보지 않은 자료에 적용하기 전에 고정해야 한다.

Table 1 비교행의 누락은 보완했지만 논문 전체의 모든 endpoint·기준물질·문헌 계보까지 완료한 것은 아니다. 남은 9개도 독립성 승인을 받은 것이 아니다. **새 fit/calibration/independent-evaluation admission은 모두 0**이다. 기존 ledger와 좁은 입력의 과거 receipt는 보존했다.

## 고정 모델과 원문 실험값의 실제 대조

원문 값은 이미 읽은 상태였다. [진단 계획](../evidence/human_5ht6_primary_retrospective_plan_v1.json)을 추론 전에 기록했지만, 이를 blind 평가로 부르지 않는다. 기존 체크포인트 `818f2b32...`와 원래 학습 평균만 사용하고, 논문별 결과를 분리했다. 데이터 범위는 이미 캡처된 30개 전부이며 결과를 보고 추가 제외하거나 문턱값을 바꾸지 않았다. SB-258585 인용행은 새 측정이 아니므로 처음부터 예측 비교 대상에 넣지 않았다.

| 실험 출처 | 행 수 | 기준 이하/초과 Ki 행 | 모델 pKi MAE | 고정 학습 평균 pKi MAE |
| --- | ---: | ---: | ---: | ---: |
| Molecules 2017, 22, 2221 | 6 | 2 / 4 | 2.082 | 1.655 |
| Molecules 2023, 28, 1108 | 4 | 4 / 0 | 0.344 | 0.303 |
| Molecules 2023, 28, 1096 | 5 | 5 / 0 | 0.742 | 0.617 |
| IJMS 2024, 25, 10287 | 3 | 2 / 1 | 1.516 | 1.007 |
| Biomolecules 2023, 13, 12 | 12 | 11 / 1 | 0.972 | 0.989 |

여기서 기준은 기존 pKi >= 6, 즉 Ki <= 1,000 nM이다. 비활성은 이 계산상의 분류 경계보다 약한 결합을 뜻하며, 생물학적 효과가 전혀 없다는 뜻이 아니다. SD/SEM은 원래 종류와 단위로 유지하고 신뢰구간으로 바꾸지 않았다.

30/30개 예측이 실행됐고, 관측 분류는 활성 24개·약한 결합 6개였다. 모델은 30개 모두 활성으로 예측했다. 예를 들어 PR59의 실험 Ki는 1,964 nM (pKi 5.707)이지만 예측 pKi는 8.163이다. 단순 평균보다 논문별 MAE가 나은 경우는 5개 중 1개였고, 그 Biomolecules에서도 RMSE는 모델 1.235, 평균 1.112로 악화했다. 작은 표본과 관련 출처로 얻은 진단이므로 일반화 성능 추정이나 유의성 주장은 하지 않는다.

실제 제품 `PublicAssaySelectorShadow`로 계산했다. 처음 시스템 Python 실행은 RDKit 버전이 달라 예측 전에 거부됐다. 거부 조건을 유지하고, 체크포인트의 RDKit 2026.03.6이 설치된 기존 외부 환경에서 실행했다. `math.fsum`을 사용한 별도의 scalar dot 계산과 제품 예측의 최대 차이는 `1.7763568394002505e-15`였다. 이는 같은 분자 특징에 대한 산술 대응이며 분자 상태나 예측 정확도의 검증을 대신하지 않는다.

[전체 실행 receipt](../evidence/human_5ht6_primary_retrospective_diagnostic_v1.json)는 행별 원문 값·오차 단위·예측·실패 분모·참조 제외·문맥 및 소스 해시를 보존한다. 체크포인트·학습 계수·원래 역할·소비자 코드·점수·고객 실행 설정은 변경하지 않았다. Fresh-128이나 기존 보호 평가의 원시 결과를 새로 열지 않았다.

## 기존 확장 평가와의 관계

별도로 이미 실행된 724행 개발 평가와 구조 유사도 비교도 확인했다. 680행 예측, 44행 기권이었고, 공통 방법/정확값 범위 515행의 pKi MAE는 Ridge 0.925299, 평균 0.926192였다. 중복 상태를 묶은 687개에서 같은 상위 138개 예산으로 확인된 활성은 Ridge와 최대 구조 유사도가 모두 116개였다. 이 자료는 이번에 새로 수행한 독립 검증이나 신규 학습 데이터가 아니다.

기존 보고서: `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-ht6-similarity-baseline-m8s61b52/report.ko.md`. 원래 학습 exact 76행이 모두 활성이라는 점과 함께 보면, 다음 우선순위는 데이터의 단순 증량보다 **같은 시험 안에서 강한 결합과 약한 결합을 모두 포함하는 출처별 검증**이다. 이전 724행을 fit으로 재사용해서 이 문제를 해결하지 않는다.

## 서비스 판단을 위해 남은 실제 자료

1. 고객에게 지원할 endpoint·화학 상태·수용체 상태·계산 목적을 먼저 고정한다. 현재 Ki 예측, 준비 입력 reader, cross interaction 점수의 성공은 서로 다른 증거다.
2. 같은 시험에서 강한 결합/약한 결합을 함께 측정한 전체 후보 집합을 확보한다. 원시 반복값·농도반응곡선·시험조건·기준물질·실패 기록이 필요하다. 독립 새 측정을 수행하거나 의뢰한 사실은 아직 없다.
3. 새 실험값을 열기 전에 화학/문헌 역할, 기준선, 모델, 후보 예산, 실패 처리와 허용 기준을 동결한다. 공통 기준물질의 그래프 의미도 그전에 해결한다.
4. 같은 후보에 구조 유사도·엔진·엔진+AI를 실행하고, 출처별 정확도와 전체 요청 성공률·준비/계산/재개/내보내기 총비용을 함께 비교한다. 현재 이 30행에 대한 실제 도킹/포즈 회복/전체 서비스 작업 검증은 0건이다.

`NOT_PROMOTED / NOT_QUALIFIED`를 유지한다. 현재 가치는 실패 사례를 재현하고 필요한 실험 데이터의 조건을 구체화한 데 있다.

## 재현

원본과 렌더링 자료는 외부 볼륨의 `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-service-validation-20260929/`에 보관한다. 다운로드 URL/바이트/추출 관계는 그 안의 `source-acquisition.json`에 있다. PDF/ZIP을 Git에 중복 저장하지 않는다.

```bash
DIAGNOSTIC_PYTHON=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-openff-runtime-y2epeamt/env/bin/python
SOURCES=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-service-validation-20260929
RUNS=/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs
"$DIAGNOSTIC_PYTHON" -B -m tools.analysis.human_5ht6_primary_diagnostic_v1 \
  --ledger "$PWD/docs/evidence/human_5ht6_ki_multi_paper_source_ledger_v1.json" \
  --pdf-directory /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-primary-20260929 \
  --source-directory "$SOURCES" \
  --context "$RUNS/engine-v2-second-fit-source-jxkx9zsg/prospective-role-context.jsonl.gz" \
  --checkpoint "$RUNS/engine-v2-post-pde2-fresh-assay-fdx9ckq6/ht6-intake/identity-complete-attempt2/fit-model/selector.json" \
  --plan "$SOURCES/diagnostic-plan-before-inference.json" \
  --output "$SOURCES/primary-diagnostic-reproduction.json"
```

출력 파일은 기존 파일을 덮어쓰지 않는다. 재현 receipt는 Git의 receipt와 바이트 단위로 비교할 수 있다. 원본 ledger, 다섯 PDF, 보충 ZIP/PDF, PubChem 화학 식별 응답, 메타데이터 문맥, 진단 계획과 체크포인트를 각각 해시로 고정한다.

검증 결과: 기존 5-paper source 검사와 새 진단/인용행 회귀를 함께 실행해 **26 passed**였다. 실제 PDF 다섯 개와 고정 메타데이터 문맥을 제공한 검사도 포함한다. 적합한 RDKit 환경에서 실제 30행 진단을 두 번 실행한 receipt는 바이트 단위로 일치했고, SHA-256은 `3660d93bff291e654c2863e028f27fe4164269aa1de7b1bad771aa4f35db987a`였다. 이 소프트웨어 검사와 재현을 독립 실험 검증 횟수로 세지 않는다.
