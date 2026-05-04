"""
Phase 8.3: Company API Adapter

기존 모니터링 시스템 업체 API(app/company_api.py)를 챗봇 런타임 파이프라인에 연결한다.

원칙:
- candidate_lookup_required=True일 때만 호출
- timeout, error, empty result는 fail-closed 처리
- 후보업체는 "계약 가능 업체"가 아니라 "검토 후보"로 표시
- 실제 API 호출과 mock client를 분리
"""
import os
from typing import Optional, List
from dataclasses import dataclass, field
from app.router.intent_schema import RouterResult


@dataclass
class CompanyCandidateRow:
    company_id: str
    company_name_masked: str
    location: str
    business_type: str = ""
    main_products: List[str] = field(default_factory=list)
    display_status: str = "검토 후보"
    legal_eligibility_status: str = "확인 필요"


@dataclass
class CompanyCandidateResult:
    status: str  # success, empty, failed, skipped
    candidates: List[CompanyCandidateRow] = field(default_factory=list)
    total_found: int = 0
    search_query: str = ""
    error: Optional[str] = None


class CompanyAPIAdapter:
    """모니터링 시스템 업체 API를 호출하는 어댑터."""

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock

    def resolve(self, router_result: RouterResult) -> CompanyCandidateResult:
        """RouterResult를 기반으로 후보업체를 조회한다."""
        if not router_result.candidate_lookup_required:
            return CompanyCandidateResult(status="skipped")

        item_name = router_result.slots.item_name
        location = router_result.slots.location or "부산"

        if not item_name:
            return CompanyCandidateResult(
                status="skipped",
                error="item_name이 없어 후보조회를 수행할 수 없습니다."
            )

        if self.use_mock:
            return self._mock_search(item_name, location)
        else:
            return self._live_search(item_name, location)

    def _mock_search(self, item_name: str, location: str) -> CompanyCandidateResult:
        """Mock 후보 조회 (테스트용)."""
        return CompanyCandidateResult(
            status="success",
            candidates=[
                CompanyCandidateRow(
                    company_id="mock_001",
                    company_name_masked="가나다***",
                    location=location,
                    business_type="제조업",
                    main_products=[item_name],
                    display_status="검토 후보",
                    legal_eligibility_status="확인 필요"
                ),
                CompanyCandidateRow(
                    company_id="mock_002",
                    company_name_masked="라마바***",
                    location=location,
                    business_type="도매업",
                    main_products=[item_name],
                    display_status="검토 후보",
                    legal_eligibility_status="확인 필요"
                ),
            ],
            total_found=2,
            search_query=f"품목: {item_name}, 지역: {location}"
        )

    def _live_search(self, item_name: str, location: str) -> CompanyCandidateResult:
        """실제 모니터링 시스템 API 호출."""
        try:
            from app.company_api import search_by_product

            raw = search_by_product(item_name)
            candidates_raw = raw.get("candidates", [])

            if not candidates_raw:
                return CompanyCandidateResult(
                    status="empty",
                    total_found=0,
                    search_query=f"품목: {item_name}"
                )

            rows = []
            for c in candidates_raw:
                name = c.get("company_name", "")
                # 마스킹: 이름 앞 3자만 표시
                masked = name[:3] + "***" if len(name) >= 3 else name + "***"
                rows.append(CompanyCandidateRow(
                    company_id=c.get("company_id", "unknown"),
                    company_name_masked=masked,
                    location=c.get("location", location),
                    business_type=", ".join(c.get("license_or_business_type", [])),
                    main_products=c.get("main_products", []),
                    display_status="검토 후보",
                    legal_eligibility_status="확인 필요"
                ))

            return CompanyCandidateResult(
                status="success",
                candidates=rows[:10],
                total_found=len(candidates_raw),
                search_query=f"품목: {item_name}"
            )

        except Exception as e:
            return CompanyCandidateResult(
                status="failed",
                error=f"Company API 호출 실패: {str(e)}",
                search_query=f"품목: {item_name}"
            )
