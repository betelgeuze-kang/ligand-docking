from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_cross_family_residual_shadow_layer_plan', ROOT / 'tools' / 'build_cross_family_residual_shadow_layer_plan.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_build_payload_contains_expected_families():
    payload = mod.build_payload()
    fams = {row['family'] for row in payload['family_rows']}
    assert {'gpcr','ion_channel','kinase','idp','non_kinase_enzyme_ca2','nuclear_receptor_pxr','transporter'} <= fams
    assert payload['summary']['mode'] == 'shadow_only_first'
