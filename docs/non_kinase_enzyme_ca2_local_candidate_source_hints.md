# CA2 Local Candidate Source Hints

이 helper는 인터넷 없이 repo 안 자산만 사용해서, `CA2` packet replacement slot마다
바로 참고할 수 있는 `candidate / source / provenance hint`를 뽑습니다.

핵심 원칙
- scientific binding evidence를 새로 만들지 않습니다.
- `exact_smiles_local_curated`와 `weak_scaffold_analogy`를 엄격히 분리합니다.
- `1CA2` target anchor는 ligand provenance가 아니라 `target-context hint`로만 씁니다.

출력
- `runs/ca2_local_candidate_source_hints_current.json`
- `runs/ca2_local_candidate_source_hints_current.csv`
- `runs/ca2_local_candidate_source_hints_current.md`

hint 유형
- `target_anchor`
  - `1CA2` pocket center, target notes, pocket fingerprint
  - 용도: packet slot을 CA2 target context에 맞게 채우는 기준점
- `exact_smiles_local_curated`
  - repo 안 다른 ligand meta CSV에 동일 SMILES가 이미 존재하는 경우
  - 용도: `replacement_ligand_id / smiles / scaffold`를 더 안전하게 채우는 출발점
- `weak_scaffold_analogy`
  - repo 안 다른 domain에서 motif 수준 유사성만 보이는 경우
  - 용도: scaffold inspiration only
  - 비CA2 evidence이므로 provenance나 binding label을 복사하면 안 됩니다.

권장 사용 순서
1. `exact_smiles_local_curated`가 있는 slot부터 replacement workbook에 반영
2. exact match가 없는 slot은 `target_anchor`만 보고 수동 큐레이션
3. `weak_scaffold_analogy`는 ligand motif 탐색 메모로만 사용
