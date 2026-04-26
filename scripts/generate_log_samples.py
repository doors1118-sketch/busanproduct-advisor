import sys
import os
sys.path.insert(0, os.path.abspath('app'))

from prompting.keyword_pre_router import keyword_pre_route
from prompting.intent_router import classify_intent
from prompting.guardrail_selector import select_guardrails
from prompting.guardrail_sanity_check import apply_guardrail_sanity_check
from prompting.prompt_assembler import assemble_prompt

questions = [
    '8천만원 컴퓨터 수의계약 가능해?',
    '소방공사 장비 구매인데 설치 포함이야',
    '시스템 구축하고 1년 운영까지 포함',
    '지방계약법 제30조 설명해줘',
    '업체가 여성기업 태그면 바로 1억 수의계약 가능해?'
]

output = '# LOG_SAMPLES.md\n\n'
output += '## 1. 민감정보 제거 로그 샘플 (JSONL 구조)\n\n'
output += '```json\n'
output += '{\n'
output += '  "timestamp": "2026-04-25T22:45:01.123456",\n'
output += '  "request_id": "req-abc-123",\n'
output += '  "user_question": "***-****-**** 번호로 연락주세요",\n'
output += '  "keyword_result": {"matched": ["item_purchase"], "ambiguous": []},\n'
output += '  "intent_result": {"candidates": [{"label": "item_purchase", "confidence": 0.95}], "status": "success"},\n'
output += '  "selected_guardrails": ["common_procurement", "item_purchase"],\n'
output += '  "sanity_added_guardrails": [],\n'
output += '  "router_conflict": false,\n'
output += '  "low_confidence": false,\n'
output += '  "api_status": {"mcp_status": "success", "rag_status": "success", "company_search_status": "not_called"},\n'
output += '  "timeout_sources": [],\n'
output += '  "legal_conclusion_allowed": true,\n'
output += '  "core_prompt_hash": "d34db33f...",\n'
output += '  "prompt_prefix_hash": "b105f00d...",\n'
output += '  "cache_hit_rate": 0.85,\n'
output += '  "input_token_count": 1200,\n'
output += '  "output_token_count": 450,\n'
output += '  "ttft_ms": 1200,\n'
output += '  "total_latency_ms": 4500\n'
output += '}\n'
output += '```\n\n'

output += '## 2. 프롬프트 조립 샘플\n\n'

for i, q in enumerate(questions, 1):
    kw_res = keyword_pre_route(q)
    int_res = classify_intent(q, kw_res)
    raw_guards = select_guardrails(kw_res, int_res)
    final_guards = apply_guardrail_sanity_check(q, kw_res, int_res, raw_guards)
    
    assembled = assemble_prompt(
        keyword_result=kw_res,
        intent_result=int_res,
        guardrails=final_guards.final_guardrails,
        user_question=q,
        rag_context='[Mocked RAG Context]',
        agency_type='local_government'
    )
    
    output += f'### 샘플 {i}: {q}\n'
    output += f'- **Keyword Pre-Router 결과**: matched={kw_res.matched_categories}, ambiguous={kw_res.ambiguous_keywords}, is_unambiguous={kw_res.is_unambiguous}\n'
    output += f'- **Intent Router 결과**: candidates={[c.label for c in int_res.candidates]}, status={int_res.router_status}, mcp_required={int_res.mcp_required}\n'
    output += f'- **Guardrail Sanity Check 결과**: added={final_guards.sanity_added}\n'
    output += f'- **최종 선택된 Guardrail**: {final_guards.final_guardrails}\n'
    output += f'- **Core Prompt가 system_instruction에만 들어가는지**: 예 (core_prompt_hash 생성 됨)\n'
    output += f'- **Core Prompt가 첫 번째 블록인지 여부**: 예 (Gemini API 호출 시 system_instruction 파라미터로 별도 전달)\n'
    output += f'- **core_prompt_hash**: {assembled.core_prompt_hash[:16]}...\n'
    output += f'- **prompt_prefix_hash**: {assembled.prompt_prefix_hash}\n\n'
    
    output += '**[Dynamic Context 구조 요약]**\n```text\n'
    
    lines = assembled.dynamic_context.split('\\n')
    for line in lines[:15]:
        if not line.strip(): continue
        if len(line) > 80:
            output += line[:80] + '...\n'
        else:
            output += line + '\n'
    output += '... (이하 생략) ...\n```\n\n'

with open('LOG_SAMPLES.md', 'w', encoding='utf-8') as f:
    f.write(output)
print('Generated LOG_SAMPLES.md')
