"""
Phase 11.2: Item Eligibility Adapter (API 실시간 조회 전환)

item_name을 바탕으로 모니터링 시스템 API를 호출하여
중기경쟁제품, 인증제품, 혁신제품, 우수조달물품, MAS 등록 여부 등
품목 적격성을 실시간으로 판별하는 어댑터입니다.

원칙:
- USE_MOCK_ITEM_ELIGIBILITY=true (기본값): JSON 파일 로드 (하위 호환)
- USE_MOCK_ITEM_ELIGIBILITY=false: 모니터링 시스템 API 실시간 호출
- API 실패 시 Fail-Closed (data_unavailable 반환)
- PII 원천 차단: company_id만 사용, 사업자번호 미사용
"""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ── 방어적 타입 정규화 헬퍼 ──
def _as_str(value) -> str:
    return "" if value is None else str(value)

def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [str(value)]


# ── 환경변수 기반 기본값 ──
def _default_use_mock() -> bool:
    val = os.getenv("USE_MOCK_ITEM_ELIGIBILITY", "true").strip().lower()
    return val != "false"


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
    # ── API 실시간 조회 추가 필드 ──
    certified_products: Optional[List[Dict[str, str]]] = None
    innovation_products: Optional[List[Dict[str, str]]] = None
    excellent_procurement_products: Optional[List[Dict[str, str]]] = None
    shopping_mall_products: Optional[List[Dict[str, str]]] = None
    data_source: str = "mock"  # mock, live_api, data_unavailable


def normalize_item_name(s: str) -> str:
    if not s:
        return ""
    return s.lower().replace(" ", "").replace("-", "").strip()


class ItemEligibilityResult(BaseModel):
    resolver_status: str  # "resolved", "ambiguous", "not_found", "not_triggered", "data_unavailable"
    context: Optional[ItemEligibilityContext] = None


