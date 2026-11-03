# Historical global-orientation source snapshot

This snapshot supports **static verification of the archived protocol only**.
It is never imported, added to `sys.path`, or executed. It is inside the existing
`benchmarks/**` product-image exclusion.

The protocol and all of its original identities remain unchanged:

- Protocol: `7ecbb5fa10ce95b035cdc0c11b2c27469caa019aa994315831ad2631cca0fdc3`
- Full 187-file Engine V2 Python manifest: `7db2a8ba4bdf4c70c941b106892e36aaccd253c6a88d31ac4ef78e73fd416aa7`
- PoseBusters local evaluation source manifest: `2f843fee77e2d40d70882d2bb959fc828f3806921b915a0e702b1a138cc777bb`

The bytes were taken from commit
`a0c06c20cd182741258d73b4218214bbdd4928e4`, tree
`0acd4a1b16d0f3cd3c2ce584a833235982ba4a7e`. `manifest.json` binds every
original Engine V2 Python file, the original public redocking runner, and the
four additional configuration files consumed by the verifier. The five source
files that are changing in the P0/P1 branch are retained verbatim as `.py.txt`
data. The remaining files are shared with the checkout only while their exact
size and SHA-256 still match the original manifest; any drift or absence fails.

The verifier authenticates the manifest against its independently fixed raw
SHA-256, then checks all 192 file payloads before checking the original protocol.
Changing an archived file and updating its manifest row cannot bypass the fixed
manifest identity. The canonical engine and evaluation manifests are rederived
from those verified bytes and must retain the original identities above.

Use the explicit archival mode:

```bash
python tools/verify_engine_v2_global_orientation_contaminated_development.py --historical-snapshot
```

Its distinct JSON receipt says `verification_mode=historical_static_source_only`,
`live_checkout_verified=false`, and `execution_authorized=false`, and lists the
actual current-source differences. It does not validate a current executable or
authorize historical execution. The default CLI and `verify_protocol()` continue
to require the original live source bytes and reject the newer P0/P1 checkout.
The P0/P1 run has its own separately recorded source and evaluator identities.
