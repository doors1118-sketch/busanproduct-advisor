from dataclasses import dataclass
from typing import Optional

@dataclass
class SlotValues:
    buyer_type: Optional[str]        # "local_government" | "national_government" | "public_institution" | None
    contract_object: Optional[str]   # "construction" | "goods" | "service" | None
    amount: Optional[int]            # 추정가격 (원) | None
    procurement_route: Optional[str] # "pps_delegated_contract" | "mas" | "pps_shopping_mall" | ... | None
    contract_method: Optional[str]   # "general_competition" | "limited_competition" | "direct_contract" | ... | None
    item_name: Optional[str]         # 품목명 (일반명) | None
    detail_item_code: Optional[str]  # 세부품명번호 | None
    company_id: Optional[str]        # 특정 업체 ID | None
    location: str = "부산"            # 지역 (기본값: 부산)

@dataclass
class GatewayRequest:
    request_id: str                  # UUID
    user_query: str                  # 사용자 질문 원문
    slots: SlotValues                # 추출된 슬롯
