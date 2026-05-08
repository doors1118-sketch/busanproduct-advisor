from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "app" / "data" / "practice_manual_cards.json"
REPORT_PATH = ROOT / "app" / "data" / "practice_manual_ingest_report.json"

SOURCE_PDFS = [
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\(25.9.15)지방계약 실무 매뉴얼.pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\「우수조달물품+지정+및+3자단가계약+실무매뉴얼」 (1).pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\1. 공사계약 매뉴얼-내지(3교).pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\2. 용역계약 메뉴얼-내지(3교).pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\2025 조합추천수의계약 제도 안내자료.pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\2025년도 지방계약 우수사례집.pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\감사원_공공계약 실무가이드 2024년 개정판_발간번호.pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\지방자치단체를 당사자로 하는 계약에 관한 법률 시행령의 수의계약 등 한시적 특례 적용기간에 관한 고시(행정안전부고시)(제2025-72호)(20260101).pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\(1권) 2025 공공구매제도 실무가이드.pdf"),
    Path(r"C:\Users\doors\OneDrive\바탕 화면\업무 지침\(2권) 중소기업자간 경쟁제품 해설(609개 품목).pdf"),
]

TOPICS: list[dict[str, Any]] = [
    {
        "topic": "direct_contract",
        "title": "수의계약 실무 검토",
        "keywords": ["수의계약", "1인 견적", "2인 이상 견적", "분할발주", "계약상대자"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "수의계약은 가능 여부와 1인 견적 가능 여부를 분리하고, 품목·금액·기관유형·정책기업 요건을 함께 확인해야 한다.",
        "checklist": ["수의계약 사유와 견적 방식 분리", "추정가격 산정 기준 확인", "분할발주 금지 여부 확인", "정책기업·직접생산·인증 유효성 확인"],
    },
    {
        "topic": "regional_restriction",
        "title": "지역제한경쟁입찰 실무 검토",
        "keywords": ["지역제한", "지역제한경쟁", "본점 소재지", "입찰참가자격", "제한경쟁"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "지역제한은 금액 기준뿐 아니라 공종·업종·본점 소재지·지역업체 수·부당제한 가능성을 함께 확인해야 한다.",
        "checklist": ["최신 금액 기준은 source map에서 확인", "본점 소재지 기준 확인", "지역업체 수와 경쟁성 확인", "과도한 참가자격 제한 여부 확인"],
    },
    {
        "topic": "regional_joint_contract",
        "title": "지역의무공동도급 실무 검토",
        "keywords": ["지역의무", "의무공동", "공동도급", "공동수급", "지역업체 참여비율"],
        "contract_objects": ["construction"],
        "summary": "지역의무공동도급은 공사에서 지역업체 참여를 확보하는 장치이며, 적용 대상과 지역업체 수·시공능력을 먼저 확인해야 한다.",
        "checklist": ["공사 계약인지 확인", "지역업체 참여비율은 source map에서 확인", "지역업체 수와 시공능력 확인", "특정 업체 하도급 강제 금지"],
    },
    {
        "topic": "local_company_points",
        "title": "지역업체 참여도·가점 실무 검토",
        "keywords": ["지역업체 참여도", "지역업체 가점", "신인도", "적격심사", "평가항목", "제안서평가"],
        "contract_objects": ["service", "construction", "goods"],
        "summary": "지역업체 우대는 기관유형과 평가방식에 따라 다르므로 가점, 참여도, 공동계약, 공고 평가항목을 구분해야 한다.",
        "checklist": ["기관유형 확인", "적격심사·종합평가·협상계약 구분", "점수·비율은 source map에서 확인", "공고문 평가항목 반영 가능성 확인"],
    },
    {
        "topic": "mas_shopping_mall",
        "title": "종합쇼핑몰·MAS·제3자단가 실무 검토",
        "keywords": ["종합쇼핑몰", "MAS", "다수공급자", "2단계 경쟁", "제3자단가", "납품요구"],
        "contract_objects": ["goods"],
        "summary": "쇼핑몰 구매는 등록상품·계약상태·납품가능지역·2단계 경쟁 대상 여부를 확인하고, 지역업체 우대는 정당한 평가요소와 연결해야 한다.",
        "checklist": ["쇼핑몰 등록 및 계약상태 확인", "규격과 세부품명 일치 확인", "2단계 경쟁 대상 여부 확인", "납기·A/S 등 정당한 평가요소 확인"],
    },
    {
        "topic": "excellent_procurement",
        "title": "우수조달물품·기술개발제품 실무 검토",
        "keywords": ["우수조달", "기술개발제품", "성능인증", "우선구매", "인증제품", "NEP", "NET"],
        "contract_objects": ["goods"],
        "summary": "우수조달·기술개발제품은 지정·인증 유효기간과 제품명 일치, 조달등록 여부를 확인한 뒤 구매경로로 연결해야 한다.",
        "checklist": ["지정·인증 유효기간 확인", "구매 품목과 지정 제품 일치 확인", "조달등록·쇼핑몰 등록 확인", "수의계약 특례는 최신 법령 기준으로 재검증"],
    },
    {
        "topic": "sme_competition",
        "title": "중소기업자간 경쟁제품 실무 검토",
        "keywords": ["중소기업자간 경쟁제품", "중기간", "직접생산", "공공구매", "판로지원", "세부품명"],
        "contract_objects": ["goods"],
        "summary": "중소기업자간 경쟁제품은 세부품명과 직접생산확인, 예외 구매 가능성을 확인해야 지역상품 구매전략에 안정적으로 반영된다.",
        "checklist": ["세부품명과 경쟁제품 해당 여부 확인", "직접생산확인증명서 확인", "예외 구매 가능성 확인", "지역업체 후보의 생산·납품 가능성 확인"],
    },
    {
        "topic": "policy_company_purchase",
        "title": "정책기업 공공구매 실무 검토",
        "keywords": ["여성기업", "장애인기업", "사회적기업", "소기업", "소상공인", "창업기업", "공공구매"],
        "contract_objects": ["goods", "service"],
        "summary": "정책기업 구매는 기업유형별 자격과 유효기간, 수의계약·1인견적 기준을 분리해 검토해야 한다.",
        "checklist": ["정책기업 유형과 증빙 확인", "유효기간 확인", "금액·견적 기준은 source map에서 확인", "실제 수행 또는 납품 가능성 확인"],
    },
    {
        "topic": "construction_contract",
        "title": "공사계약 실무 검토",
        "keywords": ["공사계약", "종합공사", "전문공사", "전기공사", "정보통신공사", "소방공사", "분리발주"],
        "contract_objects": ["construction"],
        "summary": "공사는 공종 구분, 면허, 분리발주, 지역제한, 공동도급을 함께 검토해야 하며 물품·용역과 다른 경로로 판단해야 한다.",
        "checklist": ["공종과 면허 구분", "분리발주 대상 여부 확인", "지역제한·공동도급 적용 가능성 확인", "설계서·내역서 기준 확인"],
    },
    {
        "topic": "service_contract",
        "title": "용역계약 실무 검토",
        "keywords": ["용역계약", "기술용역", "학술용역", "일반용역", "청소용역", "협상에 의한 계약", "과업지시서"],
        "contract_objects": ["service"],
        "summary": "용역은 과업 범위, 평가방식, 면허·인력 요건, 지역업체 참여도 반영 가능성을 함께 검토해야 한다.",
        "checklist": ["용역 종류 구분", "과업지시서와 평가방식 확인", "면허·인력·실적 요건 확인", "지역업체 참여도 반영 가능성 확인"],
    },
    {
        "topic": "audit_risk",
        "title": "감사·분쟁 리스크 실무 검토",
        "keywords": ["감사", "분쟁", "부당", "특혜", "제한", "위법", "주의사항", "감사원"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "지역상품 구매지원은 특정 업체 특혜나 과도한 제한으로 보이지 않도록 근거, 시장조사, 평가항목, 확인 절차를 문서화해야 한다.",
        "checklist": ["특정업체 지목 금지", "시장조사 근거 보관", "평가항목의 객관성 확보", "예외·특례 적용 사유 문서화"],
    },
]


def normalize_space(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def sanitize_numeric_standards(text: str) -> str:
    text = normalize_space(text)
    text = re.sub(r"\d+(?:\.\d+)?\s*억\s*(?:\d+(?:,\d+)?\s*)?만?\s*원?", "[금액기준은 최신 법령/source map 확인]", text)
    text = re.sub(r"\d+(?:,\d+)?\s*(?:천만|백만|만)\s*원", "[금액기준은 최신 법령/source map 확인]", text)
    text = re.sub(r"\d{1,3}(?:\.\d+)?\s*%", "[비율기준은 최신 법령/source map 확인]", text)
    text = re.sub(r"20\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.?", "[시행일은 최신 DB 확인]", text)
    return text


def extract_pages(pdf_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    info = {
        "source": pdf_path.name,
        "exists": pdf_path.exists(),
        "page_count": 0,
        "text_pages": 0,
        "extractable": False,
    }
    if not pdf_path.exists():
        return [], info
    pages: list[dict[str, Any]] = []
    with fitz.open(str(pdf_path)) as doc:
        info["page_count"] = doc.page_count
        for idx in range(doc.page_count):
            text = doc.load_page(idx).get_text("text")
            text = normalize_space(text)
            if len(text) < 80:
                continue
            pages.append({"source": pdf_path.name, "page": idx + 1, "text": text})
    info["text_pages"] = len(pages)
    info["extractable"] = bool(pages)
    return pages, info


def score_page(text: str, keywords: list[str]) -> int:
    return sum(3 if kw in text else 0 for kw in keywords) + min(text.count("확인"), 5)


def build_cards(all_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for topic in TOPICS:
        scored = []
        for page in all_pages:
            score = score_page(page["text"], topic["keywords"])
            if score > 0:
                scored.append((score, page))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [page for _, page in scored[:4]]
        notes = []
        sources = []
        for page in selected:
            snippet = sanitize_numeric_standards(page["text"][:900])
            if snippet:
                notes.append(snippet[:450])
                sources.append({"source": page["source"], "page": page["page"]})
        cards.append({
            "card_id": f"practice:{topic['topic']}",
            "topic": topic["topic"],
            "title": topic["title"],
            "authority_level": "practice_guidance",
            "numeric_use_allowed": False,
            "allowed_usage": ["procedure_explanation", "checklist", "practical_caution", "answer_tone_support"],
            "blocked_usage": ["current_threshold", "legal_effective_date", "final_legal_conclusion"],
            "contract_objects": topic["contract_objects"],
            "agency_types": ["local_government", "national_agency", "public_corporation", "invested_institution"],
            "keywords": topic["keywords"],
            "summary": topic["summary"],
            "checklist": topic["checklist"],
            "manual_notes": notes,
            "sources": sources,
            "source_status": "manual_card_generated" if sources else "manual_source_not_found",
        })
    return cards


def main() -> None:
    all_pages: list[dict[str, Any]] = []
    source_report = []
    for pdf in SOURCE_PDFS:
        pages, info = extract_pages(pdf)
        source_report.append(info)
        all_pages.extend(pages)

    cards = build_cards(all_pages)
    payload = {
        "schema_version": "practice_manual_cards_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "usage_policy": {
            "priority": "legal_db_and_source_map_first",
            "runtime_behavior": "precomputed_cards_only",
            "numeric_standard_policy": "manual numbers are masked and must not override source_map.resolved_value",
            "max_runtime_cards": 5,
        },
        "cards": cards,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "generated_at": payload["generated_at"],
        "source_count": len(source_report),
        "extractable_sources": sum(1 for row in source_report if row["extractable"]),
        "card_count": len(cards),
        "sources": source_report,
        "output": str(OUT_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
