"""
지역상품 구매지원 지능형 업무 매뉴얼
Streamlit 메인 앱
"""
import streamlit as st

st.set_page_config(
    page_title="지역상품 구매지원 매뉴얼",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 사이드바 ──
with st.sidebar:
    st.image("https://www.busan.go.kr/cmm/img/busan_logo.png", width=180)
    st.markdown("---")
    st.markdown("### 🧭 지역상생 조달 어드바이저")
    st.caption("부산광역시 공공조달 모니터링 시스템")
    st.markdown("---")
    st.markdown("""
    **📖 매뉴얼** — 지역업체 계약 가이드  
    **💬 챗봇** — AI 법령 해석 상담  
    """)

# ── 메인 페이지 ──
st.markdown("""
<style>
    .hero-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1e3a5f 0%, #2e86de 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .hero-sub {
        font-size: 1.2rem;
        color: #555;
        margin-bottom: 2rem;
    }
    .card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 16px;
        padding: 2rem;
        border-left: 5px solid #2e86de;
        margin-bottom: 1rem;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 800;
        color: #2e86de;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #666;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">지역상품 구매지원 지능형 업무 매뉴얼</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">계약 담당자를 위한 지역업체 배려 계약 가이드 + AI 법령 챗봇</div>', unsafe_allow_html=True)

# ── 핵심 지표 ──
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("부산시 본청 수주율", "70.6%", "목표 80%↑")
with col2:
    st.metric("국가기관 수주율", "31.6%", "개선 필요")
with col3:
    st.metric("총 발주 금액", "3.7조원", "2025년 기준")
with col4:
    st.metric("관내 등록 업체", "20,000+", "면허 18,678건")

st.markdown("---")

# ── 주요 기능 카드 ──
col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
    <div class="card">
        <h3>📖 인터랙티브 매뉴얼</h3>
        <p>지역업체 계약의 법적 근거, 절차, 체크리스트를 한눈에 확인</p>
        <ul>
            <li>계약방법 추천 도우미</li>
            <li>지역제한 입찰 체크리스트</li>
            <li>수의계약 한도·요건 기준표</li>
            <li>8단계 계약업무 흐름도</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col_b:
    st.markdown("""
    <div class="card">
        <h3>💬 AI 법령 챗봇</h3>
        <p>법제처 API + Korean Law MCP로 법령·판례를 즉시 검색·해석</p>
        <ul>
            <li>자연어 질의응답</li>
            <li>법적 근거 자동 제시</li>
            <li>판례·질의회신 검색</li>
            <li>AI 인용 검증 (환각 방지)</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("© 2026 부산광역시 공공조달 모니터링 시스템 | 본 서비스의 답변은 참고용이며 법적 효력이 없습니다.")
