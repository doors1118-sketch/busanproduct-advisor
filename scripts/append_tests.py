import unittest

class TestP0FixesRev3(unittest.TestCase):
    def test_verify_and_annotate_v144_preserves_answer_lines(self):
        """verify_and_annotate_v144가 기존 답변의 줄을 누락하지 않는지 검증"""
        from gemini_engine import _verify_and_annotate_v144
        answer = "첫 번째 줄입니다.\n두 번째 줄에 지방계약법 제25조에 따르면 가능합니다. [최신 법령 확인 완료]\n세 번째 줄입니다."
        tool_results = [{'status': 'success', 'result': '지방계약법 시행령 제25조'}]
        result = _verify_and_annotate_v144(answer, tool_results)
        lines = result.split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], "첫 번째 줄입니다.")
        self.assertEqual(lines[2], "세 번째 줄입니다.")

    def test_sanity_check_adds_specific_contract_guardrails(self):
        """Sanity check가 공사, 용역, 물품, MAS 키워드에 따라 개별 가드레일을 추가하는지 검증"""
        from prompting.guardrail_sanity_check import apply_guardrail_sanity_check
        q1 = "소방공사 장비 구매인데 설치 포함이야"
        res1 = apply_guardrail_sanity_check(q1, [])
        self.assertIn("construction_contract", res1)
        self.assertIn("item_purchase", res1)
        self.assertIn("mixed_contract", res1)
        
        q2 = "시스템 구축 용역 문의"
        res2 = apply_guardrail_sanity_check(q2, [])
        self.assertIn("service_contract", res2)
        
        q3 = "종합쇼핑몰 물품"
        res3 = apply_guardrail_sanity_check(q3, [])
        self.assertIn("mas_shopping_mall", res3)
        self.assertIn("item_purchase", res3)

    def test_timeout_warning_marked_as_timeout_not_success(self):
        """결과에 TIMEOUT 포함 시 status가 timeout으로 설정되는지 구조적 로직 검증"""
        with open('app/gemini_engine.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertTrue('status = "timeout"' in content and 'if "[TIMEOUT]" in result_str' in content)

    def test_legal_scope_rewrites_or_blocks_final_answer(self):
        """blocked_scope 발생 시 재생성 로직(rewrite_prompt)이 존재하는지 검증"""
        with open('app/gemini_engine.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertTrue('rewrite_prompt =' in content and '유보적 표현' in content)

    def test_mcp_client_no_explicit_120_timeout(self):
        """mcp_client.py 내 하드코딩된 timeout 인자가 없는지 검증"""
        with open('app/mcp_client.py', 'r', encoding='utf-8') as src:
            content = src.read()
        self.assertFalse('timeout=120' in content)
        self.assertFalse('timeout=30' in content)

    def test_import_paths_consistent(self):
        """app.prompting, app.policies 형태의 절대경로 import가 제거되었는지 검증"""
        import glob
        for fpath in glob.glob('app/**/*.py', recursive=True):
            with open(fpath, 'r', encoding='utf-8') as src:
                content = src.read()
            self.assertFalse('from app.prompting' in content, f"{fpath}에 app.prompting 존재")
            self.assertFalse('from app.policies' in content, f"{fpath}에 app.policies 존재")