class ItemEligibilityAdapter:
    def __init__(self, data_path: Optional[str] = None, use_mock: Optional[bool] = None):
        if use_mock is None:
            self.use_mock = _default_use_mock()
        else:
            self.use_mock = use_mock

        self.data: Dict[str, Any] = {}
        if self.use_mock:
            if not data_path:
                # app/runtime/item_eligibility_adapter.py → app/ → project_root/
                runtime_dir = os.path.dirname(os.path.abspath(__file__))  # app/runtime/
                app_dir = os.path.dirname(runtime_dir)                   # app/
                data_path = os.path.join(app_dir, "data", "item_eligibility_mock_seed_data.json")

            if os.path.exists(data_path):
                with open(data_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            else:
                logger.warning(f"[ItemEligibilityAdapter] Mock seed data not found at {data_path}")

        logger.info(f"ItemEligibilityAdapter initialized (use_mock={self.use_mock})")

    def resolve(self, item_name: Optional[str], detail_item_code: Optional[str],
                company_id: Optional[str]) -> ItemEligibilityResult:
        if not item_name and not detail_item_code:
            return ItemEligibilityResult(resolver_status="not_triggered")

        if self.use_mock:
            return self._mock_resolve(item_name, detail_item_code, company_id)
        else:
            return self._live_resolve(item_name, detail_item_code, company_id)

    # ══════════════════════════════════════════════
    # Mock 모드 (기존 JSON 파일 기반, 하위 호환)
    # ══════════════════════════════════════════════
    def _mock_resolve(self, item_name: Optional[str], detail_item_code: Optional[str],
                      company_id: Optional[str]) -> ItemEligibilityResult:
        if not self.data:
            return ItemEligibilityResult(
                resolver_status="data_unavailable",
                context=ItemEligibilityContext(
                    detail_item_name=item_name or detail_item_code,
                    eligibility_status="data_unavailable",
                    procurement_support_message="품목 적격성 DB 조회가 불가합니다.",
                    legal_conclusion_allowed=False,
                    data_source="mock"
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

            matches = exact_matches if exact_matches else contains_matches
            matches.sort(key=lambda x: x.get("match_confidence", 0.0), reverse=True)

            if not matches:
                return ItemEligibilityResult(
                    resolver_status="not_found",
                    context=ItemEligibilityContext(
                        detail_item_name=item_name,
                        eligibility_status="not_found",
                        data_source="mock"
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
                        procurement_support_message="여러 세부품명 후보가 발견되었습니다.",
                        data_source="mock"
                    )
                )
            else:
                detail_item_code = matches[0]["detail_item_code"]

        # 2. detail_item_code 확정 시 데이터 조회
        if detail_item_code:
            master = self.data.get("procurement_item_master", [])
            item_info = next((i for i in master if i["detail_item_code"] == detail_item_code), None)
            item_display_name = item_info["detail_item_name"] if item_info else item_name

            sme_list = self.data.get("sme_competition_product_item", [])
            sme_info = next((s for s in sme_list if s["detail_item_code"] == detail_item_code), None)
            is_sme = sme_info["is_sme_competition_product"] if sme_info else False

            dp_list = self.data.get("direct_production_requirement", [])
            dp_info = next((d for d in dp_list if d["detail_item_code"] == detail_item_code), None)
            is_dp = dp_info["direct_production_required"] if dp_info else False

            company_cert_status = None
            if company_id:
                cert_list = self.data.get("company_direct_production_cert_mapping", [])
                cert_info = next((c for c in cert_list
                                  if c["detail_item_code"] == detail_item_code and c["company_id"] == company_id), None)
                if cert_info:
                    company_cert_status = cert_info.get("cert_status")
                else:
                    company_cert_status = "not_found"

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
                    legal_conclusion_allowed=False,
                    data_source="mock"
                )
            )

        return ItemEligibilityResult(resolver_status="not_triggered")

    # ══════════════════════════════════════════════
    # Live API 모드 (모니터링 시스템 API 실시간 호출)
    # ══════════════════════════════════════════════
    def _live_resolve(self, item_name: Optional[str], detail_item_code: Optional[str],
                      company_id: Optional[str]) -> ItemEligibilityResult:
        """모니터링 시스템 API를 호출하여 품목 적격성을 실시간 판별.

        호출 API:
        1. /api/chatbot/product/certified-search → 인증제품 (NEP/NET/KS 등)
        2. /api/chatbot/product/innovation-search → 혁신제품
        3. /api/chatbot/product/excellent-procurement-search → 우수조달물품
        4. /api/chatbot/shopping-mall/product-search → MAS/종합쇼핑몰
        5. /api/chatbot/company/detail → 업체 인증 상태 (company_id 있을 때)
        """
        import requests as req_lib

        search_name = item_name or detail_item_code
        if not search_name:
            return ItemEligibilityResult(resolver_status="not_triggered")

        try:
            from app.company_api import (
                search_certified_product,
                search_innovation_product,
                search_excellent_procurement_product,
                search_shopping_mall_product,
                get_company_detail,
            )

            # ── 4종 API 조회 (개별 실패 허용) ──
            api_failures = []
            certified_raw = self._safe_api_call(search_certified_product, search_name, api_failures)
            innovation_raw = self._safe_api_call(search_innovation_product, search_name, api_failures)
            excellent_raw = self._safe_api_call(search_excellent_procurement_product, search_name, api_failures)
            shopping_raw = self._safe_api_call(search_shopping_mall_product, search_name, api_failures)

            # 4종 모두 연결 실패 → data_unavailable
            if len(api_failures) == 4:
                logger.error(f"Item Eligibility API 4종 전체 실패 (query={search_name})")
                return self._fail_closed_result(search_name, "4종 API 전체 연결 실패")

            # ── 응답 파싱 ──
            certified_items = self._extract_items(certified_raw, "인증제품")
            innovation_items = self._extract_items(innovation_raw, "혁신제품")
            excellent_items = self._extract_items(excellent_raw, "우수조달물품")
            shopping_items = self._extract_items(shopping_raw, "쇼핑몰상품")

            has_any = bool(certified_items or innovation_items or excellent_items or shopping_items)

            # ── 적격성 판별 ──
            # 라이브 API 조회의 한계: MAS/쇼핑몰이 중기경쟁제품을 의미하지 않으며,
            # 인증제품이 직접생산확인 대상을 의미하지 않음. 따라서 Live 모드에서는 None(불명)으로 설정
            is_sme = None
            direct_production_required = None

            has_shopping = bool(shopping_items)
            has_certified = bool(certified_items)
            has_innovation = bool(innovation_items)
            has_excellent = bool(excellent_items)
            
            # 모든 응답 중 'failed' 상태 개수 확인 (예외 발생은 아니지만 정상적인 조회가 아님)
            raw_responses = [certified_raw, innovation_raw, excellent_raw, shopping_raw]
            failed_status_count = sum(1 for r in raw_responses if r and r.get("company_search_status") == "failed")
            
            if failed_status_count == 4:
                logger.error(f"Item Eligibility API 4종 상태 모두 failed (query={search_name})")
                return self._fail_closed_result(search_name, "4종 API 전체 상태 failed")

            # ── 업체 인증 상태 확인 (company_id 있을 때) ──
            company_cert_status = None
            if company_id and has_any:
                detail_raw = self._safe_api_call(get_company_detail, company_id)
                if detail_raw and detail_raw.get("company_search_status") != "failed":
                    company_cert_status = self._extract_company_cert_status(
                        detail_raw, search_name
                    )
                else:
                    company_cert_status = "not_found"

            # ── eligibility_status 결정 ──
            if not has_any:
                if api_failures or failed_status_count > 0:
                    eligibility_status = "data_unavailable"
                    resolver_status = "data_unavailable"
                    message = f"'{search_name}' 조회 중 일부 API 실패로 정확한 결과를 확인할 수 없습니다."
                else:
                    eligibility_status = "not_found"
                    resolver_status = "not_found"
                    message = f"'{search_name}'에 대한 인증/등록 정보가 조회되지 않았습니다."
            else:
                resolver_status = "resolved"
                if company_cert_status is None:
                    eligibility_status = "item_resolved_company_not_checked"
                elif company_cert_status == "not_found":
                    eligibility_status = "cert_not_found"
                elif company_cert_status == "expired":
                    eligibility_status = "cert_expired"
                elif company_cert_status in ("valid", "verified"):
                    eligibility_status = "cert_verified_candidate"
                else:
                    eligibility_status = "item_resolved_company_not_checked"

                # 안내 메시지 구성
                parts = []
                if has_certified:
                    parts.append(f"인증제품 {len(certified_items)}건")
                if has_innovation:
                    parts.append(f"혁신제품 {len(innovation_items)}건")
                if has_excellent:
                    parts.append(f"우수조달물품 {len(excellent_items)}건")
                if has_shopping:
                    parts.append(f"쇼핑몰 등록 {len(shopping_items)}건")
                message = f"'{search_name}' 조회 결과: " + ", ".join(parts)

            logger.info(f"Item Eligibility API 조회 완료: {message}")

            return ItemEligibilityResult(
                resolver_status=resolver_status,
                context=ItemEligibilityContext(
                    detail_item_resolved=has_any,
                    detail_item_name=search_name,
                    is_sme_competition_product=is_sme,
                    direct_production_required=direct_production_required,
                    company_cert_status=company_cert_status,
                    eligibility_status=eligibility_status,
                    procurement_support_message=message,
                    legal_conclusion_allowed=False,
                    certified_products=certified_items if certified_items else None,
                    innovation_products=innovation_items if innovation_items else None,
                    excellent_procurement_products=excellent_items if excellent_items else None,
                    shopping_mall_products=shopping_items if shopping_items else None,
                    data_source="live_api"
                )
            )

        except req_lib.exceptions.Timeout as e:
            logger.error(f"Item Eligibility API 타임아웃: {e} (query={search_name})")
            return self._fail_closed_result(search_name, f"API 타임아웃: {e}")
        except req_lib.exceptions.ConnectionError as e:
            logger.error(f"Item Eligibility API 연결 실패: {e} (query={search_name})")
            return self._fail_closed_result(search_name, f"API 연결 실패: {e}")
        except ImportError as e:
            logger.error(f"company_api 모듈 임포트 실패: {e}")
            return self._fail_closed_result(search_name, f"모듈 로드 실패: {e}")
        except Exception as e:
            logger.error(f"Item Eligibility API 호출 중 예기치 않은 오류: {e} (query={search_name})")
            return self._fail_closed_result(search_name, f"API 호출 실패: {e}")

    def _safe_api_call(self, func, *args, api_failures: list = None) -> dict:
        """API 호출을 안전하게 수행. 개별 API 실패 시 빈 dict 반환."""
        # api_failures가 args 마지막에 list로 들어오는 경우 처리
        actual_args = args
        if args and isinstance(args[-1], list):
            api_failures = args[-1]
            actual_args = args[:-1]

        func_name = getattr(func, '__name__', str(func))
        try:
            result = func(*actual_args)
            if isinstance(result, dict):
                return result
            return {}
        except Exception as e:
            logger.warning(f"API 호출 실패 ({func_name}): {e}")
            if api_failures is not None:
                api_failures.append(func_name)
            return {}

    def _extract_items(self, raw: dict, label: str) -> List[Dict[str, str]]:
        """API 응답에서 items/candidates를 추출하여 간략화."""
        if not raw or raw.get("company_search_status") == "failed":
            return []

        # API마다 candidates, items, data 등 다양한 키 사용
        items = raw.get("candidates", raw.get("items", raw.get("data", [])))
        if not isinstance(items, list):
            return []

        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            result.append({
                "product_name": _as_str(item.get("product_name", item.get("item_name", item.get("상품명", "")))),
                "certification_type": _as_str(item.get("certification_type", item.get("인증유형", ""))),
                "company_name": _as_str(item.get("company_name", item.get("업체명", ""))),
                "status": _as_str(item.get("status", item.get("contract_status", ""))),
                "source": label
            })

        return result[:10]  # 최대 10건

    def _extract_company_cert_status(self, detail_raw: dict, item_name: str) -> str:
        """업체 상세 정보에서 해당 품목 인증 보유 여부를 판별."""
        # tech_products: 기술인증제품 (우수조달, 혁신 등)
        tech_products = _as_list(detail_raw.get("tech_products"))
        for tp in tech_products:
            if isinstance(tp, dict):
                pname = _as_str(tp.get("product_name", ""))
                if item_name.lower() in pname.lower():
                    cert_status = _as_str(tp.get("certification_status", ""))
                    if cert_status in ("valid", "active", "유효"):
                        return "valid"
                    elif cert_status in ("expired", "만료"):
                        return "expired"

        # general_certifications: 일반 품질인증
        gen_certs = _as_list(detail_raw.get("general_certifications"))
        for gc in gen_certs:
            if isinstance(gc, dict):
                cert_name = _as_str(gc.get("certification_name", ""))
                if item_name.lower() in cert_name.lower():
                    return "valid"

        return "not_found"

    def _fail_closed_result(self, search_name: str, error_msg: str) -> ItemEligibilityResult:
        """Fail-Closed: API 실패 시 안전한 결과 반환."""
        return ItemEligibilityResult(
            resolver_status="data_unavailable",
            context=ItemEligibilityContext(
                detail_item_name=search_name,
                eligibility_status="data_unavailable",
                procurement_support_message=f"품목 적격성 조회가 일시적으로 불가합니다. ({error_msg})",
                legal_conclusion_allowed=False,
                data_source="data_unavailable"
            )
        )
