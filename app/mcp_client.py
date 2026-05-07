"""
Korean Law MCP 클라이언트
NCP 서버(49.50.133.160)에서 자체 호스팅한 MCP v3.5를 통해 법령 검색.

모든 76개 도구 사용 가능: 법령/판례/해석례/행정규칙/별표/체인 등.
MCP(Model Context Protocol) JSON-RPC over HTTP로 통신.
"""
import os
import json
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# NCP 자체 호스팅 MCP (fly.dev 대비 전 도구 동작)
# .env.example과의 호환: MCP_ENDPOINT / MCP_BASE_URL 모두 인식
MCP_BASE_URL = os.getenv("MCP_ENDPOINT") or os.getenv("MCP_BASE_URL", "http://49.50.133.160:3000/mcp")
# .env.example과의 호환: LAW_OC / LAW_API_OC 모두 인식
OC = os.getenv("LAW_OC") or os.getenv("LAW_API_OC", "busanproduct1")
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_request_id = 0


def _mcp_call(tool_name: str, arguments: dict, timeout: int = None) -> dict:
    """MCP 도구 호출 공통 함수. timeout 미지정 시 환경변수 기반."""
    global _request_id
    _request_id += 1

    # P0-6: timeout 환경변수 기반 (하드코딩 제거)
    if timeout is None:
        from policies.timeout_policy import get_timeout
        timeout = get_timeout(tool_name)

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
        "id": _request_id,
    }

    try:
        resp = requests.post(
            f"{MCP_BASE_URL}?oc={OC}",
            json=payload,
            headers=MCP_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        # MCP 응답에서 텍스트 추출
        result = data.get("result", {})
        contents = result.get("content", [])
        is_error = result.get("isError", False)

        text = ""
        for content in contents:
            if content.get("type") == "text":
                text += content.get("text", "")

        return {
            "success": not is_error,
            "text": text,
            "raw": data,
        }
    except Exception as e:
        return {
            "success": False,
            "text": f"MCP 호출 오류: {str(e)}",
            "raw": None,
        }


# ─────────────────────────────────────────────
# 공개 API (law_api_client.py와 동일 인터페이스)
# ─────────────────────────────────────────────

def search_law(query: str, display: int = 5) -> str:
    """법령명으로 검색. 내부 DB 우선 → 외부 MCP 보완."""
    # ── 1단계: 내부 DB 우선 조회 (key_articles.json + ChromaDB) ──
    try:
        from internal_law_lookup import search_internal_law
        internal_result = search_internal_law(query)
        if internal_result:
            return internal_result
    except Exception as e:
        print(f"  [search_law] 내부 DB 조회 실패: {e}")
    
    # ── 2단계: 내부에 없으면 외부 MCP 보완 호출 ──
    try:
        result = _mcp_call("search_law", {"query": query, "display": display})
        if result["success"] and result["text"] and "[NOT_FOUND]" not in result["text"]:
            return f"[외부MCP] {result['text']}"
        # 외부 MCP도 NOT_FOUND
        return result["text"]
    except Exception as e:
        return f"[FAILED] 외부 MCP 호출 실패 (법제처 API 응답 거부 가능): {e}"


def get_law_text(mst: str = None, law_id: str = None, jo: str = None) -> str:
    """법령 조문 조회. 내부 DB 우선 → 외부 MCP fallback."""
    # ── 1단계: 내부 DB 우선 조회 (MST + 조문번호) ──
    if mst and jo:
        try:
            from internal_law_lookup import _load_law_db, _mst_to_short, _lookup_index
            _load_law_db()
            if _mst_to_short and _lookup_index:
                short_name = _mst_to_short.get(str(mst))
                if short_name:
                    # 조문번호 정규화: "25" → "제25조"
                    article_key = f"제{jo}조" if not jo.startswith("제") else jo
                    lookup_key = f"{short_name} {article_key}"
                    text = _lookup_index.get(lookup_key, "")
                    if text:
                        print(f"  [get_law_text] 내부 DB HIT: {lookup_key} ({len(text)} chars)")
                        return f"[내부DB] [{lookup_key}]\n{text}"
        except Exception as e:
            print(f"  [get_law_text] 내부 DB 조회 실패: {e}")
    
    # ── 2단계: 외부 MCP fallback ──
    args = {}
    if mst:
        args["mst"] = mst
    if law_id:
        args["lawId"] = law_id
    if jo:
        args["jo"] = jo
    result = _mcp_call("get_law_text", args)
    return result["text"]


def search_interpretations(query: str) -> str:
    """해석례(유권해석) 검색."""
    result = _mcp_call("search_decisions", {
        "query": query,
        "domain": "interpretation",
        "display": 5,
    })
    return result["text"]


def search_decisions(query: str) -> str:
    """판례 검색."""
    result = _mcp_call("search_decisions", {
        "query": query,
        "domain": "precedent",
        "display": 5,
    })
    return result["text"]


def get_annexes(law_name: str, annex_no: str = None) -> str:
    """별표/서식 조회."""
    args = {"lawName": law_name}
    if annex_no:
        args["annexNo"] = annex_no
    result = _mcp_call("get_annexes", args)
    return result["text"]


def chain_law_system(query: str) -> str:
    """법률→시행령→시행규칙→행정규칙 4단 체계 분석. 내부 DB 우선 → 외부 MCP 보완."""
    # ── 1단계: 내부 DB 우선 (0ms) ──
    try:
        from internal_law_lookup import chain_law_system_internal
        internal_result = chain_law_system_internal(query)
        if internal_result:
            return internal_result
    except Exception as e:
        print(f"  [chain_law_system] 내부 DB 실패: {e}")
    
    # ── 2단계: 내부에 없으면 외부 MCP 보완 ──
    try:
        result = _mcp_call("chain_law_system", {"query": query})
        if result["success"]:
            return f"[외부MCP] {result['text']}"
        return f"[FAILED] chain_law_system 실패: {result['text']}"
    except Exception as e:
        return f"[FAILED] chain_law_system 외부 MCP 호출 실패: {e}"


def chain_full_research(query: str) -> str:
    """종합 리서치. 법령(내부DB) + 판례·해석례(외부MCP) 하이브리드."""
    parts = []
    
    # ── 1단계: 법령/행정규칙 (내부 DB, 0ms) ──
    try:
        from internal_law_lookup import chain_full_research_internal
        internal_result = chain_full_research_internal(query)
        if internal_result:
            parts.append(internal_result)
    except Exception as e:
        print(f"  [chain_full_research] 내부 DB 실패: {e}")
    
    # ── 2단계: 판례·해석례 (외부 MCP) ──
    try:
        prec = _mcp_call("search_decisions", {"query": query, "domain": "precedent", "display": 3})
        if prec["success"] and prec["text"] and len(prec["text"]) > 30:
            parts.append(f"▶ 관련 판례:\n{prec['text']}")
    except Exception:
        pass
    
    try:
        interp = _mcp_call("search_decisions", {"query": query, "domain": "interpretation", "display": 3})
        if interp["success"] and interp["text"] and len(interp["text"]) > 30:
            parts.append(f"▶ 관련 해석례:\n{interp['text']}")
    except Exception:
        pass
    
    if parts:
        return "\n\n".join(parts)
    
    # 전부 실패 시 외부 MCP chain 시도
    try:
        result = _mcp_call("chain_full_research", {"query": query})
        if result["success"]:
            return f"[외부MCP] {result['text']}"
        return f"[FAILED] chain_full_research 실패: {result['text']}"
    except Exception as e:
        return f"[FAILED] chain_full_research 실패: {e}"


def chain_action_basis(query: str) -> str:
    """처분/허가/인가의 법적 근거 종합 추적."""
    result = _mcp_call("chain_action_basis", {"query": query})
    return result["text"]


def verify_citations(text: str) -> str:
    """LLM 환각 방지 — 법령 인용 교차검증."""
    result = _mcp_call("verify_citations", {"text": text})
    return result["text"]


# ─────────────────────────────────────────────
# 행정규칙 (훈령/예규/고시) — execute_tool 경유
# ─────────────────────────────────────────────

def search_admin_rule(query: str, knd: int = None) -> str:
    """행정규칙(훈령/예규/고시) 검색. 내부 DB 우선 → 외부 MCP 보완."""
    # ── 1단계: 내부 DB 우선 조회 ──
    try:
        from internal_law_lookup import search_internal_admin_rule
        internal_result = search_internal_admin_rule(query)
        if internal_result:
            return internal_result
    except Exception as e:
        print(f"  [search_admin_rule] 내부 DB 조회 실패: {e}")
    
    # ── 2단계: 외부 MCP 보완 호출 ──
    try:
        params = {"query": query}
        if knd is not None:
            params["knd"] = str(knd)
        result = _mcp_call("execute_tool", {
            "tool_name": "search_admin_rule",
            "params": params,
        })
        if result["success"]:
            return f"[외부MCP] {result['text']}"
        return result["text"]
    except Exception as e:
        return f"[FAILED] search_admin_rule 외부 MCP 호출 실패: {e}"


def get_admin_rule(rule_id: str) -> str:
    """행정규칙 전문 조회. 내부 DB 우선 → 외부 MCP fallback."""
    # ── 1단계: 내부 DB 우선 조회 ──
    try:
        from internal_law_lookup import _load_law_db, _law_db_cache
        _load_law_db()
        if _law_db_cache:
            # rule_id가 숫자ID일 수 있으므로, DB에서 이름 기반 매칭 시도
            for short_name, law_data in _law_db_cache.items():
                source = law_data.get("source", "")
                if "행정규칙" not in source and "규정" not in short_name \
                   and "예규" not in short_name and "기준" not in short_name \
                   and "요령" not in short_name and "세칙" not in short_name:
                    continue
                # rule_id가 이름의 일부인지 확인
                if rule_id in short_name or short_name in rule_id:
                    articles = law_data.get("articles", {})
                    if articles:
                        lines = [f"[내부DB] {short_name} 전문"]
                        for art_no, art_data in articles.items():
                            lines.append(art_data.get("text", "")[:2000])
                        result_text = "\n\n".join(lines)
                        print(f"  [get_admin_rule] 내부 DB HIT: {short_name} ({len(result_text)} chars)")
                        return result_text
    except Exception as e:
        print(f"  [get_admin_rule] 내부 DB 조회 실패: {e}")
    
    # ── 2단계: 외부 MCP fallback ──
    result = _mcp_call("execute_tool", {
        "tool_name": "get_admin_rule",
        "params": {"id": rule_id},
    })
    return result["text"]


# ─────────────────────────────────────────────
# 추가 체인 도구 (기본 노출 15개에 포함)
# ─────────────────────────────────────────────

def chain_procedure_detail(query: str) -> str:
    """절차·비용·서식 안내 (법체계→별표→시행규칙별표)."""
    result = _mcp_call("chain_procedure_detail", {"query": query})
    return result["text"]


def chain_ordinance_compare(query: str) -> str:
    """조례 비교 연구 (상위법→전국 조례 검색). 외부 MCP 사용."""
    try:
        result = _mcp_call("chain_ordinance_compare", {"query": query})
        if result["success"]:
            return result["text"]
        return f"[FAILED] chain_ordinance_compare 실패: {result['text']}"
    except Exception as e:
        return f"[FAILED] chain_ordinance_compare 외부 MCP 호출 실패: {e}"


def chain_amendment_track(query: str) -> str:
    """개정 추적 (신구대조+조문이력)."""
    result = _mcp_call("chain_amendment_track", {"query": query})
    return result["text"]


def chain_document_review(query: str) -> str:
    """계약서·약관 리스크 분석 (문서분석→관련법령→판례)."""
    result = _mcp_call("chain_document_review", {"query": query})
    return result["text"]


# ─────────────────────────────────────────────
# 판례/해석례 전문 조회
# ─────────────────────────────────────────────

def get_decision_text(decision_id: str, domain: str = "precedent") -> str:
    """판례·해석례 전문 조회. search_decisions 결과에서 얻은 ID 사용."""
    result = _mcp_call("get_decision_text", {
        "id": decision_id,
        "domain": domain,
    })
    return result["text"]


# ─────────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("=== Korean Law MCP 테스트 (NCP 서버) ===\n")
    print(f"엔드포인트: {MCP_BASE_URL}\n")

    print("1. search_law('지방계약법'):")
    print(search_law("지방계약법", 3))

    print("\n2. search_decisions('수의계약'):")
    print(search_decisions("수의계약"))

    print("\n3. search_interpretations('수의계약'):")
    print(search_interpretations("수의계약"))
