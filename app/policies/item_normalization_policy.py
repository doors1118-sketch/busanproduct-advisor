"""
품목명 정규화 정책.

목적:
- 사용자의 자연어 품목 표현(LED, 엘이디 조명 등)을 업체/상품 API 검색에
  더 안정적인 표준 검색어로 변환한다.
- 답변 생성에는 표준 품목명과 보조 검색어를 함께 제공하여 LLM이 품목을
  과도하게 추정하지 않도록 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass(frozen=True)
class NormalizedItem:
    original: str
    canonical_name: str = ""
    primary_search_term: str = ""
    search_terms: list[str] = field(default_factory=list)
    matched_alias: str = ""
    confidence: float = 0.0
    reason: str = "not_found"

    @property
    def found(self) -> bool:
        return bool(self.canonical_name and self.primary_search_term)


_ITEM_SYNONYM_GROUPS: list[dict] = [
    {
        "canonical_name": "LED 조명",
        "primary_search_term": "LED",
        "search_terms": ["LED 조명", "LED조명", "LED", "엘이디 조명", "엘이디조명", "LED 등기구", "LED등"],
        "aliases": [
            "led 조명",
            "led조명",
            "led",
            "엘이디 조명",
            "엘이디조명",
            "엘이디",
            "led 등기구",
            "led등기구",
            "led 등",
            "led등",
        ],
    },
    {
        "canonical_name": "CCTV",
        "primary_search_term": "CCTV",
        "search_terms": ["CCTV", "영상감시장치", "감시카메라", "보안카메라", "보안용카메라"],
        "aliases": ["cctv", "씨씨티비", "영상감시장치", "감시카메라", "보안카메라", "보안용카메라"],
    },
    {
        "canonical_name": "컴퓨터",
        "primary_search_term": "데스크톱컴퓨터",
        "search_terms": ["데스크톱컴퓨터", "노트북컴퓨터", "컴퓨터", "데스크톱", "PC", "피씨"],
        "aliases": ["컴퓨터", "데스크톱", "데스크탑", "pc", "피씨"],
    },
    {
        "canonical_name": "노트북",
        "primary_search_term": "노트북",
        "search_terms": ["노트북컴퓨터", "노트북", "랩톱", "휴대용 컴퓨터"],
        "aliases": ["노트북", "랩톱", "랩탑", "휴대용 컴퓨터"],
    },
    {
        "canonical_name": "프린터",
        "primary_search_term": "프린터",
        "search_terms": ["프린터", "프린터기", "인쇄기"],
        "aliases": ["프린터", "프린터기", "인쇄기"],
    },
    {
        "canonical_name": "복사기",
        "primary_search_term": "복사기",
        "search_terms": ["복사기", "복합기", "디지털복합기"],
        "aliases": ["복사기", "복합기", "디지털 복합기", "디지털복합기"],
    },
    {
        "canonical_name": "냉난방기",
        "primary_search_term": "냉난방기",
        "search_terms": ["냉난방기", "냉난방", "에어컨", "공기조화기"],
        "aliases": ["냉난방기", "냉난방", "에어컨", "공기조화기"],
    },
    {
        "canonical_name": "가구",
        "primary_search_term": "가구",
        "search_terms": ["가구", "책상", "의자", "사무용가구"],
        "aliases": ["가구", "책상", "의자", "사무용 가구", "사무용가구"],
    },
    {
        "canonical_name": "캐비닛",
        "primary_search_term": "캐비닛",
        "search_terms": ["캐비닛", "문서보관함", "보관함", "수납장"],
        "aliases": ["캐비닛", "캐비넷", "문서보관 캐비닛", "문서보관함", "보관함", "수납장"],
    },
    {
        "canonical_name": "서버",
        "primary_search_term": "서버",
        "search_terms": ["서버", "전산서버", "서버장비"],
        "aliases": ["서버", "전산 서버", "전산서버", "서버장비"],
    },
    {
        "canonical_name": "소프트웨어",
        "primary_search_term": "소프트웨어",
        "search_terms": ["소프트웨어", "SW", "상용소프트웨어", "패키지소프트웨어", "보안소프트웨어"],
        "aliases": [
            "소프트웨어",
            "sw",
            "상용 소프트웨어",
            "상용소프트웨어",
            "패키지 소프트웨어",
            "패키지소프트웨어",
            "보안 소프트웨어",
            "보안소프트웨어",
            "보안 sw",
            "보안sw",
            "백신",
            "백신 프로그램",
            "안티바이러스",
            "정보보호",
            "방화벽",
        ],
        "negative_contexts": ["예방접종", "접종", "의약품", "의료용", "병원백신"],
    },
    {
        "canonical_name": "주방기기",
        "primary_search_term": "주방기기",
        "search_terms": ["주방기기", "급식실", "조리기기", "조리대"],
        "aliases": ["주방기기", "주방 기기", "급식실", "조리기기", "조리 기기", "조리대"],
    },
    {
        "canonical_name": "레미콘",
        "primary_search_term": "레미콘",
        "search_terms": ["레미콘", "ready mixed concrete"],
        "aliases": ["레미콘", "ready mixed concrete", "ready-mixed concrete", "readymixedconcrete"],
    },
    {
        "canonical_name": "아스콘",
        "primary_search_term": "아스팔트콘크리트",
        "search_terms": ["아스팔트콘크리트", "아스콘", "순환상온아스팔트콘크리트"],
        "aliases": ["아스콘", "아스팔트콘크리트", "아스팔트 콘크리트", "아스팔트"],
    },
    {
        "canonical_name": "스텐밴드",
        "primary_search_term": "스텐밴드",
        "search_terms": ["스텐밴드", "스테인리스밴드", "스테인리스 밴드"],
        "aliases": ["스텐밴드", "스텐 밴드", "스텐레스밴드", "스테인리스밴드", "스테인리스 밴드"],
    },
    {
        "canonical_name": "각재",
        "primary_search_term": "각재",
        "search_terms": ["각재", "목재각재", "목재 각재"],
        "aliases": ["각재", "목재각재", "목재 각재", "방부각재", "방부 각재"],
    },
    {
        "canonical_name": "복층유리",
        "primary_search_term": "복층유리",
        "search_terms": ["복층유리", "복층 유리", "단열복층유리"],
        "aliases": ["복층유리", "복층 유리", "단열복층유리", "단열 복층유리", "페어글라스"],
    },
    {
        "canonical_name": "소화전",
        "primary_search_term": "소화전",
        "search_terms": ["소화전", "옥내소화전", "옥외소화전"],
        "aliases": ["소화전", "옥내소화전", "옥내 소화전", "옥외소화전", "옥외 소화전"],
    },
    {
        "canonical_name": "도서",
        "primary_search_term": "서적",
        "search_terms": ["서적", "도서", "책", "교재"],
        "aliases": ["서적", "도서", "책", "교재", "도서구매", "책구매"],
    },
    {
        "canonical_name": "우유",
        "primary_search_term": "우유",
        "search_terms": ["우유", "학교우유"],
        "aliases": ["우유", "학교 우유", "학교우유", "급식 우유", "우유급식"],
    },
    {
        "canonical_name": "식육",
        "primary_search_term": "식육류",
        "search_terms": ["식육류", "식육", "축산물", "식육가공품"],
        "aliases": ["식육", "식육류", "축산물", "고기", "급식 식육", "식육 납품"],
    },
    {
        "canonical_name": "채소류",
        "primary_search_term": "채소류",
        "search_terms": ["채소류", "채소", "농산물"],
        "aliases": ["채소", "채소류", "농산물", "급식 채소", "채소 납품"],
    },
    {
        "canonical_name": "과일류",
        "primary_search_term": "과일류",
        "search_terms": ["과일류", "과일"],
        "aliases": ["과일", "과일류", "급식 과일", "과일 납품"],
    },
    {
        "canonical_name": "김치",
        "primary_search_term": "배추김치",
        "search_terms": ["배추김치", "김치"],
        "aliases": ["김치", "배추김치", "급식 김치", "김치 납품"],
    },
    {
        "canonical_name": "청소용역",
        "primary_search_term": "청소용역",
        "search_terms": ["청소용역", "건물청소", "환경미화", "청소"],
        "aliases": ["청소용역", "청소 용역", "건물청소", "환경미화", "청소"],
    },
    {
        "canonical_name": "시설관리용역",
        "primary_search_term": "시설관리",
        "search_terms": ["시설관리", "시설관리용역", "건물관리"],
        "aliases": ["시설관리", "시설 관리", "시설관리용역", "건물관리", "건물 관리"],
    },
    {
        "canonical_name": "경비용역",
        "primary_search_term": "경비용역",
        "search_terms": ["경비용역", "시설경비", "보안경비", "경비"],
        "aliases": ["경비용역", "경비 용역", "시설경비", "보안경비", "경비"],
    },
    {
        "canonical_name": "번역용역",
        "primary_search_term": "번역",
        "search_terms": ["번역", "번역용역", "통번역", "통역번역"],
        "aliases": ["번역", "번역 용역", "번역용역", "통번역", "통역 번역", "통역번역"],
    },
    {
        "canonical_name": "행사용역",
        "primary_search_term": "행사",
        "search_terms": [
            "행사",
            "행사용역",
            "행사기획",
            "행사대행",
            "기타행사기획및대행서비스",
            "이벤트",
            "발대식",
            "기념식",
            "개회식",
            "공연",
            "전시",
            "홍보",
        ],
        "aliases": [
            "행사",
            "행사 용역",
            "행사용역",
            "행사기획",
            "행사 기획",
            "행사대행",
            "행사 대행",
            "기타행사기획및대행서비스",
            "이벤트",
            "발대식",
            "기념식",
            "개회식",
            "공연",
            "전시",
            "홍보",
        ],
    },
    {
        "canonical_name": "건축설계",
        "primary_search_term": "건축설계용역",
        "search_terms": ["건축설계용역", "건축사사무소", "건축설계"],
        "aliases": ["건축설계", "건축 설계", "건축설계용역", "건축사", "건축사사무소"],
    },
    {
        "canonical_name": "디자인서비스",
        "primary_search_term": "디자인서비스",
        "search_terms": ["디자인서비스", "시각디자인", "환경디자인", "산업디자인"],
        "aliases": ["디자인", "디자인서비스", "시각디자인", "시각 디자인", "환경디자인", "환경 디자인", "산업디자인"],
    },
    {
        "canonical_name": "영상제작",
        "primary_search_term": "동영상제작서비스",
        "search_terms": ["동영상제작서비스", "방송영상", "비디오물제작업", "영상제작"],
        "aliases": ["동영상", "동영상 제작", "영상제작", "영상 제작", "방송영상", "방송 영상", "비디오물제작"],
    },
    {
        "canonical_name": "홍보마케팅",
        "primary_search_term": "홍보및마케팅서비스",
        "search_terms": ["홍보및마케팅서비스", "홍보", "마케팅"],
        "aliases": ["홍보", "마케팅", "홍보마케팅", "홍보 마케팅", "홍보 용역", "마케팅 용역"],
    },
    {
        "canonical_name": "간판",
        "primary_search_term": "간판",
        "search_terms": ["간판", "안내판", "옥외광고사업"],
        "aliases": ["간판", "안내판", "사인", "사인물", "표지판", "옥외광고"],
    },
    {
        "canonical_name": "정보시스템",
        "primary_search_term": "정보시스템개발서비스",
        "search_terms": ["정보시스템개발서비스", "정보시스템유지관리서비스", "정보인프라구축서비스", "소프트웨어"],
        "aliases": ["정보시스템", "정보 시스템", "시스템개발", "시스템 개발", "시스템유지관리", "정보시스템 유지관리", "정보인프라"],
    },
    {
        "canonical_name": "디지털콘텐츠",
        "primary_search_term": "디지털콘텐츠개발서비스",
        "search_terms": ["디지털콘텐츠개발서비스", "디지털콘텐츠", "콘텐츠관리소프트웨어"],
        "aliases": ["디지털콘텐츠", "디지털 콘텐츠", "콘텐츠개발", "콘텐츠 개발"],
    },
    {
        "canonical_name": "방송장치",
        "primary_search_term": "구내방송장치",
        "search_terms": ["구내방송장치", "영상.음향및조명장치임대서비스", "방송장치", "음향장비"],
        "aliases": ["구내방송", "구내방송장치", "방송장치", "음향", "음향장비", "조명장비", "음향 조명", "방송설비"],
    },
    {
        "canonical_name": "비디오프로젝터",
        "primary_search_term": "비디오프로젝터",
        "search_terms": ["비디오프로젝터", "프로젝터"],
        "aliases": ["비디오프로젝터", "프로젝터", "빔프로젝터", "빔 프로젝터"],
    },
    {
        "canonical_name": "배전반",
        "primary_search_term": "폐쇄형배전반",
        "search_terms": ["폐쇄형배전반", "분전반", "배전반"],
        "aliases": ["폐쇄형배전반", "수배전반", "배전반", "분전반", "전기배전반"],
    },
    {
        "canonical_name": "무정전전원장치",
        "primary_search_term": "무정전전원장치",
        "search_terms": ["무정전전원장치", "UPS"],
        "aliases": ["무정전전원장치", "무정전 전원장치", "UPS", "유피에스"],
    },
    {
        "canonical_name": "태양광발전장치",
        "primary_search_term": "태양광발전장치",
        "search_terms": ["태양광발전장치", "태양광", "신재생에너지설비"],
        "aliases": ["태양광", "태양광발전", "태양광발전장치", "태양광 발전장치"],
    },
    {
        "canonical_name": "승강기유지보수",
        "primary_search_term": "승강기유지보수서비스",
        "search_terms": ["승강기유지보수서비스", "승강기 유지관리업", "승강기"],
        "aliases": ["승강기", "엘리베이터", "승강기 유지보수", "승강기유지보수", "승강기 유지관리"],
    },
    {
        "canonical_name": "방역소독",
        "primary_search_term": "방역서비스",
        "search_terms": ["방역서비스", "소독업", "소독", "살균제"],
        "aliases": ["방역", "방역서비스", "소독", "소독업", "방역소독", "소독업체", "살균"],
    },
    {
        "canonical_name": "폐기물",
        "primary_search_term": "폐기물수집·운반업",
        "search_terms": ["폐기물수집·운반업", "건설폐기물 수집·운반업", "폐기물"],
        "aliases": ["폐기물", "폐기물 수집", "폐기물 운반", "폐기물 수집 운반", "건설폐기물", "건설 폐기물"],
    },
    {
        "canonical_name": "지질조사",
        "primary_search_term": "지질연구조사서비스",
        "search_terms": ["지질연구조사서비스", "엔지니어링사업(토질, 지질)", "지질조사", "토질조사"],
        "aliases": ["지질조사", "지질 조사", "토질조사", "토질 지질", "지질연구"],
    },
    {
        "canonical_name": "측량",
        "primary_search_term": "측량업(기타-일반측량업)",
        "search_terms": ["측량업(기타-일반측량업)", "측량", "공공측량"],
        "aliases": ["측량", "측량용역", "측량 용역", "공공측량", "일반측량"],
    },
    {
        "canonical_name": "원가계산",
        "primary_search_term": "원가계산용역",
        "search_terms": ["원가계산용역", "원가계산용역기관", "원가검토기관"],
        "aliases": ["원가계산", "원가 계산", "원가계산 용역", "원가검토", "원가 검토"],
    },
    {
        "canonical_name": "법무서비스",
        "primary_search_term": "법무서비스",
        "search_terms": ["법무서비스", "법무사업(사무소)"],
        "aliases": ["법무", "법무서비스", "법무 서비스", "법무사"],
    },
    {
        "canonical_name": "여행전세버스",
        "primary_search_term": "국내여행업",
        "search_terms": ["국내여행업", "종합여행업", "전세버스", "여객자동차운수사업"],
        "aliases": ["여행", "국내여행", "국내여행업", "종합여행업", "전세버스", "전세 버스", "버스 임차"],
    },
    {
        "canonical_name": "피복",
        "primary_search_term": "남자근무복",
        "search_terms": ["남자근무복", "남자작업복", "근무복", "작업복"],
        "aliases": ["근무복", "작업복", "피복", "유니폼", "근무복 구매", "작업복 구매"],
    },
    {
        "canonical_name": "안전화",
        "primary_search_term": "안전화",
        "search_terms": ["안전화", "장갑"],
        "aliases": ["안전화", "안전 신발", "안전용품", "안전장갑"],
    },
    {
        "canonical_name": "마스크",
        "primary_search_term": "보건용마스크",
        "search_terms": ["보건용마스크", "일반마스크", "마스크"],
        "aliases": ["마스크", "보건용마스크", "보건용 마스크", "일반마스크"],
    },
    {
        "canonical_name": "손소독제",
        "primary_search_term": "손소독제",
        "search_terms": ["손소독제", "살균제"],
        "aliases": ["손소독제", "손 소독제", "소독제"],
    },
    {
        "canonical_name": "복사용지",
        "primary_search_term": "프린트및복사용지",
        "search_terms": ["프린트및복사용지", "복사용지", "프린트용지"],
        "aliases": ["복사용지", "복사 용지", "프린트용지", "프린터용지", "A4용지", "에이포용지"],
    },
    {
        "canonical_name": "토너",
        "primary_search_term": "정품토너",
        "search_terms": ["정품토너", "토너"],
        "aliases": ["토너", "정품토너", "프린터 토너"],
    },
    {
        "canonical_name": "드론",
        "primary_search_term": "드론",
        "search_terms": ["드론", "초경량비행장치사용사업"],
        "aliases": ["드론", "무인기", "초경량비행장치"],
    },
    {
        "canonical_name": "전기공사",
        "primary_search_term": "전기공사",
        "search_terms": ["전기공사", "전기공사업"],
        "aliases": ["전기공사", "전기 공사", "전기공사업"],
    },
    {
        "canonical_name": "소방공사",
        "primary_search_term": "소방공사",
        "search_terms": ["소방공사", "소방시설공사", "소방시설업"],
        "aliases": ["소방공사", "소방 공사", "소방시설공사", "소방시설 공사", "소방시설업"],
    },
    {
        "canonical_name": "정보통신공사",
        "primary_search_term": "정보통신공사",
        "search_terms": ["정보통신공사", "통신공사", "정보통신공사업"],
        "aliases": ["정보통신공사", "정보통신 공사", "통신공사", "정보통신공사업"],
    },
    {
        "canonical_name": "조경공사",
        "primary_search_term": "조경공사",
        "search_terms": ["조경공사", "조경식재공사", "조경식재·시설물공사", "조경공사업", "조경식재·시설물공사업"],
        "aliases": [
            "조경공사",
            "조경 공사",
            "조경식재공사",
            "조경 식재 공사",
            "조경시설물공사",
            "조경 시설물 공사",
            "조경식재·시설물공사",
            "조경식재 시설물 공사",
            "조경공사업",
            "조경식재·시설물공사업",
        ],
    },
]


_PURCHASE_WORDS = [
    "구매", "구입", "사려고", "살려고", "사려", "사는", "납품", "발주", "계약",
    "수의계약", "입찰", "종합쇼핑몰", "나라장터", "부산업체", "지역업체", "업체",
    "추천", "찾아", "가능", "검토", "방법", "활용", "하려고", "해야", "어떻게",
    "맡기려고", "맡길", "진행", "추진", "해야", "한다",
]


_PREFERRED_ITEM_QUERY_OVERRIDES: list[dict] = [
    {
        "canonical_name": "홍보마케팅",
        "primary_search_term": "홍보및마케팅서비스",
        "search_terms": ["홍보및마케팅서비스", "광고대행업", "홍보", "마케팅"],
        "aliases": ["홍보마케팅", "홍보 마케팅", "홍보 용역", "마케팅 용역"],
    },
    {
        "canonical_name": "음향조명임대",
        "primary_search_term": "영상.음향및조명장치임대서비스",
        "search_terms": ["영상.음향및조명장치임대서비스", "음향장비", "조명장비"],
        "aliases": ["음향 조명", "음향조명", "음향 장비 임대", "조명 장비 임대", "음향 조명 장비 임대", "무대음향", "무대조명"],
    },
    {
        "canonical_name": "손소독제",
        "primary_search_term": "손소독제",
        "search_terms": ["손소독제", "살균제"],
        "aliases": ["손소독제", "손 소독제", "손세정제", "손 세정제"],
    },
]


def _compact(value: str) -> str:
    return re.sub(r"[\s\-_·ㆍ]+", "", (value or "").lower())


def _alias_matches(alias: str, text: str, compact_text: str) -> bool:
    compact_alias = _compact(alias)
    if not compact_alias:
        return False
    if len(compact_alias) == 1:
        # 단문 품목어는 "정책기업"의 "책"처럼 일반 단어 내부에서 오탐되기 쉽다.
        return re.search(rf"(?<![가-힣A-Za-z0-9]){re.escape(compact_alias)}(?![가-힣A-Za-z0-9])", text.lower()) is not None
    return compact_alias in compact_text


def _is_context_only_alias(group: dict, alias: str, text: str, compact_text: str) -> bool:
    compact_alias = _compact(alias)
    if group.get("canonical_name") == "도서" and compact_alias == "도서" and "도서관" in compact_text:
        explicit_book_terms = (
            "도서구매",
            "도서구입",
            "도서납품",
            "도서업체",
            "도서계약",
            "서적",
            "교재",
            "책구매",
            "책구입",
        )
        return not any(term in compact_text for term in explicit_book_terms)
    return False


def normalize_item_query(user_message: str, router_item: str | None = None) -> NormalizedItem:
    """사용자 질문/라우터 슬롯에서 표준 품목명을 찾는다."""
    original = (router_item or user_message or "").strip()
    text = f"{router_item or ''} {user_message or ''}".strip()
    compact_text = _compact(text)

    for group in _PREFERRED_ITEM_QUERY_OVERRIDES:
        aliases = list(group["aliases"]) + list(group["search_terms"])
        for alias in sorted(aliases, key=len, reverse=True):
            if _compact(alias) and _compact(alias) in compact_text:
                return NormalizedItem(
                    original=original,
                    canonical_name=group["canonical_name"],
                    primary_search_term=group["primary_search_term"],
                    search_terms=list(dict.fromkeys(group["search_terms"])),
                    matched_alias=alias,
                    confidence=0.98 if router_item else 0.94,
                    reason="preferred_alias",
                )

    for group in _ITEM_SYNONYM_GROUPS:
        if any(_compact(context) and _compact(context) in compact_text for context in group.get("negative_contexts", [])):
            continue
        aliases = list(group["aliases"]) + list(group["search_terms"])
        for alias in sorted(aliases, key=len, reverse=True):
            if _alias_matches(alias, text, compact_text):
                if _is_context_only_alias(group, alias, text, compact_text):
                    continue
                return NormalizedItem(
                    original=original,
                    canonical_name=group["canonical_name"],
                    primary_search_term=group["primary_search_term"],
                    search_terms=list(dict.fromkeys(group["search_terms"])),
                    matched_alias=alias,
                    confidence=0.98 if router_item else 0.92,
                    reason="known_alias",
                )

    # 라우터가 이미 구체 품목을 준 경우는 사전 미등록 품목이라도 검색어로 사용한다.
    if router_item and len(_compact(router_item)) >= 2:
        clean = router_item.strip()
        return NormalizedItem(
            original=original,
            canonical_name=clean,
            primary_search_term=clean,
            search_terms=[clean],
            matched_alias=clean,
            confidence=0.75,
            reason="router_item_fallback",
        )

    return NormalizedItem(original=original)


def extract_item_keyword_with_synonyms(user_message: str) -> str:
    """기존 레거시 추출기의 대체/보완용 API 검색어 반환."""
    normalized = normalize_item_query(user_message)
    if normalized.found:
        return normalized.primary_search_term

    text = user_message or ""
    text = re.sub(r"\d+[,\d]*(억|천만|백만|만)?원?", " ", text)
    for word in _PURCHASE_WORDS:
        text = text.replace(word, " ")
    text = re.sub(r"[?!.]", " ", text)
    text = re.sub(r"(은|는|이|가|을|를|로|으로|랑|하고|에서)$", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip()
    return text
