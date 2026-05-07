"""
Phase 11: Company API Fail-Closed 테스트

Company API가 실패(타임아웃, 연결 불가, API 오류 등)해도
전체 파이프라인이 중단되지 않고 안전하게 응답하는지 검증한다.
"""
import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.runtime.company_api_adapter import (
    CompanyAPIAdapter,
    CompanyCandidateResult,
    _default_use_mock,
)
from app.runtime.chatbot_orchestrator import (
    ChatbotRuntimeOrchestrator,
    run_chatbot_runtime,
    DISCLAIMER,
)
from app.runtime.runtime_schema import ChatbotRuntimeRequest


# ─── 공통 헬퍼 ───
def _make_mock_gemini_response(intent="candidate_search", item_name="컴퓨터", 
                                 candidate_lookup=True, amount=50000000):
    return {
        "primary_intent": intent,
        "confidence": 0.9,
        "slots": {
            "item_name": item_name,
            "contract_type": "물품",
            "amount": amount,
            "location": "부산",
            "candidate_lookup_requested": candidate_lookup,
        },
        "candidate_lookup_required": candidate_lookup,
    }


def _make_request(mock_gemini=None, use_mock_company_api=None, use_evidence=False):
    if mock_gemini is None:
        mock_gemini = _make_mock_gemini_response()
    opts = {}
    if use_mock_company_api is not None:
        opts["use_mock_company_api"] = use_mock_company_api
    if use_evidence:
        opts["use_evidence_builder"] = True
    return ChatbotRuntimeRequest(
        user_query="컴퓨터 납품 가능한 부산업체 추천해줘",
        mock_gemini_response=mock_gemini,
        runtime_options=opts if opts else None,
    )


