# CASP17 Strict-Blind Internal-Like Source Review

- generated: `2026-06-02T03:41:17+09:00`
- status: `strict_blind_internal_like_source_review_all_post_native`
- candidates/triage-match: `166/166` `True`
- mapped/pre-native/post-native/same-day/missing/unmapped: `166/0/166/0/0/0`
- targets/all-post-native/pre-native-targets: `10/10/0`
- prediction date range: `2026-02-19` to `2026-02-22`
- first blocker: `HIST_BBA5` `prediction_not_before_native` `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_bba5_sample000_step00020.pdb`

## Target Rollup

| target | candidates | pre-native | post-native | date range | status | first candidate |
| --- | ---: | ---: | ---: | --- | --- | --- |
| `HIST_BBA5` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_bba5_sample000_step00020.pdb` |
| `HIST_CHIGNOLIN` | 22 | 0 | 22 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_chignolin_sample000_step00010.pdb` |
| `HIST_CRAMBIN` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_crambin_sample000_step00020.pdb` |
| `HIST_FSD_1` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_fsd_1_sample000_step00020.pdb` |
| `HIST_GB1_MINI` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_gb1_mini_sample000_step00020.pdb` |
| `HIST_PROTEIN_A_BDOMAIN` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_protein_a_bdomain_sample000_step00020.pdb` |
| `HIST_TRP_CAGE` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_trp_cage_sample000_step00020.pdb` |
| `HIST_UBIQUITIN_MINI` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_ubiquitin_mini_sample000_step00020.pdb` |
| `HIST_VILLIN_HP35` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_villin_hp35_sample000_step00020.pdb` |
| `HIST_WW_DOMAIN_FIP35` | 16 | 0 | 16 | `2026-02-19`-`2026-02-22` | `target_all_internal_like_candidates_post_native` | `data/internal_structures/nightly/2026-02-19-ops-full-dashboard-r1/internal_post_ww_domain_fip35_sample000_step00020.pdb` |

## Claim Boundary

CASP17 strict-blind internal-like source review only. It uses durable path dates and existing source-request native release dates to reject post-native local artifacts before source-gate use. It does not use filesystem mtime, does not approve no-leak provenance, and does not promote any candidate into strict-blind proof.
