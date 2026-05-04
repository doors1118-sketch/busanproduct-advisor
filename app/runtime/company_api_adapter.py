"""
Phase 8.3: Company API Adapter

기존 모니터링 시스템 업체 API(app/company_api.py)를 챗봇 런타임 파이프라인에 연결한다.
app/company_api.py는 내부적으로 MONITORING_COMPANY_API_BASE_URL 기반 HTTP client이다.

원칙:
- candidate_lookup_required=True일 때만 호출
- timeout, error, empty result는 fail-closed 처리
- 후보업체는 "계약 가능 업체"가 아니라 "검토 후보"로 표시
- 실제 API 호출과 mock client를 분리
- location이 있으면 후처리 필터링으로 지역 한정
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
    search_location: str = ""
    error: Optional[str] = None


class CompanyAPIAdapter:
    """모니터링 시스템 업체 API를 호출하는 어댑터.

    app/company_api.py는 내부적으로 requests.get()을 통해
    MONITORING_COMPANY_API_BASE_URL (기본 http://127.0.0.1:8000)로 호출한다.
    즉, 별도 HTTP 서버가 아니라 같은 호스트의 FastAPI 엔드포인트를 호출하는 구조이다.
    """

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
            search_query=f"품목: {item_name}",
            search_location=location
        )

    def _live_search(self, item_name: str, location: str) -> CompanyCandidateResult:
        """실제 모니터링 시스템 API 호출.

        app/company_api.search_by_product()는 내부적으로
        GET {BASE_URL}/api/chatbot/company/product-search?product_name={item_name}
        을 호출한다. location 파라미터는 API에서 지원하지 않으므로
        결과를 후처리로 필터링한다.
        """
        try:
            from app.company_api import search_by_product

            raw = search_by_product(item_name)

            if raw.get("company_search_status") == "failed":
                return CompanyCandidateResult(
                    status="failed",
                    error=raw.get("error", "API 응답 실패"),
                    search_query=f"품목: {item_name}",
                    search_location=location
                )

            candidates_raw = raw.get("candidates", [])

            # location 후처리 필터링: API가 location 파라미터를 지원하지 않으므로
            if location:
                candidates_raw = [
                    c for c in candidates_raw
                    if location in c.get("location", "")
                ]

            if not candidates_raw:
                return CompanyCandidateResult(
                    status="empty",
                    total_found=0,
                    search_query=f"품목: {item_name}",
                    search_location=location
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
                search_query=f"품목: {item_name}",
                search_location=location
            )

        except Exception as e:
            return CompanyCandidateResult(
                status="failed",
                error=f"Company API 호출 실패: {str(e)}",
                search_query=f"품목: {item_name}",
                search_location=location
            )
