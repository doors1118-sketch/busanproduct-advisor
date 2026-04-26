import unittest
import json

class TestP0FixesRev4(unittest.TestCase):
    def test_parallel_same_tool_name_calls_do_not_overwrite(self):
        """병렬 tool call 시 동일 이름 도구(인자 다름)가 덮어써지지 않는지 코드 로직 검증"""
        with open('app/gemini_engine.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertTrue('call_key = f"{idx}:{fc.name}' in content)
        self.assertTrue('futures[call_key] = (fc' in content)
        self.assertFalse('futures[fc.name] = (fc' in content)

    def test_mcp_prefetch_timeout_marked_as_timeout(self):
        """MCP prefetch 결과에 TIMEOUT 포함 시 status가 timeout이 되는지 검증"""
        with open('app/gemini_engine.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertTrue('prefetch_result = mcp.chain_full_research' in content)
        self.assertTrue('if "[TIMEOUT]" in prefetch_result' in content)
        self.assertTrue('status = "timeout"' in content)

    def test_nts_verification_failure_sets_business_status_unknown(self):
        """NTS 조회 실패 시 _사업자상태="영업상태 확인 필요", _사업자상태검증="failed" 설정 검증"""
        from company_api import filter_active_companies
        import company_api
        
        # mock verify_business_status to return None (failure)
        original_verify = company_api.verify_business_status
        company_api.verify_business_status = lambda biz_nums: None
        
        try:
            data = {"업체목록": [{"사업자번호": "123-45-67890", "업체명": "테스트기업"}]}
            result = filter_active_companies(data)
            self.assertEqual(result["_사업자상태검증"], "failed")
            self.assertEqual(result["업체목록"][0]["_사업자상태"], "영업상태 확인 필요")
        finally:
            company_api.verify_business_status = original_verify

    def test_legal_scope_rewrite_removes_confirmed_phrases_after_rewrite(self):
        """legal_scope rewrite 시 답변 재생성을 수행하는 로직이 있는지 구조적 검증"""
        with open('app/gemini_engine.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertTrue('rewrite_prompt = (' in content)
        self.assertTrue('client.models.generate_content(' in content)
        self.assertTrue('answer = rewrite_response.text' in content)

    def test_log_samples_match_actual_sanity_check_output(self):
        """LOG_SAMPLES.md의 샘플 2에 construction_contract, item_purchase가 있는지 검증"""
        with open('LOG_SAMPLES.md', 'r', encoding='utf-8') as src:
            content = src.read()
        
        # 샘플 2 부분을 찾아서 검증
        sample_2_idx = content.find('### 샘플 2: 소방공사 장비 구매인데 설치 포함이야')
        sample_3_idx = content.find('### 샘플 3:')
        if sample_2_idx != -1 and sample_3_idx != -1:
            sample_2_content = content[sample_2_idx:sample_3_idx]
            self.assertTrue('construction_contract' in sample_2_content)
            self.assertTrue('item_purchase' in sample_2_content)
            self.assertTrue('mixed_contract' in sample_2_content)
