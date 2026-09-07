"""Development data must not cross evaluation or missing-evidence boundaries."""
from __future__ import annotations

import csv
import itertools

import pytest
import torch

from tools import train_residual_production_score_model as trainer
from tools.product.stage2_skip_router import apply_stage2_skip_router, route_stage2_candidate


def rows():
    return [dict(ligand_id=f"l{i}", target="synthetic", raw_score=0., mean_min_distance_A=3.,
                 is_binder=i % 2, delta_score=-1., role="fit") for i in range(24)]


def write(path, data):
    fields = list(dict.fromkeys(key for row in data for key in row))
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(data)


@pytest.mark.parametrize('column,value', [
    *[(k,v) for k,v in itertools.product(('role','split','dataset_split'),
      ('test','holdout','validation','val','blind','fresh128','fresh_128','fresh-128'))],
    ('evaluation_only',True), ('evaluation_only','1'), ('role',' HOLDOUT '),
])
@pytest.mark.parametrize('entry', ['train','matrix','split','cache'])
def test_evaluation_declarations_rejected_at_every_entry(tmp_path, column, value, entry):
    data=rows(); data[3][column]=value
    p=tmp_path/'input.csv'; write(p,data)
    out=tmp_path/'candidate.pt'
    with pytest.raises(ValueError,match='evaluation_only_training_row'):
        if entry=='matrix': trainer._matrix(data, [], [])
        elif entry=='split': trainer._split_indices(data,42,.8)
        elif entry=='cache':
            trainer.try_skip_training(input_csv=str(p),out_checkpoint=str(out),out_json=str(tmp_path/'summary.json'),
                force_derivation_json='/dev/null',fingerprint_json=str(tmp_path/'fp.json'),
                epochs=1,hidden_dim=8,batch_size=8,lr=.001,weight_decay=0.,train_ratio=.8,seed=42)
        else: trainer.train_residual_production_score_model(input_csv=str(p),out_checkpoint=str(out),epochs=1,hidden_dim=8,device_name='cpu')
    assert not out.exists()


@pytest.mark.parametrize('value', [None,'','  ','bad','nan','inf',float('nan'),float('inf'),True,{},[1]])
def test_required_score_not_coerced_to_zero(value):
    data=rows(); data[0]['raw_score']=value
    with pytest.raises(ValueError,match='feature:raw_score'):
        trainer._matrix(data,[],[])


def test_optional_missing_and_true_zero_distinguishable():
    data=rows()[:2]; data[0]['mean_min_distance_A']=''; data[1]['mean_min_distance_A']=0.
    x,*_,names=trainer._matrix(data,[],[])
    i=names.index('mean_min_distance_A'); m=names.index('mean_min_distance_A__observed')
    assert x[:,i].tolist()==[0.,0.]
    assert x[:,m].tolist()==[0.,1.]


@pytest.mark.parametrize('key', ['mean_min_distance_A','refine_tier_delta'])
@pytest.mark.parametrize('value', ['oops',float('inf'),True])
def test_optional_but_supplied_invalid_features_fail(key,value):
    data=rows();data[0][key]=value
    with pytest.raises(ValueError,match=f'feature:{key}'):
        trainer._matrix(data,[],[],refine_fields=['refine_tier_delta'])


def test_feature_inventory_fitted_only_to_training_partition(tmp_path):
    data=rows(); train,val=trainer._split_indices(data,42,.8)
    for i in val: data[i]['refine_tier_delta']=2.
    path=tmp_path/'data.csv';write(path,data)
    previous=torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        result=trainer.train_residual_production_score_model(input_csv=str(path),out_checkpoint=str(tmp_path/'m.pt'),
                    epochs=1,hidden_dim=8,batch_size=8,device_name='cpu')
    finally: torch.set_num_threads(previous)
    assert 'refine_tier_delta' not in result['feature_names']
    assert result['production_checkpoint_ready'] is False


@pytest.mark.parametrize('rank',[None,'',float('nan'),float('inf'),-float('inf'),'nan','bad',True,False,-.1,1.1,[],{}])
def test_unknown_rank_never_means_tail(rank):
    kept,summary=apply_stage2_skip_router([{'prior_rank_proxy':rank}])
    assert len(kept)==1 and summary['stage2_skip_count']==0
    assert kept[0]['stage2_prior_rank_proxy'] is None
    assert kept[0]['stage2_skip_reason']=='missing_or_invalid_rank'


def test_missing_rank_and_direct_default_preserve_candidate():
    assert len(apply_stage2_skip_router([{}])[0])==1
    assert route_stage2_candidate()['stage2_skip_applied'] is False


@pytest.mark.parametrize('key', ['affinity_hint','onsps_norm','mw_norm'])
def test_invalid_hints_cannot_cause_skip(key):
    kept,_=apply_stage2_skip_router([dict(prior_rank_proxy=1.,**{key:'bad'})])
    assert len(kept)==1 and kept[0]['stage2_skip_reason']=='invalid_routing_hint'


def test_invalid_primary_rank_is_not_hidden_by_alias():
    kept,_=apply_stage2_skip_router([dict(prior_rank_proxy='nan',rank_pct=1.)])
    assert len(kept)==1


@pytest.mark.parametrize('value',[None,''])
def test_missing_primary_rank_can_use_valid_alias(value):
    kept,summary=apply_stage2_skip_router([dict(prior_rank_proxy=value,rank_pct=0.)])
    assert len(kept)==1 and kept[0]['stage2_prior_rank_proxy']==0.
