from nisayon.engine.integrate import evaluator_contract_probe


def test_merged_evaluator_consumes_producer_predicates_and_action_clock():
    result = evaluator_contract_probe()
    assert result["all_met"], result
    assert result["evidence_origin"] == "synthetic_development_interface_probe"
