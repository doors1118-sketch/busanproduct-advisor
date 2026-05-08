from typing import Dict, Any, List
import json
from app.router.intent_schema import RouterResult, Intent

ROUTING_BY_INTENT = {
    "legal_explanation": "legal_explanation_flow",
    "contract_review": "contract_review_flow",
    "local_purchase_support": "local_purchase_support_flow",
    "candidate_search": "candidate_search_flow",
    "item_eligibility": "item_eligibility_flow",
    "procurement_route_review": "procurement_route_review_flow",
    "mixed": "mixed_flow",
    "out_of_scope": "out_of_scope"
}

class DeterministicIntentValidator:
    def __init__(self):
        # 1. local_purchase_support triggers
        self.local_support_keywords = [
            "지역업체", "부산업체", "지역제품", "지역상품", "지역제한",
            "지역가점", "지역업체 참여도", "지역의무공동도급", "지역업체 우대"
        ]
        
        # 2. candidate_search triggers
        self.candidate_keywords = [
            "추천", "찾아줘", "후보", "업체 목록", "업체목록", "업체명",
            "부산업체 추천", "납품업체", "등록업체"
        ]
        
        # 3. item_eligibility triggers
        self.eligibility_keywords = [
            "중기경쟁", "중소기업자간 경쟁제품", "직접생산확인", "직생",
            "세부품명번호", "세부품명", "성능인증", "혁신제품",
            "기술개발제품", "우수조달"
        ]
        
        # 4. procurement_route_review triggers
        self.route_keywords = [
            "MAS", "다수공급자계약", "종합쇼핑몰", "제3자단가",
            "제3자를 위한 단가계약", "2단계경쟁", "납품요구",
            "나라장터", "조달청"
        ]

        # 5. Legal review triggers
        self.legal_review_keywords = [
            "수의계약", "입찰", "계약", "견적", "가능", "가능해",
            "기준", "법령", "시행령", "시행규칙", "예규", "조례",
            "검토", "위반", "제한", "금액", "한도"
        ]
        
        # 6. Execution verbs for contract_review
        self.execution_verbs = [
            "구매하려고", "발주하려고", "계약하려고", "어떻게 해야 해", "어떻게 해", "살 수 있나"
        ]
        
        # legal_explanation bypass verbs
        self.explanation_verbs = [
            "뭐야", "차이가 뭐야", "차이점이 뭐야", "어떤 거야", "무엇인가요", "무엇입니까", "뜻이 뭐야"
        ]

    def _add_focus(self, result: RouterResult, focus: str) -> None:
        if focus not in result.answer_focus:
            result.answer_focus.append(focus)
        
    def validate(self, text: str, parsed_json: Dict[str, Any]) -> RouterResult:
        try:
            result = RouterResult.model_validate(parsed_json)
        except Exception as e:
            # Fallback if invalid schema
            return RouterResult(
                primary_intent="out_of_scope",
                routing_decision="clarification_required",
                reason=f"Schema validation failed: {str(e)}"
            )
            
        text_no_space = text.replace(" ", "")
        slots = result.slots
        
        # ── 1. Force add intents AND sync slot flags ──
        
        has_local_kw = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.local_support_keywords)
        has_candidate_kw = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.candidate_keywords)
        has_eligibility_kw = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.eligibility_keywords)
        has_route_kw = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.route_keywords)
        has_legal_kw = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.legal_review_keywords)
        
        if has_local_kw:
            if "local_purchase_support" not in result.secondary_intents and result.primary_intent != "local_purchase_support":
                result.secondary_intents.append("local_purchase_support")
            slots.local_supplier_intent = True
            
        if has_candidate_kw:
            if "candidate_search" not in result.secondary_intents and result.primary_intent != "candidate_search":
                result.secondary_intents.append("candidate_search")
            slots.candidate_lookup_requested = True
            
        if has_eligibility_kw:
            if "item_eligibility" not in result.secondary_intents and result.primary_intent != "item_eligibility":
                result.secondary_intents.append("item_eligibility")
            slots.item_eligibility_requested = True
                
        if has_route_kw:
            if "procurement_route_review" not in result.secondary_intents and result.primary_intent != "procurement_route_review":
                result.secondary_intents.append("procurement_route_review")
            # procurement_route slot 자동 보정
            if not slots.procurement_route:
                if "MAS" in text or "다수공급자계약" in text or "다수공급자" in text_no_space:
                    slots.procurement_route = "mas"
                elif "종합쇼핑몰" in text:
                    slots.procurement_route = "shopping_mall"
                elif "제3자단가" in text or "제3자를 위한 단가계약" in text:
                    slots.procurement_route = "third_party_unit_price"
                
        # Location correction
        if ("부산업체" in text or "부산 지역업체" in text) and not slots.location:
            slots.location = "부산"
                
        # ── 2. Explanation / execution detection ──
        
        has_explanation_phrase = any(kw in text for kw in self.explanation_verbs)
        has_execution = any(kw in text for kw in self.execution_verbs)
        
        slot_count = 0
        if slots.buyer_name: slot_count += 1
        if slots.amount: slot_count += 1
        if slots.item_name or slots.service_type or slots.construction_type: slot_count += 1
        if slots.contract_method: slot_count += 1
        
        is_pure_explanation = (
            has_explanation_phrase
            and not has_execution
            and not slots.buyer_name
            and not slots.amount
            and not slots.item_name
            and not slots.service_type
            and not slots.construction_type
        )
        
        # ── 3. Contract review force-add ──
        
        if not has_explanation_phrase and (has_execution or slot_count >= 2):
            if "contract_review" not in result.secondary_intents and result.primary_intent != "contract_review":
                result.secondary_intents.append("contract_review")
        
        # Pure explanation override
        if is_pure_explanation:
            result.primary_intent = "legal_explanation"
            if "contract_review" in result.secondary_intents:
                result.secondary_intents.remove("contract_review")
                
        # ── 4. Auto local_purchase_support for contract_review ──
        
        is_contract = result.primary_intent == "contract_review" or "contract_review" in result.secondary_intents
        has_object = bool(slots.item_name or slots.service_type or slots.construction_type or slots.contract_object)
        
        if is_contract and not is_pure_explanation and has_object:
            if "local_purchase_support" not in result.secondary_intents and result.primary_intent != "local_purchase_support":
                result.secondary_intents.append("local_purchase_support")
                
        # ── 5. Conservative candidate_lookup_required ──
        
        explicit_candidate_req = has_candidate_kw
        implicit_candidate_ready = bool(slots.item_name) and slots.local_supplier_intent
        
        if explicit_candidate_req or implicit_candidate_ready:
            result.candidate_lookup_required = True
        else:
            result.candidate_lookup_required = False
        result.company_lookup_required = result.candidate_lookup_required
            
        # item_name clarification ONLY if NOT a pure explanation query
        has_local_or_candidate = any(i in [result.primary_intent] + result.secondary_intents for i in ["candidate_search", "local_purchase_support"])
        if has_local_or_candidate and not slots.item_name and not is_pure_explanation:
            if "item_name" not in result.clarification_needed:
                result.clarification_needed.append("item_name")
            result.candidate_lookup_required = False
            result.company_lookup_required = False
            
        # ── 6. legal_explanation_only ──
        
        if is_pure_explanation:
            result.legal_explanation_only = True
        elif result.primary_intent == "legal_explanation" and not slots.amount and not slots.buyer_name and not slots.item_name and not result.candidate_lookup_required and not slots.local_supplier_intent:
            result.legal_explanation_only = True
        else:
            result.legal_explanation_only = False

        # ── 6.5. Answer purpose flags ──
        intents = [result.primary_intent] + list(result.secondary_intents)
        result.legal_review_required = (
            result.primary_intent == "legal_explanation"
            or "contract_review" in intents
            or "procurement_route_review" in intents
            or "item_eligibility" in intents
            or has_legal_kw
            or bool(slots.amount or slots.contract_method or slots.quote_type)
        )
        result.local_purchase_support_required = (
            "local_purchase_support" in intents
            or bool(slots.local_supplier_intent)
            or has_local_kw
            or (("contract_review" in intents or result.primary_intent == "contract_review") and has_object and not is_pure_explanation)
        )
        result.company_lookup_required = result.candidate_lookup_required

        if result.legal_review_required:
            self._add_focus(result, "법령상 계약 가능 범위와 확인 필요사항")
        if result.local_purchase_support_required:
            self._add_focus(result, "부산 지역상품 구매지원 경로")
        if "procurement_route_review" in intents:
            self._add_focus(result, "MAS·종합쇼핑몰·조달청 구매경로")
        if "item_eligibility" in intents:
            self._add_focus(result, "중기경쟁제품·직접생산확인 등 품목 자격")
        if result.company_lookup_required:
            self._add_focus(result, "부산 업체·상품 후보 조회")
        if not result.answer_focus and result.primary_intent == "out_of_scope":
            self._add_focus(result, "지원 범위 확인")
            
        # ── 7. Confidence fallback ──
        
        if result.confidence < 0.65:
            result.routing_decision = "clarification_required"
            if not result.clarification_needed:
                result.clarification_needed.append("의도 불분명")
                
        # ── 8. Prohibited phrases ──
        
        prohibited = ["계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다", "지역제한 가능합니다", "낙찰 가능합니다"]
        for p in prohibited:
            if result.reason and p in result.reason:
                result.reason = result.reason.replace(p, "(금지된 표현 제거됨)")
                
        # ── 9. routing_decision default fill ──
        
        if not result.routing_decision:
            if result.confidence < 0.65:
                result.routing_decision = "clarification_required"
            else:
                result.routing_decision = ROUTING_BY_INTENT.get(result.primary_intent, "out_of_scope")
                
        return result
