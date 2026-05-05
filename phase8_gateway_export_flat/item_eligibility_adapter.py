"""
Phase 9.1: Item Eligibility Adapter (P0)

item_name 또는 detail_item_code를 바탕으로 중기경쟁제품, 직접생산확인 대상 여부,
그리고 업체 인증 상태를 조회하여 품목 적격성을 판별하는 어댑터입니다.
현재 버전은 실제 DB 대신 item_eligibility_mock_seed_data.json을 사용합니다.
"""
import os
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from pydantic import BaseModel

class ItemEligibilityContext(BaseModel):
    detail_item_resolved: bool = False
    detail_item_code: Optional[str] = None
    detail_item_name: Optional[str] = None
    is_sme_competition_product: Optional[bool] = None
    direct_production_required: Optional[bool] = None
    company_cert_status: Optional[str] = None
    eligibility_status: Optional[str] = None
    candidate_action: Optional[str] = None
    candidate_items: Optional[List[Dict[str, str]]] = None
    procurement_support_message: Optional[str] = None
    legal_conclusion_allowed: bool = False

def normalize_item_name(s: str) -> str:
    if not s:
        return ""
    return s.lower().replace(" ", "").replace("-", "").strip()

class ItemEligibilityResult(BaseModel):
    resolver_status: str  # "resolved", "ambiguous", "not_found", "not_triggered"
    context: Optional[ItemEligibilityContext] = None

class ItemEligibilityAdapter:
    def __init__(self, data_path: Optional[str] = None):
        if not data_path:
            # Default to app/data/item_eligibility_mock_seed_data.json relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_path = os.path.join(base_dir, "app", "data", "item_eligibility_mock_seed_data.json")
        
        self.data: Dict[str, Any] = {}
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            import logging
            logging.warning(f"[ItemEligibilityAdapter] Mock seed data not found at {data_path}")

    def resolve(self, item_name: Optional[str], detail_item_code: Optional[str], company_id: Optional[str]) -> ItemEligibilityResult:
        if not item_name and not detail_item_code:
            return ItemEligibilityResult(resolver_status="not_triggered")

        if not self.data:
            return ItemEligibilityResult(
                resolver_status="data_unavailable",
                context=ItemEligibilityContext(
                    detail_item_name=item_name or detail_item_code,
                    eligibility_status="data_unavailable",
                    procurement_support_message="품목 적격성 DB 조회가 불가합니다.",
                    legal_conclusion_allowed=False
                )
            )

        # 1. Alias Map Search
        if not detail_item_code and item_name:
            alias_map = self.data.get("item_alias_map", [])
            norm_q = normalize_item_name(item_name)
            
            exact_matches = []
            contains_matches = []
            for m in alias_map:
                a_name = m.get("alias_name", "")
                a_norm = m.get("alias_normalized", "")
                norm_a = normalize_item_name(a_name)
                norm_a2 = normalize_item_name(a_norm)
                
                if item_name.lower() == a_name.lower() or norm_q == norm_a or norm_q == norm_a2:
                    exact_matches.append(m)
                elif norm_q in norm_a or norm_q in norm_a2:
                    contains_matches.append(m)
            
            # exact match 우선, 없으면 contains match
            matches = exact_matches if exact_matches else contains_matches
            
            # 점수순 정렬
            matches.sort(key=lambda x: x.get("match_confidence", 0.0), reverse=True)
            
            if not matches:
                return ItemEligibilityResult(
                    resolver_status="not_found",
                    context=ItemEligibilityContext(
                        detail_item_name=item_name,
                        eligibility_status="not_found"
                    )
                )
            elif len(matches) > 1:
                candidates = [
                    {
                        "detail_item_code": m["detail_item_code"],
                        "detail_item_name": m.get("alias_name", ""),
                        "match_reason": "exact" if m in exact_matches else "contains"
                    } for m in matches
                ]
                return ItemEligibilityResult(
                    resolver_status="ambiguous",
                    context=ItemEligibilityContext(
                        detail_item_name=item_name,
                        eligibility_status="ambiguous",
                        candidate_items=candidates,
                        procurement_support_message="여러 세부품명 후보가 발견되었습니다."
                    )
                )
            else:
                detail_item_code = matches[0]["detail_item_code"]

        # 2. detail_item_code 확정 시 데이터 조회
        if detail_item_code:
            # item master
            master = self.data.get("procurement_item_master", [])
            item_info = next((i for i in master if i["detail_item_code"] == detail_item_code), None)
            item_display_name = item_info["detail_item_name"] if item_info else item_name

            # sme competition product
            sme_list = self.data.get("sme_competition_product_item", [])
            sme_info = next((s for s in sme_list if s["detail_item_code"] == detail_item_code), None)
            is_sme = sme_info["is_sme_competition_product"] if sme_info else False

            # direct production requirement
            dp_list = self.data.get("direct_production_requirement", [])
            dp_info = next((d for d in dp_list if d["detail_item_code"] == detail_item_code), None)
            is_dp = dp_info["direct_production_required"] if dp_info else False

            # company cert status
            company_cert_status = None
            if company_id:
                cert_list = self.data.get("company_direct_production_cert_mapping", [])
                cert_info = next((c for c in cert_list if c["detail_item_code"] == detail_item_code and c["company_id"] == company_id), None)
                if cert_info:
                    company_cert_status = cert_info.get("cert_status")
                else:
                    company_cert_status = "not_found"

            # determine granular eligibility_status
            eligibility_status = "item_resolved_company_not_checked"
            if is_dp:
                if company_cert_status is None:
                    eligibility_status = "item_resolved_company_not_checked"
                elif company_cert_status == "not_found":
                    eligibility_status = "cert_not_found"
                elif company_cert_status == "expired":
                    eligibility_status = "cert_expired"
                elif company_cert_status == "verified":
                    eligibility_status = "cert_verified_candidate"
            else:
                eligibility_status = "item_resolved_company_not_checked"

            return ItemEligibilityResult(
                resolver_status="resolved",
                context=ItemEligibilityContext(
                    detail_item_resolved=True,
                    detail_item_code=detail_item_code,
                    detail_item_name=item_display_name,
                    is_sme_competition_product=is_sme,
                    direct_production_required=is_dp,
                    company_cert_status=company_cert_status,
                    eligibility_status=eligibility_status,
                    legal_conclusion_allowed=False
                )
            )

        return ItemEligibilityResult(resolver_status="not_triggered")
