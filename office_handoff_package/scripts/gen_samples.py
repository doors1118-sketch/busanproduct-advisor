"""프롬프트 조립 샘플 생성 스크립트"""
import sys, os
sys.path.insert(0, os.path.join('.', 'app'))
from prompting.keyword_pre_router import keyword_pre_route
from prompting.guardrail_selector import select_guardrails
from prompting.guardrail_sanity_check import apply_guardrail_sanity_check
from prompting.prompt_assembler import assemble_prompt, get_core_prompt_hash
from prompting.schemas import IntentRouteResult, IntentCandidate

questions = [
    "8천만원 컴퓨터 수의계약 가능해?",
    "소방공사 장비 구매인데 설치 포함이야",
    "시스템 구축하고 1년 운영까지 포함",
    "지방계약법 제30조 설명해줘",
    "업체가 여성기업 태그면 바로 1억 수의계약 가능해?",
]

for i, q in enumerate(questions):
    kr = keyword_pre_route(q)
    cands = [IntentCandidate(c, 0.85 if kr.is_unambiguous else 0.55) for c in kr.matched_categories[:2]]
    if not cands:
        cands = [IntentCandidate("unclear", 0.3)]
    ir = IntentRouteResult(candidates=cands, router_status="skipped" if kr.is_unambiguous else "simulated")
    gs = select_guardrails(ir, kr)
    gs = apply_guardrail_sanity_check(q, gs)
    assembled = assemble_prompt(kr, ir, gs, q)
    tag_check = "NON-USER POLICY CONTEXT" in assembled.dynamic_context
    uq_check = "USER QUESTION" in assembled.dynamic_context
    print(f"=== Q{i+1}: {q} ===")
    print(f"  Pre-Router: matched={kr.matched_categories} ambiguous={kr.ambiguous_keywords} unambiguous={kr.is_unambiguous}")
    print(f"  Intent: {[(c.label, c.confidence) for c in ir.candidates]} status={ir.router_status}")
    print(f"  Guardrails: {gs}")
    print(f"  core_prompt_hash: {assembled.core_prompt_hash[:16]}...")
    print(f"  Core in system_instruction: YES (len={len(assembled.core_prompt)})")
    print(f"  Dynamic context len: {len(assembled.dynamic_context)}")
    print(f"  [NON-USER POLICY CONTEXT] present: {tag_check}")
    print(f"  [USER QUESTION] present: {uq_check}")
    print()
