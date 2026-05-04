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
            expected_trigger = tc.get('expected_trigger')
            gw_resp = tc.get('gateway_response', {})
            
            # 4. JSON Schema validation
            try:
                validate(instance=gw_resp, schema=schema)
            except ValidationError as e:
                failures.append({"file": mock_file, "tc": tc_id, "reason": f"Schema validation failed: {e.message}"})
            
            # 5. request_id UUID format and variant
            req_id = gw_resp.get('request_id')
            try:
                val = uuid.UUID(req_id)
                if val.variant != uuid.RFC_4122:
                    failures.append({"file": mock_file, "tc": tc_id, "reason": "UUID variant is not RFC_4122"})
                # We skip randomness check (version 4) as requested: "고정 fixture UUID를 사용하므로 무작위성 검증은 하지 않는다."
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
            
            # 7. procedure_context.judgment_eligible == false
            proc_ctx = gw_resp.get('procedure_context', {})
            if proc_ctx.get('judgment_eligible') is not False:
                failures.append({"file": mock_file, "tc": tc_id, "reason": "procedure_context.judgment_eligible is not false"})
                
            # 8. procedure_context.usage
            usage = proc_ctx.get('usage')
            if usage != "answer_builder_procedure_section_only":
                failures.append({"file": mock_file, "tc": tc_id, "reason": f"procedure_context.usage is invalid for read-only: {usage}"})
                
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
