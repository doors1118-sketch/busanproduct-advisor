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
        "search_terms": ["CCTV", "영상감시장치", "감시카메라", "보안카메라"],
        "aliases": ["cctv", "씨씨티비", "영상감시장치", "감시카메라", "보안카메라"],
    },
    {
        "canonical_name": "컴퓨터",
        "primary_search_term": "컴퓨터",
        "search_terms": ["컴퓨터", "데스크톱", "PC", "피씨"],
        "aliases": ["컴퓨터", "데스크톱", "데스크탑", "pc", "피씨"],
    },
    {
        "canonical_name": "노트북",
        "primary_search_term": "노트북",
        "search_terms": ["노트북", "랩톱", "휴대용 컴퓨터"],
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
        "canonical_name": "서버",
        "primary_search_term": "서버",
        "search_terms": ["서버", "전산서버", "서버장비"],
        "aliases": ["서버", "전산 서버", "전산서버", "서버장비"],
    },
    {
        "canonical_name": "소프트웨어",
        "primary_search_term": "소프트웨어",
        "search_terms": ["소프트웨어", "SW", "상용소프트웨어", "패키지소프트웨어"],
        "aliases": ["소프트웨어", "sw", "상용 소프트웨어", "상용소프트웨어", "패키지 소프트웨어", "패키지소프트웨어"],
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
        "search_terms": ["시설관리", "시설관리용역", "건물관리", "유지관리"],
        "aliases": ["시설관리", "시설 관리", "시설관리용역", "건물관리", "유지관리", "유지 관리"],
    },
    {
        "canonical_name": "경비용역",
        "primary_search_term": "경비용역",
        "search_terms": ["경비용역", "시설경비", "보안경비", "경비"],
        "aliases": ["경비용역", "경비 용역", "시설경비", "보안경비", "경비"],
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
]


_PURCHASE_WORDS = [
    "구매", "구입", "사려고", "살려고", "사려", "사는", "납품", "발주", "계약",
    "수의계약", "입찰", "종합쇼핑몰", "나라장터", "부산업체", "지역업체", "업체",
    "추천", "찾아", "가능", "검토", "방법", "활용", "하려고", "해야", "어떻게",
    "맡기려고", "맡길", "진행", "추진", "해야", "한다",
]


def _compact(value: str) -> str:
    return re.sub(r"[\s\-_·ㆍ]+", "", (value or "").lower())


def normalize_item_query(user_message: str, router_item: str | None = None) -> NormalizedItem:
    """사용자 질문/라우터 슬롯에서 표준 품목명을 찾는다."""
    original = (router_item or user_message or "").strip()
    text = f"{router_item or ''} {user_message or ''}".strip()
    compact_text = _compact(text)

    for group in _ITEM_SYNONYM_GROUPS:
        aliases = list(group["aliases"]) + list(group["search_terms"])
        for alias in sorted(aliases, key=len, reverse=True):
            if _compact(alias) and _compact(alias) in compact_text:
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
