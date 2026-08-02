# CASP17 tracked artifact cleanup — 2026-08-02

This cleanup removes the expanded `casp17/` artifact tree from the current
donor-branch checkout. The exact pre-cleanup tree remains recoverable from Git;
no claim, policy, or active product configuration is changed by this inventory.

- Retaining commit: `4606ccd2de5a4cbb185434d2b259f34c74808383`
- Retaining tree: `5e5896c3ba2accf1fa88120b66d91bd9bdd2bb15`
- Files: `13,884`
- Aggregate bytes: `2,504,457,856`

| Extension | Files | Bytes |
| --- | ---: | ---: |
| cif | 1,485 | 1,091,866,253 |
| csv | 3,487 | 276,112,131 |
| fasta | 20 | 22,719 |
| gitignore | 1 | 109 |
| gitkeep | 37 | 0 |
| html | 1,516 | 123,369,462 |
| json | 829 | 236,844,360 |
| md | 4,024 | 9,713,976 |
| pdb | 507 | 141,498,533 |
| pml | 76 | 281,569 |
| png | 380 | 445,657,410 |
| svg | 1,507 | 178,979,401 |
| txt | 15 | 111,933 |

Restore without external lookup by checking out the retained tree from Git.
