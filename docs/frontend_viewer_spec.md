# 내부용 분자동역학 시각화 및 피규어 생성 웹앱 구현 명세서

## 1. 개요 (Overview)
- **목적:** 내부 연구진이 파이프라인에서 생성된 동역학 궤적(Trajectory) 파일과 리간드 결합 상태를 브라우저 상에서 인터랙티브하게 확인하고, 출판/보고서용(AlphaFold 수준)의 고해상도 단백질 이미지를 즉시 추출할 수 있는 독립형 프론트엔드 뷰어 구축.
- **포지셔닝:** 기존 Python/HTML 생성 코드(`visualize_experiment_dashboard.py`)와 ChimeraX 오프라인 렌더링 스크립트를 대체하거나 보완하는 현대적 Single Page Application(SPA).

---

## 2. 핵심 구현 스펙 및 요구사항

### 2.1. 고성능 3D 뷰어 모듈
- **엔진:** **Mol*** (Molstar) WebGL 기반 뷰어 도입
- **지원 포맷:** PDB, mmCIF 파일 및 리간드용 SDF/MOL2 형식 렌더링.
- **다중 구조 비교:** 베이스라인 구조와 Candidate(리간드 결합 형태)를 겹쳐서 비교하는 Superposition(구조 정렬) 기능.

### 2.2. 리간드-단백질 결합 포즈 (Binding Pose) 특화 시각화
- **상호작용 자동 표시:** 단백질 포켓과 리간드 간의 수소 결합(Hydrogen bond), 소수성 상호작용(Hydrophobic interaction), Pi-Pi 결합 등을 계산하여 3D 점선(Dashed line) 및 거리 텍스트로 오버레이.
- **표면(Surface) 투명도 렌더링:** 결합 포켓 주변 단백질의 표면을 생성하고, 표면 색상을 정전기 분포 혹은 친수/소수성에 맞춰 렌더링.
- **스코어 오버레이:** 결합 에너지, 최소 거리(A), Stage3 Top-K 순위 정보를 3D 공간 상에 라벨링.

### 2.3. MD 트래젝토리 (동역학 궤적) 플레이어
- **타임라인 조작:** 재생(Play), 일시정지, 프레임 슬라이더(Scrubbing), 재생 속도 조절.
- **동적 색상 스킴:** 프레임 변동 구간에 맞춰 RMSF (잔기별 굽힘성/이동성) 값을 B-factor 영역에 매핑하여 열지도(Heatmap) 형태로 시각화.
- **메트릭 동기화 연동:** 하단에 Plotly 기반의 2D 그래프(시간에 따른 RMSD, Energy, Radius of Gyration 등)를 띄우고 영상 프레임 재생 시점을 2D 그래프에 수직선으로 동기화 매핑.

#### 2.3.1. NPZ 계약 vNext
- **필수 키:** `protein_ca[P,3]`, `ligand_frames[T,L,3]`, `frame_indices[T]`
- **선택 키:** `protein_residue_rmsf[P]`, `protein_residue_bfactor_equivalent[P]`, `protein_residue_centroids[T,P,3]`, `protein_residue_schema_version[1]`
- **full protein motion 확장 키:** `protein_atom_frames[T,A,3]`, `protein_atom_template_index[A]`, `protein_atom_schema_version[1]`
- **정렬 기준:** residue-level 배열은 반드시 `protein_ca` 순서와 1:1로 정렬되어야 함.
- **atom-level 정렬 기준:** `protein_atom_frames[:, i, :]`는 viewer가 로드한 `proteinTemplateAtoms[i]`와 동일한 atom order를 따라야 함. order를 직접 보장할 수 없으면 `protein_atom_template_index[A]`를 함께 전달.
- **문자열 residue label:** NPZ에 직접 넣지 말고 bundle JSON sidecar로 전달.
- **뷰어 사용 방식:** `protein_residue_bfactor_equivalent`가 있으면 B-factor color theme에 우선 사용하고, 없으면 `protein_residue_rmsf`를 fallback으로 사용.
- **full protein frame mutation eligibility:** `protein_atom_frames`의 `T`는 `ligand_frames.shape[0]`와 같아야 하고, `A`는 viewer의 `proteinTemplateAtoms.length`와 같아야 함. 이 조건이 맞지 않으면 viewer는 ligand fast-path만 사용하고 protein은 static template 또는 selective reload로 fallback.
- **fallback 정책:** `protein_residue_*` 키만 있으면 frame-aware residue heatmap/색상만 지원하고, `protein_atom_frames`까지 있을 때만 protein Cartesian motion in-place update를 시도.
- **버전 정책:** `protein_atom_schema_version`과 `protein_residue_schema_version`은 cache busting과 parser gate의 기준으로 같이 유지.

### 2.4. 논문/보고서용 초정밀 피규어 엔진 (High-Res Snapshot)
- **렌더링 옵션 (AlphaFold 수준 표현):**
  - Ambient Occlusion (그림자 깊이감 추가)
  - Soft Shadows (부드러운 조명)
  - Silhouette / Outlines (외곽선 셀셰이딩, AlphaFold 기본 시각화 스타일 재현)
- **출력 (Export) 기능:** 해상도 배율 설정(2x, 4x, 8x), 투명 배경 처리된 고품질 초정밀 PNG/JPEG 원클릭 내보내기. 
- (※ 현재 `render_chimerax_movies.py`에 의존하는 스냅샷 작업을 브라우저단에서 바로 수행하여 즉각적 대응 가능화)

### 2.5. 전기장/전하 표면 데이터 계약
- **입력 포맷:** `DX`, `CUBE/CUB`
- **bundle 필드:** `surface_map_path`, `surface_map_format`, `surface_map_kind`, `surface_map_isovalue`
- **기본 렌더 정책:** `+isovalue`는 blue, `-isovalue`는 red 반투명 isosurface로 표시
- **역할 분리:** APBS/DelPhi 계산은 upstream에서 수행하고, viewer는 volumetric map import와 surface coloring만 담당

---

## 3. 화면 구성 제안 (UI Layout)

1. **좌측 패널 (제어 계기판):**
   - 로컬 파일 트리 및 업로드 인터페이스 (`PDB/SDF` 로드)
   - 표현 설정 (Cartoon, Surface, Ball-and-Stick 등)
   - 컬러 스킴 선택 (pLDDT, B-factor, 이차 구조 등)
2. **중앙 뷰어 (View Port):**
   - 넓은 공간을 차지하는 3D 뷰어 화면.
3. **하단 패널 (타임라인 & 플롯):**
   - 트래젝토리 제어 재생 바(Slider).
   - 선택적 2D 메트릭 플롯 영역 (RMSD 그래프 등).
4. **우측 상단 패널 (분석 & 스냅샷):**
   - 상호작용 분석 결과 리스트 (결합 거리 기록표).
   - "고해상도 피규어 렌더링" 제어 위젯 (해상도 선택, 투명도 토글, 캡처 버튼).

---

## 4. 권장 기술 스택 (Tech Stack)
- **프론트엔드 프레임워크:** `React.js` (또는 유지보수 자유도가 높은 `Vanilla JS + Webpack/Vite`)
- **3D 렌더러 분자 엔진:** `Molstar (mol*)` 라이브러리 (성능면에서 3Dmol.js 대비 매우 우수하며, 하이엔드 그림자/스냅샷 처리에 유리)
- **차트 라이브러리:** `Plotly.js` (현행 Python 대시보드 플롯 코드를 그대로 브라우저로 이식하기 쉬움)
- **스타일링:** `TailwindCSS` 등 유틸리티 기반 프레임워크 (빠른 UI 구축 목적)
