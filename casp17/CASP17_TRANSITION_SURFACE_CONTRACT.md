# CASP17 Transition Surface Contract

- status: `casp17_transition_surface_contract_ready`
- surface_ready: `True`
- blocker_count: `0`
- casp17_api_file_present: `True`
- casp17_router_registered: `True`
- casp17_upload_endpoint_present: `True`
- casp17_transition_endpoint_present: `True`
- casp17_upload_artifacts_referenced: `True`
- casp17_cleanup_artifacts_referenced: `True`
- casp17_cleanup_gate_artifacts_referenced: `True`
- casp17_fail_closed_flags_present: `True`
- upload_executed: `False`
- delete_executed: `False`
- native_accuracy_computed: `False`
- external_state_mutated: `False`

## Checks

| check | status | observed | required | artifact | reason |
| --- | --- | --- | --- | --- | --- |
| `casp17_api_file_present` | `pass` | `api/casp17.py=True` | `api/casp17.py exists` | `api/casp17.py` | CASP17 transition status needs a dedicated read-only API surface before upload and cleanup state can be inspected consistently. |
| `casp17_router_registered` | `pass` | `casp17_router_registered=True` | `api.main imports and includes casp17_router` | `api/main.py` | The CASP17 API must be mounted into the FastAPI app, not only defined as a detached module. |
| `casp17_upload_endpoint_present` | `pass` | `upload_endpoint=True` | `/casp17/upload route present` | `api/casp17.py` | Operators need a consolidated CASP17 current-upload status endpoint before any human upload decision. |
| `casp17_transition_endpoint_present` | `pass` | `transition_endpoint=True` | `/casp17/transition route present` | `api/casp17.py` | CASP17 transition and cleanup state need one read-only inspection surface during the move to CAMEO/product validation. |
| `casp17_upload_artifacts_referenced` | `pass` | `upload_artifacts_referenced=True` | `decision-rule, action-runway, and active-manifest lock artifacts referenced` | `api/casp17.py` | CASP17 upload status must be grounded in the existing fail-closed upload evidence packets. |
| `casp17_cleanup_artifacts_referenced` | `pass` | `cleanup_artifacts_referenced=True` | `large cleanup drilldown and protected cleanup review artifacts referenced` | `api/casp17.py` | CASP17 transition status must expose the cleanup payload context without promoting deletion. |
| `casp17_cleanup_gate_artifacts_referenced` | `pass` | `cleanup_gate_artifacts_referenced=True` | `cleanup approval gate, postcheck contract, and completion gate artifacts referenced` | `api/casp17.py` | CASP17 transition status must expose cleanup approval, postcheck, and completion gates before cleanup can be claimed. |
| `casp17_fail_closed_flags_present` | `pass` | `fail_closed_flags_present=True` | `upload/delete/native-accuracy/external-mutation flags returned as disabled` | `api/casp17.py` | The CASP17 API must be visibly read-only and must not imply upload, deletion, or native-accuracy computation happened. |

## Claim Boundary

CASP17 transition surface contract only; it audits whether the repository exposes read-only CASP17 upload and transition status surfaces from local files. It does not enter operator decisions, serialize an author code, create final upload files, submit to CASP, compute native accuracy, delete, move, archive, externalize, upload, or mutate external state.

## Next Step

- CASP17 transition surface is ready; operator decisions, author serialization, upload, and cleanup remain separately gated.
