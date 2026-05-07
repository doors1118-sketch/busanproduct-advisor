"""
Phase 11: Company API Adapter (Live 전환 + Fail-Closed 고도화)

기존 모니터링 시스템 업체 API(app/company_api.py)를 챗봇 런타임 파이프라인에 연결한다.
app/company_api.py는 내부적으로 MONITORING_COMPANY_API_BASE_URL 기반 HTTP client이다.

원칙:
- candidate_lookup_required=True일 때만 호출
- timeout, error, empty result는 fail-closed 처리
- 후보업체는 "계약 가능 업체"가 아니라 "검토 후보"로 표시
- 환경변수 USE_MOCK_COMPANY_API로 Mock/Live 전환 (기본값: true → Mock)
- location이 있으면 후처리 필터링으로 지역 한정
"""
import os
import logging
from typing import Optional, List
from dataclasses import dataclass, field
from app.router.intent_schema import RouterResult

logger = logging.getLogger(__name__)


# ── 방어적 타입 정규화 헬퍼 ──
def _as_str(value) -> str:
    """None이나 비문자열을 빈 문자열로 안전 변환."""
    return "" if value is None else str(value)


def _as_list(value) -> list:
    """None/문자열/기타를 list로 안전 변환.
    - None → []
    - list → 그대로
    - str → [str]  (글자 단위 join 방지)
    - 기타 → [str(value)]
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [str(value)]

# ── 환경변수 기반 기본값 ──
def _default_use_mock() -> bool:
    """USE_MOCK_COMPANY_API 환경변수를 읽어 기본값을 결정한다.
    미설정이거나 'true'이면 Mock, 'false'이면 Live."""
    val = os.getenv("USE_MOCK_COMPANY_API", "true").strip().lower()
    return val != "false"


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
    error_type: Optional[str] = None  # timeout, connection, api_error, parse_error, unknown


class CompanyAPIAdapter:
    """모니터링 시스템 업체 API를 호출하는 어댑터.

    app/company_api.py는 내부적으로 requests.get()을 통해
    MONITORING_COMPANY_API_BASE_URL (기본 http://127.0.0.1:8000)로 호출한다.
    즉, 별도 HTTP 서버가 아니라 같은 호스트의 FastAPI 엔드포인트를 호출하는 구조이다.
    """

    def __init__(self, use_mock: Optional[bool] = None):
        if use_mock is None:
            self.use_mock = _default_use_mock()
        else:
            self.use_mock = use_mock
        logger.info(f"CompanyAPIAdapter initialized (use_mock={self.use_mock})")

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

    # ── 검색어 정규화: 일반 명사 제거 ──
    _GENERIC_SUFFIXES = ["물품", "용역", "공사", "구매", "납품", "조달", "설치", "제품", "장비"]

    def _normalize_search_query(self, item_name: str) -> str:
        """Router가 'LED 물품' 처럼 일반 명사를 포함하는 경우 제거.
        'LED 물품' → 'LED', 'LED' → 'LED' (변경 없음)"""
        import re
        query = item_name.strip()
        for suffix in self._GENERIC_SUFFIXES:
            query = re.sub(rf'\s*{re.escape(suffix)}\s*', ' ', query)
        query = query.strip()
        # 정규화 후 비어버리면 원본 유지
        return query if query else item_name.strip()

    def _live_search(self, item_name: str, location: str) -> CompanyCandidateResult:
        """실제 모니터링 시스템 API 호출 (Fail-Closed 보장).

        app/company_api.search_by_product()는 내부적으로
        GET {BASE_URL}/api/chatbot/company/product-search?product_name={item_name}
        을 호출한다. location 파라미터는 API에서 지원하지 않으므로
        결과를 후처리로 필터링한다.

        에러 유형별 분리:
        - requests.exceptions.Timeout → error_type="timeout"
        - requests.exceptions.ConnectionError → error_type="connection"
        - API 응답 실패 (company_search_status=="failed") → error_type="api_error"
        - 응답 파싱 실패 → error_type="parse_error"
        - 기타 예외 → error_type="unknown"
        """
        import requests as req_lib

        try:
            from app.company_api import search_by_product

            search_query = self._normalize_search_query(item_name)
            logger.info(f"Company API 검색어 정규화: '{item_name}' → '{search_query}'")
            raw = search_by_product(search_query)

            # ── API 레벨 실패 ──
            if raw.get("company_search_status") == "failed":
                error_msg = raw.get("error", "API 응답 실패")
                logger.warning(f"Company API 응답 실패: {error_msg} (query={item_name})")
                return CompanyCandidateResult(
                    status="failed",
                    error=error_msg,
                    error_type="api_error",
                    search_query=f"품목: {item_name}",
                    search_location=location
                )

            # ── 응답 파싱 ──
            candidates_raw = raw.get("candidates", [])
            if not isinstance(candidates_raw, list):
                logger.warning(f"Company API 응답 형식 오류: candidates가 list가 아님 (query={item_name})")
                return CompanyCandidateResult(
                    status="failed",
                    error="API 응답 형식 오류: candidates가 list가 아닙니다.",
                    error_type="parse_error",
                    search_query=f"품목: {item_name}",
                    search_location=location
                )

            # ── malformed row 제거 (dict가 아닌 원소 방어) ──
            malformed_count = len([c for c in candidates_raw if not isinstance(c, dict)])
            if malformed_count:
                logger.warning(f"Malformed candidate rows skipped: {malformed_count}건 (query={item_name})")
            candidates_raw = [c for c in candidates_raw if isinstance(c, dict)]

            # ── location 후처리 필터링 (None 안전) ──
            if location:
                candidates_raw = [
                    c for c in candidates_raw
                    if location in str(c.get("location") or "")
                ]

            if not candidates_raw:
                return CompanyCandidateResult(
                    status="empty",
                    total_found=0,
                    search_query=f"품목: {item_name}",
                    search_location=location
                )

            # ── 정상 변환 (방어적 정규화) ──
            rows = []
            for c in candidates_raw:
                if not isinstance(c, dict):
                    continue
                name = _as_str(c.get("company_name"))
                # 마스킹: 이름 앞 3자만 표시
                masked = name[:3] + "***" if len(name) >= 3 else name + "***"
                rows.append(CompanyCandidateRow(
                    company_id=_as_str(c.get("company_id")) or "unknown",
                    company_name_masked=masked,
                    location=_as_str(c.get("location")) or location,
                    business_type=", ".join(_as_list(c.get("license_or_business_type"))),
                    main_products=_as_list(c.get("main_products")),
                    display_status="검토 후보",
                    legal_eligibility_status="확인 필요"
                ))

            logger.info(f"Company API 조회 성공: {len(rows)}건 (query={item_name}, location={location})")
            return CompanyCandidateResult(
                status="success",
                candidates=rows[:10],
                total_found=len(candidates_raw),
                search_query=f"품목: {item_name}",
                search_location=location
            )

        except req_lib.exceptions.Timeout as e:
            logger.error(f"Company API 타임아웃: {e} (query={item_name})")
            return CompanyCandidateResult(
                status="failed",
                error=f"업체 조회 API 타임아웃: {str(e)}",
                error_type="timeout",
                search_query=f"품목: {item_name}",
                search_location=location
            )
        except req_lib.exceptions.ConnectionError as e:
            logger.error(f"Company API 연결 실패: {e} (query={item_name})")
            return CompanyCandidateResult(
                status="failed",
                error=f"업체 조회 API 연결 실패: {str(e)}",
                error_type="connection",
                search_query=f"품목: {item_name}",
                search_location=location
            )
        except ImportError as e:
            logger.error(f"company_api 모듈 임포트 실패: {e}")
            return CompanyCandidateResult(
                status="failed",
                error=f"company_api 모듈 로드 실패: {str(e)}",
                error_type="unknown",
                search_query=f"품목: {item_name}",
                search_location=location
            )
        except Exception as e:
            logger.error(f"Company API 호출 중 예기치 않은 오류: {e} (query={item_name})")
            return CompanyCandidateResult(
                status="failed",
                error=f"Company API 호출 실패: {str(e)}",
                error_type="unknown",
                search_query=f"품목: {item_name}",
                search_location=location
            )
