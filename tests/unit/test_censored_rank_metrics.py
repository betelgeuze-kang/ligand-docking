import pytest
from betelgeuze_engine.product.censored_rank_metrics import endpoint_order, compare_rankings

def ep(value, relation="="):
    return dict(value=value, relation=relation)

@pytest.mark.parametrize("left,right,expected", [
    (ep(1),ep(2),-1), (ep(2),ep(2),0),
    (ep(2),ep(2,">"),-1), (ep(3),ep(2,">"),None),
    (ep(1,">"),ep(2,">"),None),
])
def test_strict_bounds_and_reversal(left,right,expected):
    assert endpoint_order(left,right)==expected
    assert endpoint_order(right,left)==(-expected if expected is not None else None)

@pytest.mark.parametrize("bad", [ep(0),ep(float("nan")),ep(True),ep(2,"<="),ep(float("inf"))])
def test_invalid_endpoints_rejected_even_without_pairs(bad):
    with pytest.raises(ValueError):
        compare_rankings({"a":bad},{"arm":{}})

def test_missing_and_unknown_pairs_preserve_denominator():
    result=compare_rankings({"a":ep(1),"b":ep(2),"c":ep(3,">"),"d":ep(4,">")},
                            {"full":{"a":4,"b":3,"c":2,"d":1},"missing":{"a":4,"b":3,"c":None}})
    assert result["full"]["counts"]==dict(concordant=5,discordant=0,score_tie=0,endpoint_tie=0,endpoint_order_unknown=1,score_missing=0)
    assert result["missing"]["all_pairs"]==6
    assert result["missing"]["known_endpoint_pairs"]==5
    assert result["missing"]["scored_comparable_pairs"]==1
    assert result["missing"]["counts"]["score_missing"]==4

def test_ties_and_score_direction():
    endpoints={"a":ep(1),"b":ep(2),"c":ep(2)}
    result=compare_rankings(endpoints,{"tied":{"a":0,"b":0,"c":0},"reverse":{"a":0,"b":1,"c":1}})
    assert result["tied"]["concordance"]==.5
    assert result["reverse"]["concordance"]==0
    assert result["tied"]["counts"]["endpoint_tie"]==1

@pytest.mark.parametrize("scores", [{"z":1},{"a":float("nan")},{"a":True}])
def test_bad_scores_rejected(scores):
    with pytest.raises(ValueError):
        compare_rankings({"a":ep(1)},{"arm":scores})

def test_missing_arm_and_permutation_do_not_impute():
    endpoints={"b":ep(2),"a":ep(1)}
    result=compare_rankings(endpoints,{"empty":{},"full":{"a":2,"b":1}})
    assert result==compare_rankings(dict(reversed(list(endpoints.items()))),{"empty":{},"full":{"b":1,"a":2}})
    assert result["empty"]["concordance"] is None
    assert result["empty"]["candidate_denominator"]==2
