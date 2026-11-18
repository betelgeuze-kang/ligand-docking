# 9SZ4 독립 입력 준비와 BCC 차단

기존 고정 개발 명단 32개에서 공개 UniProt 식별자를 대조했다. 9SZ4의 인간 METTL3 Q86U44와 METTL14 Q9HCE5에 일치하는 표기는 0/32였다. 저장 수용체 29개, 사슬 48개는 별도로 해시와 관측 서열을 비교했다. 대체 후보 9OC9·9OCA의 인간 DHODH Q02127은 개발 명단의 6M2B에 이미 포함됐다. [9SZ4](https://www.rcsb.org/structure/9SZ4) · [6M2B](https://www.rcsb.org/structure/6M2B)

사전에 정한 중원자 고리·연결 골격 비교에서 A1JSA는 명단의 32/32와 달랐다. 저장 seed 29개와 미준비 행의 공개 CCD 3개를 사용했다. 비교는 결합차수와 입체화학을 무시했고, 기존 명단 밖의 사용 이력은 UNKNOWN이다. 9SZ4에 이미 생성된 C11–C12 +30° 후보 8개와 원래 정책은 보존했다.

9SZ4 BCC의 67/68 지원 결과에서, Amber의 C24–N6이 CCD의 C30–N31임을 원자 대응으로 확인했다. 원소와 연결이 같지만 원본 CCD는 이 이중결합을 방향족으로 표시하고 전하용 전송 그래프는 방향족으로 표시하지 않는다. 설치표와 AmberClassic 공개표의 SHA256은 동일했고 16–24/결합형 2는 두 파일 모두에 없었다. [AmberClassic BCC 표](https://github.com/Amber-MD/AmberClassic/blob/main/dat/antechamber/BCCPARM.DAT)

21개 V2000 결합 필드만 차이가 나는 대조 파일을 로컬에서 생성했다. 공개 AmberClassic MDL reader는 숫자 4를 명시적 방향족으로 처리하지 않아 그 직접 입력은 HOLD다. 실제 설치 Amber20 판독과 인과관계는 미확인이다. 영향 범위 시험 6개는 일반 모드와 `-O`에서 각각 통과했으며 새 QM·E/F·독립 도킹은 미실행이다. [AmberClassic MDL reader](https://github.com/Amber-MD/AmberClassic/blob/main/src/antechamber/mdl.c)

production HOLD·THRB HOLD·기존 17 UNKNOWN·실제32/공식 verify/고정100 미실행을 유지한다.
