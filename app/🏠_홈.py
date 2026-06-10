"""지역상품 구매확대 지원 챗봇 홈."""

from pathlib import Path

import streamlit as st


APP_NAME = "지역상품 구매확대 지원 챗봇"

st.set_page_config(page_title=APP_NAME, layout="wide", initial_sidebar_state="expanded")


st.markdown(
    """
    <style>
    :root {
        --ink: #172033;
        --muted: #667085;
        --line: #d8dee8;
        --paper: #f6f8fb;
        --blue: #245fc7;
        --teal: #087f7a;
        --amber: #a05a00;
    }

    .stApp {
        background: #f6f8fb;
    }

    .block-container {
        max-width: 1080px;
        padding-top: 1.4rem;
        padding-bottom: 2.5rem;
    }

    [data-testid="stSidebar"] {
        background: rgba(255,255,255,0.9);
        border-right: 1px solid var(--line);
    }

    .home-head {
        align-items: flex-end;
        border-bottom: 1px solid var(--line);
        display: flex;
        gap: 1rem;
        justify-content: space-between;
        margin-bottom: 1.4rem;
        padding-bottom: 1rem;
    }

    .home-title {
        color: var(--ink);
        font-size: 1.85rem;
        font-weight: 780;
        letter-spacing: 0;
        line-height: 1.22;
        margin: 0;
    }

    .home-sub {
        color: var(--muted);
        font-size: 0.98rem;
        line-height: 1.5;
        margin-top: 0.45rem;
        max-width: 720px;
    }

    .home-badge {
        background: rgba(255,255,255,0.88);
        border: 1px solid var(--line);
        border-radius: 999px;
        color: #344054;
        font-size: 0.82rem;
        padding: 0.42rem 0.76rem;
        white-space: nowrap;
    }

    .work-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.8rem;
        margin: 1rem 0 1.25rem;
    }

    .work-item {
        background: rgba(255,255,255,0.82);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 1rem;
    }

    .work-item strong {
        color: var(--ink);
        display: block;
        font-size: 0.98rem;
        margin-bottom: 0.28rem;
    }

    .work-item span {
        color: var(--muted);
        display: block;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .note {
        background: rgba(255,248,229,0.9);
        border: 1px solid #e7c968;
        border-radius: 8px;
        color: #5c4300;
        font-size: 0.9rem;
        line-height: 1.5;
        margin-top: 1.2rem;
        padding: 0.75rem 0.85rem;
    }

    .sidebar-title {
        color: var(--ink);
        font-size: 1.04rem;
        font-weight: 780;
        line-height: 1.36;
        margin-top: 0.7rem;
    }

    .sidebar-caption {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.45;
        margin: 0.28rem 0 0.85rem;
    }

    .stButton > button,
    .stLinkButton > a {
        border-radius: 7px;
        min-height: 2.35rem;
    }

    @media (max-width: 860px) {
        .home-head {
            align-items: flex-start;
            flex-direction: column;
        }
        .work-grid {
            grid-template-columns: 1fr;
        }
        .home-title {
            font-size: 1.45rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.image("https://www.busan.go.kr/cmm/img/busan_logo.png", width=168)
    st.markdown(
        f"""
        <div class="sidebar-title">{APP_NAME}</div>
        <div class="sidebar-caption">부산 지역상품 구매 확대 업무를 지원하는 내부 참고 도구</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.page_link("🏠_홈.py", label="홈")
    st.page_link("pages/vendor_search.py", label="업체추천")
    st.page_link("pages/💬_법령챗봇.py", label="계약검토")
    if (Path(__file__).parent / "pages" / "📖_메뉴얼.py").exists():
        st.page_link("pages/📖_메뉴얼.py", label="메뉴얼")
    st.divider()
    st.link_button("나라장터", "https://www.g2b.go.kr", use_container_width=True)
    st.link_button("법제처 국가법령정보센터", "https://www.law.go.kr", use_container_width=True)


st.markdown(
    f"""
    <div class="home-head">
        <div>
            <h1 class="home-title">{APP_NAME}</h1>
            <div class="home-sub">구매담당자가 계약 방법, 금액 기준, 지역업체 활용 가능성을 빠르게 검토할 수 있도록 구성한 업무 지원 화면입니다.</div>
        </div>
        <div class="home-badge">업무 지원용 참고 시스템</div>
    </div>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="work-grid">
        <div class="work-item">
            <strong>질문 입력</strong>
            <span>기관 유형을 선택하고 계약·조달 질문을 자연어로 입력합니다.</span>
        </div>
        <div class="work-item">
            <strong>근거 검토</strong>
            <span>내부 기준, 검색 결과, 라우팅 결과를 바탕으로 답변을 생성합니다.</span>
        </div>
        <div class="work-item">
            <strong>업무 반영</strong>
            <span>최종 처리 전 원문 법령과 기관 내부 지침을 확인합니다.</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col_vendor, col_chat, col_manual = st.columns(3)
with col_vendor:
    if st.button("업체추천", type="primary", use_container_width=True):
        st.switch_page("pages/vendor_search.py")
with col_chat:
    if st.button("계약검토", use_container_width=True):
        st.switch_page("pages/💬_법령챗봇.py")
with col_manual:
    manual_page = Path(__file__).parent / "pages" / "📖_메뉴얼.py"
    if st.button("메뉴얼 보기", use_container_width=True, disabled=not manual_page.exists()):
        st.switch_page("pages/📖_메뉴얼.py")

st.markdown(
    """
    <div class="note">
    본 시스템은 구매담당자 업무 지원용 참고 도구입니다. 답변은 법적 효력을 갖지 않으며, 최종 계약 처리 전에는 관련 법령, 예규, 내부 지침을 확인해 주세요.
    </div>
    """,
    unsafe_allow_html=True,
)
