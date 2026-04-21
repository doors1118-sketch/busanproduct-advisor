"""
Gemini API 해석 엔진
Korean Law MCP를 도구로 등록하여 function calling으로 법령 검색 후 답변 생성.
"""
import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

from system_prompt import SYSTEM_PROMPT
import mcp_client as mcp  # Korean Law MCP 원격 클라이언트

# ─────────────────────────────────────────────
# Gemini 클라이언트 초기화
# ─────────────────────────────────────────────
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ─────────────────────────────────────────────
# Function Calling 도구 정의
# ─────────────────────────────────────────────

law_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_law",
                description="법령명으로 검색. 약칭 자동변환 지원(지방계약법→지방자치단체를 당사자로 하는 계약에 관한 법률). MST 식별자 획득용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색할 법령명 (예: '지방계약법', '근로기준법', '조달사업법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_law_text",
                description="법령 MST 식별자로 특정 조문의 원문을 조회합니다. search_law 결과에서 얻은 MST를 사용하세요.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "mst": types.Schema(
                            type="STRING",
                            description="법령 MST 식별자 (search_law 결과에서 획득)"
                        ),
                        "jo": types.Schema(
                            type="STRING",
                            description="조문번호 (예: '제25조', '제13조의 2'). 생략하면 전체 조문 조회"
                        ),
                    },
                    required=["mst"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_interpretations",
                description="해석례(유권해석) 검색. 법령 해석에 관한 행정부 질의회신을 찾을 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색 키워드 (예: '수의계약', '지역제한 입찰')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_decisions",
                description="판례 검색. 대법원 판결, 감사원 결정 등을 찾을 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색 키워드 (예: '지역제한 입찰 위법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_annexes",
                description="별표/서식 조회. 금액 기준표, 요율표, 처분기준표 등이 별표에 있을 때 사용. HWP/HWPX 자동 Markdown 변환.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "law_name": types.Schema(
                            type="STRING",
                            description="법령명 (예: '산업안전보건법', '지방계약법 시행령')"
                        ),
                    },
                    required=["law_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_full_research",
                description="종합 리서치. 법령명이 불명확한 복합 질문에 사용. AI검색→법령→판례→해석례 병렬 수행.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="자연어 질문 (예: '수의계약 한도', '지역업체 우선구매')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_action_basis",
                description="처분/허가/인가의 법적 근거 종합 추적. 법체계→해석례→판례→행심 병렬 조회. 법령명이 특정된 질문에 적합.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="법령명 + 주제 (예: '지방계약법', '건축법 허가')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_law_system",
                description="법령 체계 분석. 법률→시행령→시행규칙 3단 구조 + 위임 조문 + 하위법령을 한번에 조회.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="법령명 (예: '지방계약법', '건축법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
        ]
    )
]


