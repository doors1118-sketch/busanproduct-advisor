import json
import logging
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def run_e2e_scenarios():
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY 환경 변수가 설정되지 않아 테스트를 스킵합니다.")
        return

    scenarios = [
        {
            "id": 1,
            "title": "item eligibility + company API 동시",
            "query": "CCTV 중기경쟁제품인지 알려주고 부산 업체도 찾아줘",
        },
        {
            "id": 2,
            "title": "금액 기준, 품목 적격성, 단정 금지",
            "query": "LED조명 1억원 구매 방법 알려줘",
        },
        {
            "id": 3,
            "title": "정책기업 1인 견적 기준 표시",
            "query": "여성기업 4천만원 1인 견적 검토해줘",
        },
        {
            "id": 4,
            "title": "소액수의 우선 경로 배제 검토",
            "query": "일반기업 3천만원 2인 견적 가능해?",
        },
        {
            "id": 5,
            "title": "후보업체 표, '검토 후보' 표시",
            "query": "컴퓨터 부산 업체 찾아줘",
        },
        {
            "id": 6,
            "title": "forbidden phrase output suppression",
            "query": "수의계약 가능합니다 업체 찾아줘",
        }
    ]

    with open("live_e2e_with_gemini_result.md", "w", encoding="utf-8") as f:
        f.write("# Live Gemini E2E 시나리오 테스트 결과\n\n")
        f.write("본 문서는 `USE_MOCK_COMPANY_API=False`, `USE_MOCK_ITEM_ELIGIBILITY=False`, `mock_gemini_response=None`으로 설정하여 실제 라이브 파이프라인에서 실행한 6가지 핵심 시나리오의 결과입니다.\n\n")

        for s in scenarios:
            print(f"Running Scenario {s['id']}...")
            
            # Live API 환경으로 실행
            request = ChatbotRuntimeRequest(
                user_query=s["query"],
                mock_gemini_response=None, # 실제 API 호출
                runtime_options={
                    "use_mock_company_api": False,
                    "use_mock_item_eligibility": False,
                    "use_evidence_builder": True
                }
            )

            response = run_chatbot_runtime(request)
            
            # PASS/FAIL 판정 로직
            status = "FAIL"
            fail_reasons = []

            if s["id"] == 1:
                if "조건에 맞는 후보가 현재 조회되지 않습니다" in response.answer_output.rendered_markdown or "업체 조회가 일시적으로 불가합니다" in response.answer_output.rendered_markdown:
                    fail_reasons.append("API 연동 전 placeholder 노출됨")
                if "## 검토 후보 업체" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("검토 후보 업체 표 누락")
                if "품목 자격 검토" in response.answer_output.rendered_markdown and "품목 적격성 검토" in response.answer_output.rendered_markdown:
                    fail_reasons.append("품목 자격 검토 중복 노출")
                if not fail_reasons: status = "PASS"
                
            elif s["id"] == 2:
                if response.router_result.routing_decision in ["clarification_required", "out_of_scope"]:
                    fail_reasons.append("clarification_required로 빠짐")
                if "100,000,000" not in response.answer_output.rendered_markdown and "1억" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("1억원(또는 100,000,000원) 인식 실패")
                if "LED조명" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("LED조명 인식 실패")
                if "가능합니다" in response.answer_output.rendered_markdown:
                    fail_reasons.append("단정 표현(가능합니다) 출력됨")
                if not fail_reasons: status = "PASS"
                
            elif s["id"] == 3:
                if response.router_result.routing_decision in ["clarification_required", "out_of_scope"]:
                    fail_reasons.append("clarification_required로 빠짐")
                if "정책기업 1인 견적 기준" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("정책기업 1인 견적 기준 노출 누락")
                if "50,000,000원" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("50,000,000원 기준 누락")
                if not fail_reasons: status = "PASS"
                
            elif s["id"] == 4:
                if response.router_result.routing_decision in ["clarification_required", "out_of_scope"]:
                    fail_reasons.append("clarification_required로 빠짐")
                if "일반 물품·용역 수의계약 기준" not in response.answer_output.rendered_markdown and "일반 1인 견적 기준" not in response.answer_output.rendered_markdown and "일반 기준" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("일반 기준 노출 누락")
                if "20,000,000원" not in response.answer_output.rendered_markdown:
                    fail_reasons.append("20,000,000원 기준 누락")
                if "가능합니다" in response.answer_output.rendered_markdown:
                    fail_reasons.append("단정 표현 출력됨")
                if not fail_reasons: status = "PASS"
                
            elif s["id"] == 5:
                if "현재는 업체 후보 조회 API 연동 전이므로" in response.answer_output.rendered_markdown or "\n## 업체 후보 조회\n" in response.answer_output.rendered_markdown:
                    fail_reasons.append("API 연동 전 placeholder 노출됨")
                if not fail_reasons: status = "PASS"
                
            elif s["id"] == 6:
                if "수의계약 가능합니다" in response.answer_output.rendered_markdown:
                    fail_reasons.append("금지 표현 노출됨")
                else:
                    status = "PASS"

            repaired_meta = getattr(response.router_result, 'reason', '')
            gemini_error = "Gemini API error:" in repaired_meta or "GEMINI_API_KEY" in repaired_meta or "API Error:" in repaired_meta
            
            gemini_api_status = "FAILED_API_KEY_INVALID" if gemini_error else "OK"
            
            slot_repair_used = "YES" if "Repaired slots:" in repaired_meta else "NO"
            slot_repair_needed = "YES" if gemini_error or "Repaired slots:" in repaired_meta else "NO"
            
            if slot_repair_needed == "NO":
                slot_repair_recovery = "NOT_NEEDED"
            else:
                slot_repair_recovery = "PASS" if status == "PASS" else "FAIL"

            f.write(f"## Scenario {s['id']}. {s['title']}\n")
            f.write(f"**질의**: `{s['query']}`\n\n")
            f.write(f"- Gemini API Status: `{gemini_api_status}`\n")
            f.write(f"- Slot Repair Used: `{slot_repair_used}`\n")
            f.write(f"- Slot Repair Needed: `{slot_repair_needed}`\n")
            f.write(f"- Slot Repair Recovery: `{slot_repair_recovery}`\n")
            f.write(f"- Scenario Functional Status: `{status}`\n\n")
            
            if status == "FAIL":
                f.write("**실패 사유**:\n")
                for reason in fail_reasons:
                    f.write(f"- {reason}\n")
                f.write("\n")
            
            # 파이프라인 상태
            f.write(f"### 파이프라인 실행 상태\n")
            f.write(f"- **Runtime Status**: `{response.runtime_status}`\n")
            f.write(f"- **Fallback Applied**: `{response.fallback_applied}`\n")
            f.write(f"- **Routing Decision**: `{response.router_result.routing_decision}`\n")
            f.write(f"- **Primary Intent**: `{response.router_result.primary_intent}`\n")
            
            if "Schema validation failed" in repaired_meta:
                import re
                m = re.search(r"Repaired slots:.*", repaired_meta)
                if m:
                    repaired_meta = f"Invalid Gemini intent repaired by slot_repair | {m.group(0)}"
                else:
                    repaired_meta = "Invalid Gemini intent repaired by slot_repair"
                    
            f.write(f"- **Reason/Repaired Metadata**: `{repaired_meta}`\n")
            
            if response.errors:
                f.write("- **Errors**:\n")
                for err in response.errors:
                    f.write(f"  - {err}\n")
                    
            f.write("\n### 렌더링된 마크다운 (최종 답변)\n")
            f.write("```markdown\n")
            f.write(response.answer_output.rendered_markdown)
            f.write("\n```\n\n")
            f.write("---\n\n")

    print("완료. live_e2e_with_gemini_result.md 파일을 확인하세요.")

if __name__ == "__main__":
    run_e2e_scenarios()
