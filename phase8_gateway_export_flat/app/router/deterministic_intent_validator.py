from typing import Dict, Any, List
import json
from app.router.intent_schema import RouterResult, Intent

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
        
        # 5. Execution verbs for contract_review
        self.execution_verbs = [
            "구매하려고", "발주하려고", "계약하려고", "어떻게 해야 해", "어떻게 해", "살 수 있나"
        ]
        
        # legal_explanation bypass verbs
        self.explanation_verbs = [
            "뭐야", "차이가 뭐야", "차이점이 뭐야", "어떤 거야", "무엇인가요", "무엇입니까", "뜻이 뭐야"
        ]
        
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
        
        # 1. Force add local_purchase_support
        if any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.local_support_keywords):
            if "local_purchase_support" not in result.secondary_intents and result.primary_intent != "local_purchase_support":
                result.secondary_intents.append("local_purchase_support")
                
        # 2. Force add candidate_search
        if any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.candidate_keywords):
            if "candidate_search" not in result.secondary_intents and result.primary_intent != "candidate_search":
                result.secondary_intents.append("candidate_search")
                
        # 3. Force add item_eligibility
        if any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.eligibility_keywords):
            if "item_eligibility" not in result.secondary_intents and result.primary_intent != "item_eligibility":
                result.secondary_intents.append("item_eligibility")
                
        # 4. Force add procurement_route_review
        if any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.route_keywords):
            if "procurement_route_review" not in result.secondary_intents and result.primary_intent != "procurement_route_review":
                result.secondary_intents.append("procurement_route_review")
                
        # 5. Contract review condition adjustment
        is_explanation = any(kw in text for kw in self.explanation_verbs)
        has_execution = any(kw in text for kw in self.execution_verbs)
        
        # Count slots
        slots = result.slots
        slot_count = 0
        if slots.buyer_name: slot_count += 1
        if slots.amount: slot_count += 1
        if slots.item_name or slots.service_type or slots.construction_type: slot_count += 1
        if slots.contract_method: slot_count += 1
        
        if not is_explanation and (has_execution or slot_count >= 2):
            if "contract_review" not in result.secondary_intents and result.primary_intent != "contract_review":
                result.secondary_intents.append("contract_review")
        
        # If it's pure explanation, force it back
        if is_explanation:
            result.primary_intent = "legal_explanation"
            if "contract_review" in result.secondary_intents:
                result.secondary_intents.remove("contract_review")
                
        # 6. Conservative candidate_lookup_required logic
        explicit_candidate_req = any(kw in text or kw.replace(" ", "") in text_no_space for kw in self.candidate_keywords)
        implicit_candidate_ready = bool(slots.item_name) and slots.local_supplier_intent
        
        if explicit_candidate_req or implicit_candidate_ready:
            result.candidate_lookup_required = True
        else:
            result.candidate_lookup_required = False
            
        # Add item_name clarification if candidate search or local purchase support is hinted but no item
        has_local_or_candidate = any(i in [result.primary_intent] + result.secondary_intents for i in ["candidate_search", "local_purchase_support"])
        if has_local_or_candidate and not slots.item_name:
            if "item_name" not in result.clarification_needed:
                result.clarification_needed.append("item_name")
            result.candidate_lookup_required = False
            
        # 7. legal_explanation_only logic
        if result.primary_intent == "legal_explanation" and not slots.amount and not slots.buyer_name and not slots.item_name and not result.candidate_lookup_required and not slots.local_supplier_intent:
            result.legal_explanation_only = True
        elif result.primary_intent == "legal_explanation" and is_explanation:
            result.legal_explanation_only = True
        else:
            result.legal_explanation_only = False
            
        # 8. Fallback for confidence < 0.65
        if result.confidence < 0.65:
            result.routing_decision = "clarification_required"
            if not result.clarification_needed:
                result.clarification_needed.append("의도 불분명")
                
        # Prohibited phrases check
        prohibited = ["계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다", "지역제한 가능합니다", "낙찰 가능합니다"]
        for p in prohibited:
            if result.reason and p in result.reason:
                result.reason = result.reason.replace(p, "(금지된 표현 제거됨)")
                
        return result
