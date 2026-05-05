import os
import sys
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest

request = ChatbotRuntimeRequest(
    user_query="CCTV 중기경쟁제품인지 알려주고 업체도 좀 찾아줘",
    mock_gemini_response={
        "primary_intent": "mixed",
        "secondary_intents": ["item_eligibility", "candidate_search"],
        "confidence": 0.95,
        "slots": {
            "contract_object": "goods",
            "item_name": "CCTV",
            "item_eligibility_requested": True,
            "candidate_lookup_requested": True,
            "location": "부산"
        },
        "candidate_lookup_required": True,
        "routing_decision": "mixed_flow"
    },
    runtime_options={
        "use_mock_company_api": False,
        "use_mock_item_eligibility": False,
        "use_evidence_builder": True
    }
)

print("=== 챗봇 오케스트레이터 실행 (NCP Live API) ===")
response = run_chatbot_runtime(request)

print(f"\n[상태] {response.runtime_status}")
print("\n[거친 단계들]")
for stage in response.runtime_stages:
    print(f" - {stage.stage_name}: {stage.status} (skipped={stage.skipped}, reason={getattr(stage, 'reason', None)})")

print("\n[에러]")
for err in response.errors:
    print(f" - {err}")

print("\n[최종 생성된 답변(Markdown)]")
print("-" * 60)
print(response.answer_output.rendered_markdown if response.answer_output else "답변이 생성되지 않았습니다.")
print("-" * 60)