def _execute_function_call(function_call) -> str:
    """Function call을 실행하고 결과를 반환. MCP 원격 엔드포인트 사용."""
    name = function_call.name
    args = dict(function_call.args) if function_call.args else {}

    try:
        if name == "search_law":
            return mcp.search_law(args.get("query", ""))
        elif name == "get_law_text":
            return mcp.get_law_text(mst=args.get("mst"), jo=args.get("jo"))
        elif name == "search_interpretations":
            return mcp.search_interpretations(args.get("query", ""))
        elif name == "search_decisions":
            return mcp.search_decisions(args.get("query", ""))
        elif name == "get_annexes":
            return mcp.get_annexes(args.get("law_name", ""))
        elif name == "chain_full_research":
            return mcp.chain_full_research(args.get("query", ""))
        elif name == "chain_action_basis":
            return mcp.chain_action_basis(args.get("query", ""))
        elif name == "chain_law_system":
            return mcp.chain_law_system(args.get("query", ""))
        else:
            return json.dumps({"error": f"알 수 없는 함수: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


import re

def _verify_and_annotate(answer: str) -> str:
    """
    AI 답변의 법령 인용을 verify_citations로 교차검증.
    검증 오류 발견 시 답변 하단에 경고 추가.
    """
    # 법령 인용 패턴이 없으면 스킵 (성능 최적화)
    if not re.search(r'제\d+조', answer):
        return answer

    try:
        print("  [검증] verify_citations 실행 중...")
        verification = mcp.verify_citations(answer)

        if not verification or "error" in verification.lower():
            return answer  # 검증 실패 시 원본 유지

        # 검증 결과에서 문제 발견 여부 확인
        has_issues = any(kw in verification for kw in [
            "NOT_FOUND", "불일치", "확인불가", "없는", "오류",
            "mismatch", "invalid", "not found"
        ])

        if has_issues:
            answer += "\n\n---\n"
            answer += "🔍 **인용 검증 결과**\n"
            answer += verification
            print("  [검증] ⚠️ 인용 문제 발견 — 경고 추가")
        else:
            answer += "\n\n✅ *법령 인용이 검증되었습니다.*"
            print("  [검증] ✅ 인용 정확성 확인 완료")

        return answer

    except Exception as e:
        print(f"  [검증] 검증 중 오류 (무시): {e}")
        return answer  # 검증 실패해도 원본 답변 유지


def _search_pps_qa(query: str, n_results: int = 3) -> str:
    """조달청 질의응답 DB에서 유사 해석사례 검색 (RAG)."""
    try:
        from ingest_pps_qa import search_qa
        results = search_qa(query, n_results=n_results)

        if not results:
            return ""

        lines = []
        for i, r in enumerate(results):
            lines.append(f"━ 해석사례 {i+1}: {r['title']} ({r['date']})")
            lines.append(f"  분류: {r['category']}")
            if r.get('answer'):
                # 핵심만 추출 (너무 길면 잘라냄)
                answer_summary = r['answer'][:800]
                lines.append(f"  회신: {answer_summary}")
            lines.append("")

        context = "\n".join(lines)
        print(f"  [RAG] 조달청 해석사례 {len(results)}건 검색 완료")
        return context

    except Exception as e:
        print(f"  [RAG] 검색 실패 (무시): {e}")
        return ""


def chat(user_message: str, history: list[dict] = None) -> tuple[str, list[dict]]:
    """
    사용자 메시지를 받아 Gemini와 대화.
    법제처 API function calling을 자동 처리.

    Args:
        user_message: 사용자 입력 메시지
        history: 이전 대화 이력 [{"role": "user"/"model", "text": "..."}]

    Returns:
        (답변 텍스트, 업데이트된 대화 이력)
    """
    if history is None:
        history = []

    # 대화 이력을 Gemini 형식으로 변환
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["text"])]
            )
        )

    # ─── RAG: 조달청 질의응답 유사 사례 검색 ───
    rag_context = _search_pps_qa(user_message)

    # 현재 사용자 메시지 추가 (RAG 컨텍스트 포함)
    user_text = user_message
    if rag_context:
        user_text = f"""[참고: 조달청 종합민원센터 관련 해석사례]
{rag_context}

[사용자 질문]
{user_message}"""

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_text)]
        )
    )

    # Gemini 설정
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=law_tools,
        temperature=0.3,  # 법률 해석이므로 낮은 창의성
    )

    # Function calling 루프 (최대 5회 반복)
    for _ in range(5):
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=contents,
            config=config,
        )

        # Function call 응답인지 확인
        candidate = response.candidates[0]
        has_function_call = False

        for part in candidate.content.parts:
            if part.function_call:
                has_function_call = True
                fc = part.function_call
                print(f"  [도구 호출] {fc.name}({dict(fc.args) if fc.args else {}})")

                # 함수 실행
                result_str = _execute_function_call(fc)

                # 모델 응답 + 함수 결과를 대화에 추가
                contents.append(candidate.content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response={"result": result_str}
                        )]
                    )
                )
                break  # 다음 루프에서 모델이 결과 해석

        if not has_function_call:
            # 최종 텍스트 답변
            answer = candidate.content.parts[0].text if candidate.content.parts else ""

            # ─── 환각 방지: verify_citations ───
            answer = _verify_and_annotate(answer)

            # 대화 이력 업데이트
            history.append({"role": "user", "text": user_message})
            history.append({"role": "model", "text": answer})

            return answer, history

    return "죄송합니다. 답변을 생성하는 데 문제가 발생했습니다. 다시 시도해주세요.", history


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=== AI 법령 챗봇 테스트 ===\n")
    test_q = "지역제한 입찰 기준 금액이 얼마야?"
    print(f"Q: {test_q}\n")
    answer, _ = chat(test_q)
    print(f"A:\n{answer}")
