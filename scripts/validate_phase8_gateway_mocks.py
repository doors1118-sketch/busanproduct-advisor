import json
import uuid
import sys
import os
from jsonschema import validate, ValidationError

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schema_path = os.path.join(base_dir, 'app', 'data', 'phase8_gateway_response_schema.json')
    
    mock_files = [
        'phase8_gateway_mock_responses_tc01_tc06.json',
        'phase8_gateway_mock_responses_tc07_tc12.json',
        'phase8_gateway_mock_responses_extra.json'
    ]
    
    # Load schema
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"FAIL: Schema load failed: {e}")
        sys.exit(1)
        
    prohibited_phrases = [
        "계약 가능합니다",
        "구매 가능합니다",
        "수의계약 가능합니다",
        "지역제한 가능합니다",
        "낙찰 가능합니다"
    ]
    
    failures = []
    tc_id_set = set()
    request_id_set = set()
    expected_tc_ids = {f"TC-T{i}" for i in range(1, 13)}
    expected_tc_ids.add("TC-EX1")
    
    for mock_file in mock_files:
        mock_path = os.path.join(base_dir, 'app', 'data', mock_file)
        
        # 1. JSON parsing
        try:
            with open(mock_path, 'r', encoding='utf-8') as f:
                content_str = f.read()
                data = json.loads(content_str)
        except Exception as e:
            failures.append({"file": mock_file, "tc": "N/A", "reason": f"JSON parse error: {e}"})
            continue
            
        # 2 & 3. version and schema_ref
        if data.get('mock_set_version') != 'v0.1.1':
            failures.append({"file": mock_file, "tc": "N/A", "reason": "mock_set_version is not v0.1.1"})
        if data.get('schema_ref') != 'phase8_gateway_response_schema.json':
            failures.append({"file": mock_file, "tc": "N/A", "reason": "schema_ref is not phase8_gateway_response_schema.json"})
            
        # 10. Prohibited phrases check at file level
        for phrase in prohibited_phrases:
            if phrase in content_str:
                failures.append({"file": mock_file, "tc": "File-Level", "reason": f"Prohibited phrase found: {phrase}"})
        
        for tc in data.get('test_cases', []):
            tc_id = tc.get('tc_id', 'Unknown')
            tc_id_set.add(tc_id)
            expected_trigger = tc.get('expected_trigger')
            gw_resp = tc.get('gateway_response', {})
            
            # 4. JSON Schema validation
            try:
                validate(instance=gw_resp, schema=schema)
            except ValidationError as e:
                failures.append({"file": mock_file, "tc": tc_id, "reason": f"Schema validation failed: {e.message}"})
            
            # 5. request_id UUID format, variant, and duplication
            req_id = gw_resp.get('request_id')
            if req_id in request_id_set:
                failures.append({"file": mock_file, "tc": tc_id, "reason": f"Duplicate request_id: {req_id}"})
            if req_id:
                request_id_set.add(req_id)
                try:
                    val = uuid.UUID(req_id)
                    if val.variant != uuid.RFC_4122:
                        failures.append({"file": mock_file, "tc": tc_id, "reason": "UUID variant is not RFC_4122"})
                except ValueError:
                    failures.append({"file": mock_file, "tc": tc_id, "reason": f"Invalid UUID format: {req_id}"})
                
            # 6. expected_trigger validation
            metadata = gw_resp.get('metadata', {})
            resolver_status = metadata.get('item_eligibility_resolver_status')
            trigger_grade = metadata.get('item_eligibility_trigger_grade')
            
            if expected_trigger in ["not_triggered", "data_unavailable", "ambiguous"]:
                if resolver_status != expected_trigger:
                    failures.append({"file": mock_file, "tc": tc_id, "reason": f"expected_trigger={expected_trigger} but resolver_status={resolver_status}"})
            elif expected_trigger in ["silent", "explicit"]:
                if resolver_status != "resolved":
                    failures.append({"file": mock_file, "tc": tc_id, "reason": f"expected_trigger={expected_trigger} but resolver_status={resolver_status}"})
                if trigger_grade != expected_trigger:
                    failures.append({"file": mock_file, "tc": tc_id, "reason": f"expected_trigger={expected_trigger} but trigger_grade={trigger_grade}"})
            
            # 7 & 8. procedure_context
            proc_ctx = gw_resp.get('procedure_context', {})
            if proc_ctx.get('judgment_eligible') is not False:
                failures.append({"file": mock_file, "tc": tc_id, "reason": "procedure_context.judgment_eligible is not false"})
                
            usage = proc_ctx.get('usage')
            if usage != "answer_builder_procedure_section_only":
                failures.append({"file": mock_file, "tc": tc_id, "reason": f"procedure_context.usage is invalid for read-only: {usage}"})
                
            for source in proc_ctx.get('sources', []):
                s_usage = source.get('usage')
                if s_usage != "procedure_guidance_only":
                    failures.append({"file": mock_file, "tc": tc_id, "reason": f"procedure_context.sources[].usage is not procedure_guidance_only: {s_usage}"})

            # metadata consistency
            item_elig_result = gw_resp.get('item_eligibility_result', {})
            context = item_elig_result.get('context', {}) or {}
            company_candidate_ctx = gw_resp.get('company_candidate_context') or {}

            if resolver_status != item_elig_result.get('resolver_status'):
                failures.append({"file": mock_file, "tc": tc_id, "reason": "metadata resolver_status does not match item_eligibility_result.resolver_status"})
            
            ctx_trigger_grade = context.get('trigger_grade') if context else None
            if trigger_grade != ctx_trigger_grade:
                failures.append({"file": mock_file, "tc": tc_id, "reason": "metadata trigger_grade does not match context.trigger_grade"})

            meta_enrich_applied = metadata.get('enrichment_applied')
            cand_enrich_applied = company_candidate_ctx.get('enrichment_applied', False)
            if meta_enrich_applied != cand_enrich_applied:
                failures.append({"file": mock_file, "tc": tc_id, "reason": "metadata enrichment_applied does not match company_candidate_context"})

            meta_enrich_scope = metadata.get('enrichment_scope')
            cand_enrich_scope = company_candidate_ctx.get('enrichment_scope')
            if meta_enrich_scope != cand_enrich_scope:
                failures.append({"file": mock_file, "tc": tc_id, "reason": "metadata enrichment_scope does not match company_candidate_context"})
                
    if tc_id_set != expected_tc_ids:
        failures.append({"file": "All", "tc": "N/A", "reason": f"TC ID mismatch. Expected: {expected_tc_ids}, Found: {tc_id_set}"})
    if len(tc_id_set) != 13:
        failures.append({"file": "All", "tc": "N/A", "reason": f"Total TC count is not 13 (found {len(tc_id_set)})"})

    if failures:
        print("Validation FAILED")
        for fail in failures:
            print(f"- File: {fail['file']}, TC: {fail['tc']}, Reason: {fail['reason']}")
        sys.exit(1)
    else:
        print("Validation PASSED")
        sys.exit(0)

if __name__ == '__main__':
    main()
