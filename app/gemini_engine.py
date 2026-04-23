"""
Gemini API 해석 엔진
Korean Law MCP를 도구로 등록하여 function calling으로 법령 검색 후 답변 생성.
"""
import os
import json
from typing import Optional
from dotenv import load_dotenv
import company_api

load_dotenv()

from google import genai
from google.genai import types

from system_prompt import SYSTEM_PROMPT
import mcp_client as mcp  # Korean Law MCP 원격 클라이언트

# 인용 조문 저장 (답변 후 다운로드용)
_cited_laws = []

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
            types.FunctionDeclaration(
                name="search_local_company_by_product",
                description="부산 지역업체를 대표품목으로 검색합니다. 반드시 짧고 핵심적인 키워드만 사용하세요. 'LED조명'→'LED', 'CCTV카메라'→'CCTV', '소방설비'→'소방'. 조달청 등록 업체 중 부산 소재 업체만 검색됩니다.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색할 품목명 (예: 'LED', 'CCTV', '사무용가구')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_local_company_by_license",
                description="부산 지역업체를 면허(업종)으로 검색합니다. 공사/용역 업체를 찾을 때 사용. 예: '전기공사', '소방', '건축설계'",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색할 면허/업종명 (예: '전기공사', '소방시설업')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_local_company_by_category",
                description="부산 지역업체를 UNSPSC 분류코드 또는 분류명으로 검색합니다. 예: '43'(IT장비), '소방설비'",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="UNSPSC 분류코드 또는 분류명 (예: '43', '소방설비', '사무용품')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_shopping_mall",
                description="나라장터 종합쇼핑몰에 등록된 부산 지역업체의 MAS(다수공급자계약) 상품을 검색합니다. 쇼핑몰 등록 상품은 별도 계약 없이 바로 구매 가능합니다.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="품목명 (예: 'LED', '소방', '사무용가구', '컴퓨터')"
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
    global _cited_laws

    try:
        if name == "search_law":
            return mcp.search_law(args.get("query", ""))
        elif name == "get_law_text":
            result = mcp.get_law_text(mst=args.get("mst"), jo=args.get("jo"))
            # 인용 조문 저장
            _cited_laws.append({"type": "조문", "args": args, "text": result[:2000]})
            return result
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
        # ── 부산 지역업체 검색 ──
        elif name == "search_local_company_by_product":
            q = args.get("query", "")
            data = company_api.search_by_product(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"품목: {q}"
            return company_api.format_company_results(data, max_results=10)
        elif name == "search_local_company_by_license":
            q = args.get("query", "")
            data = company_api.search_by_license(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"면허: {q}"
            return company_api.format_company_results(data, max_results=10)
        elif name == "search_local_company_by_category":
            q = args.get("query", "")
            data = company_api.search_by_category(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"분류: {q}"
            return company_api.format_company_results(data, max_results=10)
        # ── 종합쇼핑몰 ──
        elif name == "search_shopping_mall":
            import shopping_mall
            q = args.get("query", "")
            data = shopping_mall.search_mall_products(q, busan_only=True)
            shopping_mall.last_mall_results = data
            shopping_mall.last_mall_query = q
            return shopping_mall.format_mall_results(data, max_results=5)
        else:
            return json.dumps({"error": f"알 수 없는 함수: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


import re

def _verify_and_annotate(answer: str) -> str:
    """
    AI 답변의 법령 인용을 verify_citations로 교차검증.
    검증 오류 발견 시 답변 하단에 간결한 경고 추가.
    """
    # 법령 인용 패턴이 없으면 스킵 (성능 최적화)
    if not re.search(r'제\d+조', answer):
        return answer

    try:
        print("  [검증] verify_citations 실행 중...")
        verification = mcp.verify_citations(answer)

        if not verification or "error" in verification.lower():
            return answer  # 검증 실패 시 원본 유지

        # 환각(HALLUCINATION) 감지 여부 확인
        hallucination_detected = "HALLUCINATION_DETECTED" in verification

        # 일반적인 검증 문제 여부 확인
        has_issues = hallucination_detected or any(kw in verification for kw in [
            "NOT_FOUND", "불일치", "확인불가", "없는",
            "mismatch", "invalid", "not found"
        ])

        if has_issues:
            # 검증 결과를 간결하게 요약 (원시 데이터를 그대로 출력하지 않음)
            answer += "\n\n---\n"
            if hallucination_detected:
                answer += "⚠️ **인용 검증 주의**: 일부 법령 인용의 정확성을 확인하지 못했습니다. 법제 담당 부서와 교차 확인을 권장합니다.\n"
            else:
                answer += "🔍 **인용 검증**: 일부 조항의 법령명 매칭이 불명확합니다. 법제처 사이트에서 직접 확인을 권장합니다.\n"
            print(f"  [검증] 인용 문제 발견 - 간결 경고 추가")
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
            lines.append(f"= 해석사례 {i+1}: {r['title']} ({r['date']})")
            lines.append(f"  분류: {r['category']}")
            if r.get('answer'):
                answer_summary = r['answer'][:800]
                lines.append(f"  회신: {answer_summary}")
            lines.append("")

        context = "\n".join(lines)
        return context[:3000]

    except Exception as e:
        print(f"  [RAG-QA] 검색 실패: {e}")
        return ""


def _search_manuals(query: str, n_results: int = 3) -> str:
    """계약 매뉴얼 RAG에서 관련 내용 검색."""
    try:
        import chromadb
        from embedding import get_query_embedding_fn
        import os
        chroma_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        ef = get_query_embedding_fn()
        collection = client.get_collection(name="manuals", embedding_function=ef)

        results = collection.query(query_texts=[query], n_results=n_results)

        if not results["documents"] or not results["documents"][0]:
            return ""

        lines = []
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            source = meta.get("source", "매뉴얼")
            page = meta.get("page", "?")
            lines.append(f"= 매뉴얼 {i+1}: [{source}] p.{page}")
            lines.append(doc[:600])
            lines.append("")

        context = "\n".join(lines)
        return context[:3000]

    except Exception as e:
        print(f"  [RAG-MANUAL] 검색 실패: {e}")
        return ""


def _search_law_rag(query: str, n_results: int = 5, agency_type: str = None) -> str:
    """핵심 법령 RAG에서 관련 조문 검색."""
    try:
        from ingest_laws import search_laws
        results = search_laws(query, n_results=n_results, agency_type=agency_type)

        if not results:
            return ""

        lines = []
        for i, r in enumerate(results):
            lines.append(f"= 법령 {i+1}: [{r['law']}] {r['article']} {r['title']}")
            lines.append(r['text'][:600])
            lines.append("")

        context = "\n".join(lines)
        return context[:4000]

    except Exception as e:
        print(f"  [RAG-LAW] search failed: {e}")
        return ""


# 사용자 친화적 도구 레이블 (보안: 내부 함수명/서버 주소 노출 방지)
TOOL_LABELS = {
    "search_law": "🔍 법령 검색 중",
    "get_law_text": "📜 조문 원문 확인 중",
    "search_interpretations": "🔍 해석례 검색 중",
    "search_decisions": "🔍 판례 검색 중",
    "get_annexes": "📊 별표/서식 조회 중",
    "chain_full_research": "🔍 종합 법령 연구 중",
    "chain_action_basis": "🔍 법체계 분석 중",
    "chain_law_system": "🔍 법령 체계도 조회 중",
    "search_local_company_by_product": "🏢 지역업체 품목 검색 중",
    "search_local_company_by_license": "🏢 지역업체 면허 검색 중",
    "search_local_company_by_category": "🏢 지역업체 분류 검색 중",
}


def chat(user_message: str, history: list[dict] = None, progress_callback=None, agency_type: str = None) -> tuple[str, list[dict]]:
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
    
    global _cited_laws
    _cited_laws = []  # 매 답변마다 초기화

    # 대화 이력을 Gemini 형식으로 변환
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["text"])]
            )
        )

    # === RAG: 법령 원문 + 조달청 QA 검색 ===
    if progress_callback:
        progress_callback("📚 관련 법령 데이터베이스 검색 중...")
    law_rag = _search_law_rag(user_message, agency_type=agency_type)
    pps_rag = _search_pps_qa(user_message)
    manual_rag = _search_manuals(user_message)

    # 혁신제품 검색
    innovation_rag = ""
    try:
        from ingest_innovation import search_innovation
        innovation_rag = search_innovation(user_message, n_results=5)
    except Exception:
        pass

    # 기술개발제품 인증 검색
    tech_rag = ""
    try:
        from ingest_tech_products import search_tech_products
        tech_rag = search_tech_products(user_message, max_results=5)
    except Exception:
        pass

    # 현재 사용자 메시지 추가 (RAG 컨텍스트 포함)
    user_text = user_message
    rag_parts = []
    if law_rag:
        rag_parts.append(f"[참고용 보조자료: 법령 조문 — MCP 검색 결과와 다르면 MCP가 우선]\n{law_rag}")
    if pps_rag:
        rag_parts.append(f"[참고용 보조자료: 조달청 질의응답 — MCP 검색 결과와 다르면 MCP가 우선]\n{pps_rag}")
    if manual_rag:
        rag_parts.append(f"[참고용 보조자료: 계약 매뉴얼 — MCP 검색 결과와 다르면 MCP가 우선]\n{manual_rag}")
    if innovation_rag:
        rag_parts.append(f"[부산 지역 혁신제품 — 시행령 제25조제1항제8호에 따라 금액 무제한 수의계약 가능]\n{innovation_rag}")
    if tech_rag:
        rag_parts.append(f"[부산 지역 기술개발제품 인증 — 시행령 제25조제1항제6호에 따라 수의계약 가능]\n{tech_rag}")
    
    if rag_parts:
        user_text = "\n\n".join(rag_parts) + f"\n\n[사용자 질문]\n{user_message}"

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_text)]
        )
    )

    # Gemini 설정 — 현재 날짜를 시스템 프롬프트에 동적 주입
    from datetime import datetime
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 기관 유형별 적용 법체계 동적 주입
    agency_guide = ""
    if agency_type == "지방자치단체":
        agency_guide = (
            "\n\n[적용 법체계: 지방자치단체]\n"
            "★ 이 사용자는 지방자치단체 소속입니다. 반드시 아래 법체계만 적용하세요:\n"
            "  · 기본법: 지방자치단체를 당사자로 하는 계약에 관한 법률 (지방계약법)\n"
            "  · 시행령: 지방계약법 시행령\n"
            "  · 행정규칙: 지방자치단체 입찰 및 계약집행기준, 낙찰자 결정기준\n"
            "⛔ 국가계약법 기준으로 답변하면 오답입니다! 절대 혼동 금지!\n"
        )
    elif agency_type == "국가기관":
        agency_guide = (
            "\n\n[적용 법체계: 국가기관]\n"
            "★ 이 사용자는 국가기관 소속입니다. 반드시 아래 법체계만 적용하세요:\n"
            "  · 기본법: 국가를 당사자로 하는 계약에 관한 법률 (국가계약법)\n"
            "  · 시행령: 국가계약법 시행령\n"
            "  · 행정규칙: 정부 입찰/계약 집행기준, 계약업무처리훈령\n"
            "⛔ 지방계약법 기준으로 답변하면 오답입니다! 절대 혼동 금지!\n"
        )
    elif agency_type == "공기업/준정부기관":
        agency_guide = (
            "\n\n[적용 법체계: 공기업/준정부기관]\n"
            "★ 이 사용자는 공기업·준정부기관 소속입니다:\n"
            "  · 상위법: 공공기관의 운영에 관한 법률\n"
            "  · 계약규칙: 공기업/준정부기관 계약사무규칙\n"
            "  · 지방계약법·국가계약법과 기준이 다를 수 있으므로 주의!\n"
        )
    elif agency_type:
        agency_guide = f"\n\n[적용 기관: {agency_type}]\n해당 기관의 법체계를 우선 적용하세요.\n"
    else:
        agency_guide = (
            "\n\n[적용 법체계: 미지정 → 지방자치단체 기본]\n"
            "사용자가 소속기관을 밝히지 않았으므로 지방계약법 기준으로 답변하되,\n"
            "답변 하단에 '국가기관·공기업 등은 기관명을 입력하시면 맞춤 답변 가능' 안내 포함.\n"
        )

    date_instruction = (
        f"\n\n[조회 시점: {today}]\n"
        f"법령 조회 결과를 인용할 때 반드시 \"{today} 기준\"임을 답변에 명시하세요.\n"
        f"예: \"지방계약법 시행령 제25조({today} 기준)에 따르면...\""
        f"{agency_guide}"
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + date_instruction,
        tools=law_tools,
        temperature=0.1,  # 법률 도메인 — 강제 규칙 준수 + 사실 기반 답변 (0.0에 가까울수록 결정적)
    )

    # Function calling 루프 (최대 15회 반복 — 기관별 비교 답변 시 다수 법령 검색 필요)
    for loop_i in range(15):
        # 429 에러 자동 재시도 (무료 티어 분당 제한 대응)
        response = None
        last_err = None
        for retry in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=contents,
                    config=config,
                )
                break  # 성공
            except Exception as api_err:
                last_err = api_err
                err_msg = str(api_err)
                if any(kw in err_msg for kw in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                    import time
                    wait_sec = 15 * (retry + 1)
                    print(f"  [API] Retry {retry+1}/3 - waiting {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    raise  # 429 외 에러는 그대로 전달
        
        if response is None:
            raise last_err or Exception("API call failed after 3 retries")

        # Function call 응답인지 확인
        candidate = response.candidates[0]
        
        # content가 None인 경우 (안전 필터 또는 빈 응답)
        if candidate.content is None or not candidate.content.parts:
            reason = getattr(candidate, 'finish_reason', None)
            print(f"  [WARNING] Empty response. finish_reason={reason}")
            if reason and "SAFETY" in str(reason):
                return "⚠️ 해당 질문은 AI 안전 정책에 의해 답변이 제한됩니다. 계약·조달 관련 법률 질문으로 다시 시도해 주세요.", history
            elif reason and "RECITATION" in str(reason):
                return "⚠️ 법령 원문 인용 제한으로 답변이 생성되지 않았습니다. 질문을 좀 더 구체적으로 입력해 주세요.", history
            else:
                return "⚠️ 답변을 생성하지 못했습니다. 질문을 계약·조달 법령과 관련된 구체적인 내용으로 다시 작성해 주세요.\n\n예시: \"수의계약 기준 금액이 얼마야?\", \"지역제한 입찰 가능한 조건이 뭐야?\"", history
        
        has_function_call = False

        for part in candidate.content.parts:
            if part.function_call:
                has_function_call = True
                fc = part.function_call
                # 진행 로그 (서버 콘솔에 표시)
                print(f"  [tool] {fc.name}({dict(fc.args) if fc.args else {}})")
                
                # UI 진행 상태 표시 (보안: 사용자 친화적 레이블만)
                if progress_callback:
                    label = TOOL_LABELS.get(fc.name, "🔍 검색 중")
                    query = dict(fc.args).get("query", "") if fc.args else ""
                    if query:
                        progress_callback(f"{label}: {query}")
                    else:
                        progress_callback(label)

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
            if progress_callback:
                progress_callback("✅ 법령 인용 검증 중...")
            answer = _verify_and_annotate(answer)

            # 대화 이력 업데이트
            history.append({"role": "user", "text": user_message})
            history.append({"role": "model", "text": answer})

            return answer, history

    print(f"  [WARNING] Function calling loop exhausted after {loop_i+1} iterations")
    return "⚠️ 법령 검색 반복 한도를 초과했습니다. 질문을 더 구체적으로(예: 기관 유형 명시) 입력해 주세요.", history


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=== AI 법령 챗봇 테스트 ===\n")
    test_q = "지역제한 입찰 기준 금액이 얼마야?"
    print(f"Q: {test_q}\n")
    answer, _ = chat(test_q)
    print(f"A:\n{answer}")