class TestEnvironmentVariableControl(unittest.TestCase):
    """USE_MOCK_COMPANY_API 환경변수에 따른 Mock/Live 분기 테스트."""

    def test_default_is_mock_true(self):
        """환경변수 미설정 시 기본값은 Mock(True)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("USE_MOCK_COMPANY_API", None)
            result = _default_use_mock()
            self.assertTrue(result)

    def test_env_true_returns_mock(self):
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "true"}):
            self.assertTrue(_default_use_mock())

    def test_env_false_returns_live(self):
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"}):
            self.assertFalse(_default_use_mock())

    def test_env_TRUE_case_insensitive(self):
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "TRUE"}):
            self.assertTrue(_default_use_mock())

    def test_env_False_case_insensitive(self):
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "False"}):
            self.assertFalse(_default_use_mock())

    def test_adapter_uses_env_default(self):
        """CompanyAPIAdapter가 환경변수 기본값을 따르는지 검증."""
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"}):
            adapter = CompanyAPIAdapter()  # use_mock 미지정
            self.assertFalse(adapter.use_mock)

    def test_adapter_explicit_override(self):
        """명시적 use_mock 파라미터가 환경변수보다 우선하는지 검증."""
        with patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"}):
            adapter = CompanyAPIAdapter(use_mock=True)
            self.assertTrue(adapter.use_mock)


class TestCompanyAPIFailClosed(unittest.TestCase):
    """Company API 실패 시 Fail-Closed 동작 검증."""

    def test_connection_error_returns_failed(self):
        """ConnectionError 발생 시 status=failed, error_type=connection."""
        import requests
        adapter = CompanyAPIAdapter(use_mock=False)

        with patch("app.company_api.search_by_product", side_effect=requests.exceptions.ConnectionError("Connection refused")):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "컴퓨터"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_type, "connection")
            self.assertEqual(len(result.candidates), 0)

    def test_timeout_error_returns_failed(self):
        """Timeout 발생 시 status=failed, error_type=timeout."""
        import requests
        adapter = CompanyAPIAdapter(use_mock=False)

        with patch("app.company_api.search_by_product", side_effect=requests.exceptions.Timeout("Read timed out")):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "모니터"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_type, "timeout")

    def test_api_error_response_returns_failed(self):
        """API가 company_search_status=failed를 반환할 때."""
        adapter = CompanyAPIAdapter(use_mock=False)

        mock_response = {
            "company_search_status": "failed",
            "error": "Internal Server Error",
            "candidates": []
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "프린터"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_type, "api_error")

    def test_invalid_candidates_format_returns_parse_error(self):
        """candidates가 list가 아닐 때 parse_error."""
        adapter = CompanyAPIAdapter(use_mock=False)

        mock_response = {
            "company_search_status": "success",
            "candidates": "not_a_list"  # 잘못된 형식
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "책상"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error_type, "parse_error")

    def test_mock_search_always_succeeds(self):
        """Mock 모드에서는 항상 성공."""
        adapter = CompanyAPIAdapter(use_mock=True)

        router_result = MagicMock()
        router_result.candidate_lookup_required = True
        router_result.slots = MagicMock()
        router_result.slots.item_name = "컴퓨터"
        router_result.slots.location = "부산"

        result = adapter.resolve(router_result)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(result.candidates), 2)


class TestOrchestratorFailClosed(unittest.TestCase):
    """Orchestrator 전체 파이프라인이 Company API 실패 시에도 정상 응답하는지 검증."""

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "true"})
    def test_pipeline_with_mock_succeeds(self):
        """Mock 모드에서 전체 파이프라인 정상 동작."""
        request = _make_request(use_mock_company_api=True)
        response = run_chatbot_runtime(request)

        self.assertIn(response.runtime_status, ("success", "degraded"))
        self.assertIsNotNone(response.answer_output)
        self.assertIsNotNone(response.answer_output.rendered_markdown)

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"})
    def test_pipeline_survives_company_api_connection_error(self):
        """Company API 연결 실패 시에도 파이프라인이 죽지 않고 답변이 생성되는지 검증."""
        import requests

        with patch("app.company_api.search_by_product",
                   side_effect=requests.exceptions.ConnectionError("Connection refused")):
            request = _make_request(use_mock_company_api=False)
            response = run_chatbot_runtime(request)

            # 파이프라인은 살아있어야 함
            self.assertIsNotNone(response.answer_output)
            self.assertIsNotNone(response.answer_output.rendered_markdown)

            # 업체 조회 실패 안내가 rendered_markdown에 포함되어야 함
            self.assertIn("업체 조회", response.answer_output.rendered_markdown)

            # company_candidate_resolver stage는 failed
            company_stage = [s for s in response.runtime_stages if s.stage_name == "company_candidate_resolver"]
            self.assertTrue(len(company_stage) > 0)
            self.assertEqual(company_stage[0].status, "failed")

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"})
    def test_pipeline_survives_company_api_timeout(self):
        """Company API 타임아웃 시에도 파이프라인이 죽지 않고 답변이 생성되는지 검증."""
        import requests

        with patch("app.company_api.search_by_product",
                   side_effect=requests.exceptions.Timeout("Read timed out")):
            request = _make_request(use_mock_company_api=False)
            response = run_chatbot_runtime(request)

            self.assertIsNotNone(response.answer_output)
            self.assertIn("업체 조회", response.answer_output.rendered_markdown)
            self.assertIn("다시 시도", response.answer_output.rendered_markdown)

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "true"})
    def test_no_candidate_lookup_skips_company_api(self):
        """candidate_lookup_required=False면 Company API를 호출하지 않음."""
        mock_gemini = _make_mock_gemini_response(
            intent="legal_explanation",
            item_name=None,
            candidate_lookup=False
        )
        # 업체 검색 키워드가 없는 순수 법적 질의
        request = ChatbotRuntimeRequest(
            user_query="지역제한 입찰 기준이 뭐야",
            mock_gemini_response=mock_gemini,
            runtime_options={"use_mock_company_api": True},
        )
        response = run_chatbot_runtime(request)

        company_stage = [s for s in response.runtime_stages if s.stage_name == "company_candidate_resolver"]
        self.assertTrue(len(company_stage) > 0)
        self.assertEqual(company_stage[0].status, "skipped")


class TestDefensiveParsing(unittest.TestCase):
    """P1: API 응답 필드가 None/문자열/타입 불일치일 때 오류 없이 정상 변환하는지 검증."""

    def test_company_name_none(self):
        """company_name=None이면 빈 문자열로 처리, 마스킹 오류 없음."""
        adapter = CompanyAPIAdapter(use_mock=False)
        mock_response = {
            "company_search_status": "success",
            "candidates": [
                {"company_id": "x1", "company_name": None, "location": "부산", 
                 "license_or_business_type": ["제조업"], "main_products": ["CCTV"]}
            ]
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "CCTV"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.candidates[0].company_name_masked, "***")

    def test_license_or_business_type_string(self):
        """license_or_business_type가 문자열이면 글자 단위 join 없이 [문자열]로 처리."""
        adapter = CompanyAPIAdapter(use_mock=False)
        mock_response = {
            "company_search_status": "success",
            "candidates": [
                {"company_id": "x2", "company_name": "테스트업체", "location": "부산",
                 "license_or_business_type": "제조업",  # 문자열!
                 "main_products": ["모니터"]}
            ]
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "모니터"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)
            self.assertEqual(result.status, "success")
            # "제조업"이 글자 단위("제, 조, 업")가 아니라 통째로 들어가야 함
            self.assertEqual(result.candidates[0].business_type, "제조업")

    def test_main_products_none(self):
        """main_products=None이면 빈 리스트로 처리."""
        adapter = CompanyAPIAdapter(use_mock=False)
        mock_response = {
            "company_search_status": "success",
            "candidates": [
                {"company_id": "x3", "company_name": "가나다라", "location": "부산",
                 "license_or_business_type": ["도매업"],
                 "main_products": None}  # None!
            ]
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "프린터"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)
            self.assertEqual(result.status, "success")
            self.assertEqual(result.candidates[0].main_products, [])

    def test_location_none_in_candidate(self):
        """candidate의 location=None이면 TypeError 없이 필터링 통과."""
        adapter = CompanyAPIAdapter(use_mock=False)
        mock_response = {
            "company_search_status": "success",
            "candidates": [
                {"company_id": "x4", "company_name": "마바사아", "location": None,
                 "license_or_business_type": [], "main_products": []},
                {"company_id": "x5", "company_name": "자차카타", "location": "부산 해운대구",
                 "license_or_business_type": [], "main_products": []}
            ]
        }
        with patch("app.company_api.search_by_product", return_value=mock_response):
            router_result = MagicMock()
            router_result.candidate_lookup_required = True
            router_result.slots = MagicMock()
            router_result.slots.item_name = "책상"
            router_result.slots.location = "부산"

            result = adapter.resolve(router_result)
            # location=None인 건은 필터링에서 제거, "부산 해운대구"만 남아야 함
            self.assertEqual(result.status, "success")
            self.assertEqual(len(result.candidates), 1)
            self.assertEqual(result.candidates[0].company_id, "x5")


class TestFailNoticeNotForbidden(unittest.TestCase):
    """P1: Company API 실패 안내 문구가 금지어 스캔에 걸리지 않는지 검증."""

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"})
    def test_connection_fail_notice_passes_forbidden_scan(self):
        """연결 실패 안내 문구에 금지 표현이 포함되지 않아야 함."""
        import requests
        from app.answer_builder.answer_type_router import FORBIDDEN_PHRASES

        with patch("app.company_api.search_by_product",
                   side_effect=requests.exceptions.ConnectionError("refused")):
            request = _make_request(use_mock_company_api=False)
            response = run_chatbot_runtime(request)

            md = response.answer_output.rendered_markdown
            for phrase in FORBIDDEN_PHRASES:
                self.assertNotIn(phrase, md,
                    f"실패 안내 문구에 금지 표현 '{phrase}'가 포함됨")
            self.assertTrue(response.answer_output.forbidden_phrase_scan_passed)

    @patch.dict(os.environ, {"USE_MOCK_COMPANY_API": "false"})
    def test_timeout_fail_notice_passes_forbidden_scan(self):
        """타임아웃 안내 문구에 금지 표현이 포함되지 않아야 함."""
        import requests
        from app.answer_builder.answer_type_router import FORBIDDEN_PHRASES

        with patch("app.company_api.search_by_product",
                   side_effect=requests.exceptions.Timeout("timed out")):
            request = _make_request(use_mock_company_api=False)
            response = run_chatbot_runtime(request)

            md = response.answer_output.rendered_markdown
            for phrase in FORBIDDEN_PHRASES:
                self.assertNotIn(phrase, md,
                    f"실패 안내 문구에 금지 표현 '{phrase}'가 포함됨")
            self.assertTrue(response.answer_output.forbidden_phrase_scan_passed)


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 11: Company API Fail-Closed Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
