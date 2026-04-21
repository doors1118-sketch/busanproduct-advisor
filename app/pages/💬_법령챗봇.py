"""
💬 법령챗봇 — AI 법령 해석 상담
지역상생 조달 어드바이저의 핵심 기능 2.
"""
import sys
import os

# app 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from gemini_engine import chat
from system_prompt import EXAMPLE_QUESTIONS

# ── 페이지 설정 ──
st.set_page_config(
    page_title="법령챗봇 | 지역상생 조달 어드바이저",
    page_icon="💬",
    layout="wide",
)

# ── 스타일 ──
st.markdown("""
<style>
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
        margin-bottom: 1.5rem;
    }
    .example-btn {
        margin: 0.2rem;
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
with st.sidebar:
    st.markdown("### 💬 AI 법령 챗봇")
    st.caption("법제처 API + Gemini 기반")
    st.markdown("---")
    st.markdown("""
    **사용 방법**
    1. 계약·조달 관련 질문 입력
    2. AI가 법제처 API에서 법령 검색
    3. 법적 근거와 함께 답변 제공
    """)
    st.markdown("---")
    st.markdown("**📌 답변 구조**")
    st.markdown("""
    - 📌 결론
    - 📜 법적 근거
    - 💼 실무 적용
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
st.markdown('<div class="chat-header">💬 AI 법령 해석 챗봇</div>', unsafe_allow_html=True)
st.markdown('<div class="chat-sub">계약·조달 법령에 대해 질문하면, 법제처 API에서 법령 원문을 검색하여 답변합니다.</div>', unsafe_allow_html=True)

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
    # 사용자 메시지 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(user_input)

    # AI 답변 생성
    with st.chat_message("assistant", avatar="⚖️"):
        with st.spinner("법령을 검색하고 해석 중입니다..."):
            try:
                answer, updated_history = chat(
                    user_input,
                    st.session_state.chat_history
                )
                st.session_state.chat_history = updated_history
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                error_msg = f"⚠️ 오류가 발생했습니다: {str(e)}\n\n법제처 API IP 등록 여부를 확인해주세요."
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
