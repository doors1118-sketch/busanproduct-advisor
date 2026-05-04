import json
import os
import pytest

# Adjust the path to be able to run locally
MAP_OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "purchase_support_rule_source_map.json")
CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "local_purchase_support_rule_catalog.json")

def load_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_map():
    with open(MAP_OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_all_rules_in_map():
    catalog = load_catalog()
    mapping = load_map()
    
    assert len(catalog) == len(mapping), "Mismatch in number of rules"
    for rule in catalog:
        rule_id = rule["rule_id"]
        assert rule_id in mapping, f"Rule {rule_id} missing from source map"

def test_wrong_match_excluded():
    mapping = load_map()
    for rule_id, data in mapping.items():
        for source_detail in data.get("primary_source_details", []):
            assert source_detail["status"] not in ("wrong_match", "needs_manual_source"), \
                f"Rule {rule_id} includes a source with excluded status"

def test_numeric_parameters():
    catalog = load_catalog()
    mapping = load_map()
    
    for rule in catalog:
        rule_id = rule["rule_id"]
        if rule.get("numeric_basis") and rule["numeric_basis"].get("parameter_refs"):
            mapped_params = mapping[rule_id]["numeric_parameters"]
            assert len(mapped_params) == len(rule["numeric_basis"]["parameter_refs"]), \
                f"Rule {rule_id} missing numeric parameters in mapping"
            
            for param in mapped_params:
                assert "candidate_source_ids" in param
                assert "parameter_ref" in param
                assert param["resolved_value"] is None
                assert param["requires_manual_numeric_verification"] is True
                assert param["parameter_status"] in ("candidate_only", "pending_resolution")

def test_status_enum():
    mapping = load_map()
    valid_statuses = {"mapped_verified", "mapped_candidate", "partial_mapped", "pending_resolution", "company_api_mapping_required"}
    for rule_id, data in mapping.items():
        assert data["source_chain_status"] in valid_statuses, f"Rule {rule_id} has invalid status {data['source_chain_status']}"

def test_mapped_verified_constraint():
    mapping = load_map()
    for rule_id, data in mapping.items():
        if data["source_chain_status"] == "mapped_verified":
            has_verified = any(ps["status"] == "verified" for ps in data.get("primary_source_details", []))
            assert has_verified, f"Rule {rule_id} is mapped_verified but has no verified sources"

def test_company_api_lookup_rules():
    mapping = load_map()
    lookup_rules = [
        "R_COMPANY_CANDIDATE_LOOKUP_GOODS",
        "R_COMPANY_CANDIDATE_LOOKUP_SERVICE",
        "R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION",
        "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP"
    ]
    
    for rule_id in lookup_rules:
        if rule_id in mapping:
            assert mapping[rule_id]["source_chain_status"] == "company_api_mapping_required", \
                f"Lookup Rule {rule_id} status should be company_api_mapping_required"
