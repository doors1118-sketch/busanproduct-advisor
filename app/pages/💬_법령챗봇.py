"""
💬 법령챗봇 — AI 법령 해석 상담
지역상생 조달 어드바이저의 핵심 기능 2.
"""
import sys
import os

# app 디렉토리를 Python 경로에 추가
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)

import streamlit as st
from dotenv import load_dotenv

# .env 파일: 프로젝트 루트(app 상위)에서 로드
PROJECT_ROOT = os.path.dirname(APP_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from gemini_engine import chat
from system_prompt import EXAMPLE_QUESTIONS

# ── 스타일 ──
st.markdown("""
<style>
    /* 메인 영역 좌우 여백 축소 */
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
    }
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }
    .chat-header {
        font-size: 1.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3a5f 0%, #2e86de 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .chat-sub {
        color: #666;
        font-size: 0.95rem;
        margin-bottom: 1rem;
    }
    /* 예시 질문 버튼 크기 통일 */
    .stButton > button {
        min-height: 3.2rem !important;
        height: auto !important;
        white-space: normal !important;
        line-height: 1.3 !important;
    }
    .disclaimer {
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        font-size: 0.85rem;
        color: #856404;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──
AGENCY_TYPES = {
    "지방자치단체 (부산시·구·군·교육청)": "지방자치단체(부산광역시)",
    "국가기관 (중앙부처·소속기관)": "국가기관",
    "국가 공기업 및 준정부기관": "공기업·준정부기관",
    "부산시 공사공단 및 출자출연기관 (부산도시공사 등)": "지방출자출연기관",
    "미지정 (일반 안내)": None,
}

with st.sidebar:
    st.markdown("### 💬 AI 법령 챗봇")
    st.caption("법제처 API + Gemini 기반")
    st.markdown("---")
    st.markdown("""
    **사용 방법**
    1. 소속기관 유형 선택
    2. 계약·조달 관련 질문 입력
    3. 해당 법령 기준으로 답변
    """)
    st.markdown("---")
    st.markdown("**📌 답변 구조**")
    st.markdown("""
    - 📌 결론
    - 📜 법적 근거
    - 💼 실무 적용
    - 🏢 지역제품 구매 방법
    - ⚠️ 주의사항
    """)
    st.markdown("---")
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.rerun()

# ── 세션 상태 초기화 ──
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── 메인 헤더 ──
st.markdown('<div class="chat-header">💬 부산광역시 지역경제 상생협력 어드바이저</div>', unsafe_allow_html=True)
st.markdown('<div class="chat-sub">계약 및 조달 법령에 대해 질문하면, 법제처 API에서 법령 및 행정규칙, 해석례, 소속기관의 계약지침을 검색하여 답변합니다.</div>', unsafe_allow_html=True)

# ── 소속기관 유형 선택 (메인 영역) ──
agency_key = st.selectbox(
    "📋 소속기관 유형",
    options=list(AGENCY_TYPES.keys()),
    index=0,
)
selected_agency = AGENCY_TYPES[agency_key]

# ── 대화가 없을 때 예시 질문 표시 ──
if not st.session_state.messages:
    st.markdown("#### 💡 이런 질문을 해보세요")
    cols = st.columns(min(len(EXAMPLE_QUESTIONS), 3))
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        col_idx = i % 3
        with cols[col_idx]:
            if st.button(q, key=f"example_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.rerun()

# ── 기존 대화 표시 ──
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "⚖️"):
        st.markdown(msg["content"])

# ── 사용자 입력 처리 ──
user_input = st.chat_input("계약·조달 법령에 대해 질문하세요...")

# 예시 질문 버튼에서 온 입력 처리
if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

if user_input:
    # 사용자 메시지 표시 (UI에는 원본 질문만)
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(user_input)
    
    # 기관 유형 컨텍스트를 질문에 삽입 (Gemini에만 전달)
    if selected_agency:
        chat_input = f"[소속기관: {selected_agency}] {user_input}"
    else:
        chat_input = user_input

    # AI 답변 생성
    with st.chat_message("assistant", avatar="⚖️"):
        status_container = st.status("법령을 검색하고 해석 중입니다...", expanded=True)
        try:
            def on_progress(msg):
                status_container.update(label=msg, state="running")
                status_container.write(msg)
            
            answer, updated_history = chat(
                chat_input,
                st.session_state.chat_history,
                progress_callback=on_progress,
                agency_type=selected_agency,
            )
            status_container.update(label="✅ 답변 완료", state="complete", expanded=False)
            st.session_state.chat_history = updated_history
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # ── 업체 검색 결과가 있으면 다운로드 + 펼쳐보기 ──
            import company_api
            results = company_api.last_search_results
            companies = results.get("업체목록", []) if results else []
            total = results.get("검색결과수", 0) if results else 0
            
            if companies and total > 10:
                query_label = company_api.last_search_query or "업체 검색"
                
                st.markdown(f"---\n📊 **전체 {total}건** 중 상위 10건만 표시됨")
                
                col1, col2 = st.columns(2)
                with col1:
                    excel_bytes = company_api.results_to_excel(results)
                    if excel_bytes:
                        st.download_button(
                            label=f"📥 전체 {total}건 Excel 다운로드",
                            data=excel_bytes,
                            file_name=f"부산_지역업체_{query_label}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                
                with col2:
                    pass  # 여백
                
                with st.expander(f"📋 전체 {total}건 펼쳐보기"):
                    import pandas as pd
                    safe_fields = ["업체명", "소재지", "대표품명", "업체구분", "제조구분"]
                    rows = [{f: c.get(f, "") for f in safe_fields} for c in companies]
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, height=400)
                
                # 결과 초기화 (중복 노출 방지)
                company_api.last_search_results = {}
                company_api.last_search_query = ""
            
            # ── 종합쇼핑몰 검색 결과 다운로드 ──
            import shopping_mall
            mall_results = shopping_mall.last_mall_results
            mall_items = mall_results.get("items", []) if mall_results else []
            
            if mall_items:
                mall_query = shopping_mall.last_mall_query or "쇼핑몰"
                filtered = mall_results.get("filteredCount", len(mall_items))
                
                st.markdown(f"---\n🛒 **종합쇼핑몰 부산 업체 상품: {filtered}건**")
                
                col1, col2 = st.columns(2)
                with col1:
                    excel_bytes = shopping_mall.results_to_excel(mall_results)
                    if excel_bytes:
                        st.download_button(
                            label=f"📥 쇼핑몰 {filtered}건 Excel",
                            data=excel_bytes,
                            file_name=f"종합쇼핑몰_{mall_query}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
                with col2:
                    pass
                
                with st.expander(f"🛒 종합쇼핑몰 {filtered}건 펼쳐보기"):
                    import pandas as pd
                    fields = {"cntrctCorpNm": "업체명", "hdoffceLocplc": "소재지",
                              "prdctSpecNm": "물품규격", "cntrctPrceAmt": "가격",
                              "cntrctMthdNm": "계약방법", "qltyRltnCertInfo": "인증"}
                    rows = [{kor: item.get(eng, "") for eng, kor in fields.items()} for item in mall_items]
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True, height=300)
                
                shopping_mall.last_mall_results = {}
                shopping_mall.last_mall_query = ""
            
            # ── 인용 규정 다운로드 ──
            import gemini_engine
            if gemini_engine._cited_laws:
                cited_text = ""
                for i, law in enumerate(gemini_engine._cited_laws):
                    cited_text += f"\n{'='*60}\n"
                    cited_text += f"📜 인용 규정 {i+1}\n"
                    cited_text += f"{'='*60}\n"
                    cited_text += law.get("text", "")
                    cited_text += "\n"
                
                st.download_button(
                    label=f"📜 인용 규정 {len(gemini_engine._cited_laws)}건 다운로드",
                    data=cited_text.encode("utf-8"),
                    file_name="인용_법령_규정.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
                
        except Exception as e:
            status_container.update(label="❌ 오류 발생", state="error", expanded=False)
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                error_msg = "⏳ **API 사용량 한도 초과**\n\n무료 티어 분당 요청 한도에 도달했습니다. **30초 후 다시 시도해주세요.**\n\n(결제 연결 시 이 제한이 해제됩니다)"
            elif "503" in err_str or "UNAVAILABLE" in err_str:
                error_msg = "⏳ **Gemini 서버 일시 과부하**\n\n잠시 후 다시 시도해주세요. (보통 1~2분 내 복구됩니다)"
            else:
                error_msg = f"⚠️ 오류가 발생했습니다: {err_str}"
            st.error(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})

# ── 면책 고지 ──
if st.session_state.messages:
    st.markdown("""
    <div class="disclaimer">
        ⚖️ <strong>면책 고지</strong>: 본 챗봇의 답변은 참고용이며 법적 효력이 없습니다.
        정확한 판단은 법제 담당 부서와 협의하세요.
    </div>
    """, unsafe_allow_html=True)
