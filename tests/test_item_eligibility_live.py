"""
Phase 11.2: Item Eligibility Live API 테스트

모니터링 시스템 API를 통한 품목 적격성 실시간 조회가
정상 동작하고, 실패 시 Fail-Closed 되는지 검증한다.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.runtime.item_eligibility_adapter import (
    ItemEligibilityAdapter,
    ItemEligibilityResult,
    _default_use_mock,
)
from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest


# ─── Mock API 응답 헬퍼 ───
def _mock_certified_response(items=None):
    if items is None:
        items = [{"product_name": "CCTV", "certification_type": "NEP", "company_name": "테스트기업", "status": "valid"}]
    return {"candidates": items, "company_search_status": "success"}

def _mock_innovation_response(items=None):
    if items is None:
        items = []
    return {"candidates": items, "company_search_status": "success"}

def _mock_excellent_response(items=None):
    if items is None:
        items = [{"product_name": "CCTV 카메라", "company_name": "우수기업", "status": "active"}]
    return {"candidates": items, "company_search_status": "success"}

def _mock_shopping_response(items=None):
    if items is None:
        items = [{"product_name": "영상감시장치", "contract_status": "active", "company_name": "MAS업체"}]
    return {"candidates": items, "company_search_status": "success"}

def _mock_empty_response():
    return {"candidates": [], "company_search_status": "success"}

def _mock_failed_response():
    return {"candidates": [], "company_search_status": "failed", "error": "API Error"}

def _mock_detail_response():
    return {
        "company_search_status": "success",
        "tech_products": [
            {"product_name": "CCTV 카메라", "certification_status": "valid"}
        ],
        "general_certifications": [
            {"certification_name": "KS 인증"}
        ]
    }


class TestEnvVariableControl(unittest.TestCase):
    """USE_MOCK_ITEM_ELIGIBILITY 환경변수 제어 테스트."""

    def test_default_is_mock(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("USE_MOCK_ITEM_ELIGIBILITY", None)
            self.assertTrue(_default_use_mock())

    def test_env_false_returns_live(self):
        with patch.dict(os.environ, {"USE_MOCK_ITEM_ELIGIBILITY": "false"}):
            self.assertFalse(_default_use_mock())

    def test_env_true_returns_mock(self):
        with patch.dict(os.environ, {"USE_MOCK_ITEM_ELIGIBILITY": "true"}):
            self.assertTrue(_default_use_mock())

    def test_adapter_uses_env(self):
        with patch.dict(os.environ, {"USE_MOCK_ITEM_ELIGIBILITY": "false"}):
            adapter = ItemEligibilityAdapter(use_mock=None)
            self.assertFalse(adapter.use_mock)

    def test_adapter_explicit_override(self):
        with patch.dict(os.environ, {"USE_MOCK_ITEM_ELIGIBILITY": "false"}):
            adapter = ItemEligibilityAdapter(use_mock=True)
            self.assertTrue(adapter.use_mock)


class TestLiveAPIResolve(unittest.TestCase):
    """API 실시간 조회 정상 동작 검증."""

    @patch("app.company_api.search_certified_product", return_value=_mock_certified_response())
    @patch("app.company_api.search_innovation_product", return_value=_mock_innovation_response())
    @patch("app.company_api.search_excellent_procurement_product", return_value=_mock_excellent_response())
    @patch("app.company_api.search_shopping_mall_product", return_value=_mock_shopping_response())
    def test_resolve_with_all_api_results(self, mock_shop, mock_exc, mock_inno, mock_cert):
        """4종 API 모두 결과가 있을 때 resolved 반환."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "resolved")
        self.assertTrue(result.context.detail_item_resolved)
        self.assertIsNone(result.context.is_sme_competition_product)  # Live 모드에서는 알 수 없음
        self.assertIsNone(result.context.direct_production_required)  # Live 모드에서는 알 수 없음
        self.assertEqual(result.context.data_source, "live_api")
        self.assertIsNotNone(result.context.certified_products)
        self.assertIsNotNone(result.context.excellent_procurement_products)
        self.assertIsNotNone(result.context.shopping_mall_products)

    @patch("app.company_api.search_certified_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_innovation_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_excellent_procurement_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_shopping_mall_product", return_value=_mock_empty_response())
    def test_resolve_no_results(self, mock_shop, mock_exc, mock_inno, mock_cert):
        """모든 API에서 결과 없으면 not_found."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="존재하지않는품목", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "not_found")
        self.assertFalse(result.context.detail_item_resolved)

    @patch("app.company_api.search_certified_product", return_value=_mock_certified_response())
    @patch("app.company_api.search_innovation_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_excellent_procurement_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_shopping_mall_product", return_value=_mock_empty_response())
    def test_resolve_certified_only(self, mock_shop, mock_exc, mock_inno, mock_cert):
        """인증제품만 있을 때 직생확인 필요 표시."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "resolved")
        self.assertIsNone(result.context.direct_production_required)
        self.assertIsNone(result.context.is_sme_competition_product)

    @patch("app.company_api.search_certified_product", return_value=_mock_certified_response())
    @patch("app.company_api.search_innovation_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_excellent_procurement_product", return_value=_mock_empty_response())
    @patch("app.company_api.search_shopping_mall_product", return_value=_mock_empty_response())
    @patch("app.company_api.get_company_detail", return_value=_mock_detail_response())
    def test_resolve_with_company_id(self, mock_detail, mock_shop, mock_exc, mock_inno, mock_cert):
        """company_id가 있으면 상세 API도 호출하여 인증 상태 확인."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="CCTV 카메라", detail_item_code=None, company_id="C-12345")

        self.assertEqual(result.resolver_status, "resolved")
        self.assertEqual(result.context.company_cert_status, "valid")
        self.assertEqual(result.context.eligibility_status, "cert_verified_candidate")


class TestLiveAPIFailClosed(unittest.TestCase):
    """API 실패 시 Fail-Closed 동작 검증."""

    @patch("app.company_api.search_shopping_mall_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_excellent_procurement_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_innovation_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_certified_product",
           side_effect=ConnectionError("refused"))
    def test_connection_error_returns_data_unavailable(self, *mocks):
        """4종 API 모두 ConnectionError 시 data_unavailable."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "data_unavailable")
        self.assertEqual(result.context.data_source, "data_unavailable")
        self.assertIn("불가", result.context.procurement_support_message)

    @patch("app.company_api.search_shopping_mall_product",
           side_effect=TimeoutError("timed out"))
    @patch("app.company_api.search_excellent_procurement_product",
           side_effect=TimeoutError("timed out"))
    @patch("app.company_api.search_innovation_product",
           side_effect=TimeoutError("timed out"))
    @patch("app.company_api.search_certified_product",
           side_effect=TimeoutError("timed out"))
    def test_timeout_returns_data_unavailable(self, *mocks):
        """4종 API 모두 Timeout 시 data_unavailable."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="모니터", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "data_unavailable")

    @patch("app.company_api.search_certified_product", return_value=_mock_failed_response())
    @patch("app.company_api.search_innovation_product", return_value=_mock_failed_response())
    @patch("app.company_api.search_excellent_procurement_product", return_value=_mock_failed_response())
    @patch("app.company_api.search_shopping_mall_product", return_value=_mock_failed_response())
    def test_all_api_failed_returns_data_unavailable(self, mock_shop, mock_exc, mock_inno, mock_cert):
        """모든 API가 failed 상태 반환 시 data_unavailable."""
        adapter = ItemEligibilityAdapter(use_mock=False)
        result = adapter.resolve(item_name="프린터", detail_item_code=None, company_id=None)

        self.assertEqual(result.resolver_status, "data_unavailable")

    def test_partial_api_failure_still_works(self):
        """일부 API 실패해도 나머지 결과가 있으면 판별(resolved)."""
        import requests
        adapter = ItemEligibilityAdapter(use_mock=False)

        with patch("app.company_api.search_certified_product",
                   side_effect=requests.exceptions.ConnectionError("refused")):
            with patch("app.company_api.search_innovation_product",
                       return_value=_mock_empty_response()):
                with patch("app.company_api.search_excellent_procurement_product",
                           return_value=_mock_excellent_response()):
                    with patch("app.company_api.search_shopping_mall_product",
                               return_value=_mock_empty_response()):
                        result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)

                        # certified는 실패했지만 excellent 결과로 resolved
                        self.assertEqual(result.resolver_status, "resolved")
                        self.assertIsNotNone(result.context.excellent_procurement_products)

    def test_partial_api_failure_with_no_results(self):
        """일부 API 실패하고 나머지 결과도 없으면 data_unavailable 반환."""
        import requests
        adapter = ItemEligibilityAdapter(use_mock=False)

        with patch("app.company_api.search_certified_product",
                   side_effect=requests.exceptions.ConnectionError("refused")):
            with patch("app.company_api.search_innovation_product",
                       return_value=_mock_empty_response()):
                with patch("app.company_api.search_excellent_procurement_product",
                           return_value=_mock_empty_response()):
                    with patch("app.company_api.search_shopping_mall_product",
                               return_value=_mock_empty_response()):
                        result = adapter.resolve(item_name="책상", detail_item_code=None, company_id=None)

                        # 일부가 실패했고 결과가 없으면 부분적으로 알 수 없으므로 data_unavailable
                        self.assertEqual(result.resolver_status, "data_unavailable")

    def test_partial_graceful_failure_with_no_results(self):
        """1개 API는 graceful failed, 나머지는 empty일 때 data_unavailable 반환."""
        adapter = ItemEligibilityAdapter(use_mock=False)

        with patch("app.company_api.search_certified_product",
                   return_value=_mock_failed_response()):
            with patch("app.company_api.search_innovation_product",
                       return_value=_mock_empty_response()):
                with patch("app.company_api.search_excellent_procurement_product",
                           return_value=_mock_empty_response()):
                    with patch("app.company_api.search_shopping_mall_product",
                               return_value=_mock_empty_response()):
                        result = adapter.resolve(item_name="책상", detail_item_code=None, company_id=None)

                        # 일부가 failed 상태이고 결과가 없으면 data_unavailable
                        self.assertEqual(result.resolver_status, "data_unavailable")


class TestMockModeBackwardCompat(unittest.TestCase):
    """Mock 모드 하위 호환성 검증."""

    def test_mock_mode_still_works(self):
        """Mock 모드가 기존과 동일하게 동작."""
        adapter = ItemEligibilityAdapter(use_mock=True)
        result = adapter.resolve(item_name="CCTV", detail_item_code=None, company_id=None)

        # Mock seed에 CCTV가 2건 있으므로 ambiguous
        self.assertEqual(result.resolver_status, "ambiguous")
        self.assertEqual(result.context.data_source, "mock")

    def test_mock_not_triggered(self):
        """item_name과 detail_item_code 둘 다 없으면 not_triggered."""
        adapter = ItemEligibilityAdapter(use_mock=True)
        result = adapter.resolve(item_name=None, detail_item_code=None, company_id=None)
        self.assertEqual(result.resolver_status, "not_triggered")


class TestOrchestratorIntegration(unittest.TestCase):
    """Orchestrator 파이프라인에서 Item Eligibility가 정상 동작하는지 검증."""

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "true", "USE_MOCK_ITEM_ELIGIBILITY": "true"})
    def test_pipeline_with_mock_eligibility(self):
        """Mock 모드에서 파이프라인 정상 동작."""
        request = ChatbotRuntimeRequest(
            user_query="CCTV 중기경쟁제품인지 알려줘",
            mock_gemini_response={
                "primary_intent": "item_eligibility",
                "confidence": 0.9,
                "slots": {"item_name": "CCTV", "item_eligibility_requested": True}
            },
            runtime_options={"use_mock_company_api": True}
        )
        response = run_chatbot_runtime(request)

        self.assertIn(response.runtime_status, ("success", "degraded"))
        self.assertIsNotNone(response.answer_output)
        ie_stage = [s for s in response.runtime_stages if s.stage_name == "item_eligibility"]
        self.assertTrue(len(ie_stage) > 0)

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "true", "USE_MOCK_ITEM_ELIGIBILITY": "false"})
    @patch("app.company_api.search_shopping_mall_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_excellent_procurement_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_innovation_product",
           side_effect=ConnectionError("refused"))
    @patch("app.company_api.search_certified_product",
           side_effect=ConnectionError("refused"))
    def test_pipeline_survives_eligibility_api_failure(self, *mocks):
        """Item Eligibility API 전체 실패 시에도 파이프라인이 죽지 않음."""
        request = ChatbotRuntimeRequest(
            user_query="CCTV 중기경쟁제품인지 알려줘",
            mock_gemini_response={
                "primary_intent": "item_eligibility",
                "confidence": 0.9,
                "slots": {"item_name": "CCTV", "item_eligibility_requested": True}
            },
            runtime_options={"use_mock_company_api": True}
        )
        response = run_chatbot_runtime(request)

        # 파이프라인은 살아있어야 함
        self.assertIsNotNone(response.answer_output)
        self.assertIsNotNone(response.answer_output.rendered_markdown)
        
        # Item Eligibility 단계가 정상 완료되었는지(NameError 없이 fallback 처리)
        ie_stage = next((s for s in response.runtime_stages if s.stage_name == "item_eligibility"), None)
        self.assertIsNotNone(ie_stage)
        self.assertIn(ie_stage.status, ("success", "failed"))
        
        # NameError가 발생하지 않았는지 검증
        self.assertFalse(any("NameError" in str(e) for e in response.errors))
        self.assertFalse(any("runtime_options" in str(e) for e in response.errors))


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 11.2: Item Eligibility Live API Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
