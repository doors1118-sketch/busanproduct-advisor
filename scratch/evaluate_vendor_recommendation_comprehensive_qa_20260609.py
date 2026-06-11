from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


POSITIVE_MISSING = ("", "없음", "미확인", "확인 필요", "DB 등록정보 없음", "미검증", "미매칭")


def norm(value: Any) -> str:
    return str(value or "").lower().replace(" ", "")


def contains_any(text: str, needles: list[str]) -> bool:
    folded = norm(text)
    return any(norm(needle) in folded for needle in needles)


def is_positive(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return not any(term in text for term in POSITIVE_MISSING if term)


def case(
    case_id: str,
    q: str,
    intent: str,
    must: list[str],
    *,
    budget_krw: int = 50_000_000,
    tags: list[str] | None = None,
    policy: bool = False,
    policy_label: str = "",
    convenience: list[str] | None = None,
    avoid_top1: list[str] | None = None,
    top1_any: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "q": q,
        "intent": intent,
        "must": must,
        "budget_krw": budget_krw,
        "tags": tags or [],
        "policy": policy,
        "policy_label": policy_label,
        "convenience": convenience or [],
        "avoid_top1": avoid_top1 or [],
        "top1_any": top1_any or [],
    }


BASE: list[dict[str, Any]] = [
    case("goods_led", "LED 조명 5천만원 구매 업체 추천", "물품", ["led", "조명"], budget_krw=50_000_000, tags=["baseline"], policy=True, convenience=["shopping_or_mas"]),
    case("goods_cctv", "CCTV 보안카메라 구매 업체", "물품", ["cctv", "카메라", "영상감시"], budget_krw=70_000_000, tags=["baseline"], policy=True),
    case("goods_desktop", "데스크톱 컴퓨터 4천만원 구매 부산업체", "물품", ["컴퓨터", "데스크톱", "데스크탑", "pc"], budget_krw=40_000_000, tags=["baseline"], policy=True, convenience=["shopping_or_mas"]),
    case("goods_notebook", "노트북 구매 업체 추천", "물품", ["노트북", "컴퓨터"], budget_krw=30_000_000, tags=["baseline"], policy=True),
    case("goods_server", "서버 컴퓨터 구매 업체", "물품", ["서버", "컴퓨터"], budget_krw=90_000_000, tags=["baseline"], policy=True),
    case("goods_security_sw", "보안 소프트웨어 구매 업체", "물품", ["소프트웨어", "보안", "sw", "프로그램"], budget_krw=40_000_000, tags=["baseline"], policy=True),
    case("goods_firewall", "방화벽 장비 구매 업체", "물품", ["방화벽", "보안", "장치"], budget_krw=80_000_000, tags=["baseline"], policy=True),
    case("goods_toner", "정품토너 구매 업체 추천", "물품", ["토너"], budget_krw=20_000_000, tags=["baseline"], policy=True, avoid_top1=["축산", "식육", "식품"]),
    case("goods_projector", "비디오프로젝터 구매 업체", "물품", ["프로젝터", "비디오"], budget_krw=45_000_000, tags=["baseline"], policy=True),
    case("goods_drone", "드론 구매 업체", "물품", ["드론"], budget_krw=35_000_000, tags=["baseline"], policy=True),
    case("goods_switchboard", "분전반 구매 업체", "물품", ["분전반", "배전반"], budget_krw=80_000_000, tags=["baseline"], policy=True, convenience=["shopping_or_mas"]),
    case("goods_aircon", "냉난방기 에어컨 구매 부산업체", "물품", ["냉난방", "에어컨", "공기조화"], budget_krw=60_000_000, tags=["baseline"], policy=True),
    case("goods_furniture", "사무용 책상 의자 구매 업체", "물품", ["가구", "책상", "의자"], budget_krw=30_000_000, tags=["baseline"], policy=True),
    case("goods_cabinet", "문서보관 캐비닛 구매 업체", "물품", ["캐비닛", "보관함", "가구"], budget_krw=25_000_000, tags=["baseline"], policy=True),
    case("goods_kitchen", "급식실 주방기기 구매 업체", "물품", ["주방", "급식", "조리"], budget_krw=70_000_000, tags=["baseline"], policy=True),
    case("goods_remicon", "레미콘 구매 부산 업체", "물품", ["레미콘", "콘크리트"], budget_krw=100_000_000, tags=["baseline"], policy=True),
    case("goods_ascon", "아스콘 구매 업체", "물품", ["아스콘", "아스팔트"], budget_krw=100_000_000, tags=["baseline"], policy=True),
    case("goods_elastic", "체육시설 탄성포장재 구매 업체", "물품", ["탄성포장", "포장재"], budget_krw=90_000_000, tags=["baseline"], policy=True),
    case("goods_printing", "홍보물 인쇄 업체 추천", "물품", ["인쇄", "홍보물", "책자", "현수막"], budget_krw=20_000_000, tags=["baseline"], policy=True),
    case("service_event", "발대식 행사 용역 업체 추천", "용역", ["행사", "이벤트", "공연", "전시"], budget_krw=200_000_000, tags=["baseline"]),
    case("service_translation", "번역용역 부산 업체 추천", "용역", ["번역", "통역"], budget_krw=40_000_000, tags=["baseline"]),
    case("service_interpretation", "국제행사 통역 용역 업체", "용역", ["통역", "번역"], budget_krw=35_000_000, tags=["baseline"]),
    case("service_cleaning", "건물 청소용역 부산업체", "용역", ["청소", "환경미화"], budget_krw=70_000_000, tags=["baseline"]),
    case("service_security", "청사 경비용역 부산 업체", "용역", ["경비", "시설경비"], budget_krw=80_000_000, tags=["baseline"]),
    case("service_facility", "시설관리 용역 부산 업체", "용역", ["시설관리", "건물관리", "건물(시설)관리", "유지관리"], budget_krw=120_000_000, tags=["baseline"]),
    case("service_disinfection", "소독 방역 용역 업체", "용역", ["소독", "방역"], budget_krw=30_000_000, tags=["baseline"], avoid_top1=["손소독제", "살균제"]),
    case("service_waste", "폐기물 처리 용역 업체", "용역", ["폐기물"], budget_krw=50_000_000, tags=["baseline"]),
    case("service_maintenance", "승강기 유지보수 용역 업체", "용역", ["승강기", "유지보수"], budget_krw=60_000_000, tags=["baseline"]),
    case("service_accounting", "원가계산 용역 업체", "용역", ["원가", "계산"], budget_krw=30_000_000, tags=["baseline"]),
    case("service_legal", "법률자문 용역 업체", "용역", ["법률", "변호", "법무"], budget_krw=30_000_000, tags=["baseline"]),
    case("service_bus", "전세버스 임차 용역 업체", "용역", ["버스", "여객", "전세"], budget_krw=40_000_000, tags=["baseline"]),
    case("work_electric", "전기공사 부산 업체", "공사", ["전기공사"], budget_krw=100_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_communication", "정보통신공사 업체", "공사", ["정보통신"], budget_krw=100_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_fire", "소방시설공사 업체", "공사", ["소방"], budget_krw=100_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_landscape", "조경식재공사 부산 업체", "공사", ["조경", "식재"], budget_krw=100_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_paving", "도로 포장공사 업체", "공사", ["포장", "도로"], budget_krw=150_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_indoor", "실내건축공사 업체", "공사", ["실내건축", "건축"], budget_krw=80_000_000, tags=["baseline"], convenience=["capacity"]),
    case("work_mechanical", "기계설비공사 부산 업체", "공사", ["기계설비"], budget_krw=100_000_000, tags=["baseline"], convenience=["capacity"]),
]


MIXED = [
    case("mixed_led_or_cctv", "LED 조명 또는 CCTV 구매 가능한 업체", "혼합", ["led", "조명", "cctv", "카메라"], budget_krw=60_000_000, tags=["mixed"], policy=True),
    case("mixed_cleaning_security", "청소랑 경비 같이 볼 수 있는 용역업체", "혼합", ["청소", "경비"], budget_krw=120_000_000, tags=["mixed"]),
    case("mixed_event_printing", "행사 운영이랑 홍보물 인쇄 같이 가능한 업체", "혼합", ["행사", "인쇄", "홍보"], budget_krw=80_000_000, tags=["mixed"], policy=True),
    case("mixed_pc_sw", "컴퓨터랑 보안 소프트웨어 같이 구매할 업체", "혼합", ["컴퓨터", "소프트웨어", "보안"], budget_krw=90_000_000, tags=["mixed"], policy=True),
    case("mixed_fire_electric", "전기공사와 소방공사 면허 있는 업체", "혼합", ["전기", "소방"], budget_krw=150_000_000, tags=["mixed"], convenience=["capacity"]),
    case("mixed_landscape_paving", "조경식재랑 포장공사 가능한 업체", "혼합", ["조경", "포장"], budget_krw=150_000_000, tags=["mixed"], convenience=["capacity"]),
    case("mixed_kitchen_aircon", "급식실 주방기기랑 냉난방기 구매 업체", "혼합", ["주방", "냉난방", "에어컨"], budget_krw=120_000_000, tags=["mixed"], policy=True),
    case("mixed_translation_event", "국제행사 통역과 행사 운영 업체", "혼합", ["통역", "번역", "행사"], budget_krw=70_000_000, tags=["mixed"]),
    case("mixed_furniture_cabinet", "책상 의자 캐비닛 같이 살 수 있는 업체", "혼합", ["책상", "의자", "캐비닛", "가구"], budget_krw=60_000_000, tags=["mixed"], policy=True),
    case("mixed_drone_video", "드론 촬영이랑 영상 제작 업체", "혼합", ["드론", "영상"], budget_krw=50_000_000, tags=["mixed"]),
]


AMBIGUOUS = [
    case("ambiguous_light", "조명 업체 좀 찾아줘", "모호", ["조명", "led"], budget_krw=30_000_000, tags=["ambiguous"], policy=True),
    case("ambiguous_camera", "카메라 설치 가능한 부산 업체", "모호", ["카메라", "cctv", "영상감시"], budget_krw=60_000_000, tags=["ambiguous"], policy=True),
    case("ambiguous_computer", "컴퓨터 살만한 지역업체", "모호", ["컴퓨터", "데스크톱", "노트북"], budget_krw=40_000_000, tags=["ambiguous"], policy=True),
    case("ambiguous_office", "사무실 물품 업체 추천", "모호", ["사무", "컴퓨터", "가구", "토너"], budget_krw=30_000_000, tags=["ambiguous"], policy=True),
    case("ambiguous_facility", "청사 관리 업체", "모호", ["시설관리", "건물(시설)관리", "청소", "경비"], budget_krw=100_000_000, tags=["ambiguous"]),
    case("ambiguous_design", "디자인 업체 추천", "모호", ["디자인", "시각", "환경"], budget_krw=30_000_000, tags=["ambiguous"]),
    case("ambiguous_system", "시스템 구축 업체", "모호", ["시스템", "소프트웨어", "정보"], budget_krw=100_000_000, tags=["ambiguous"]),
    case("ambiguous_repair", "유지보수 업체 추천", "모호", ["유지보수", "시설관리", "승강기"], budget_krw=50_000_000, tags=["ambiguous"]),
    case("ambiguous_event", "행사 맡길 업체", "모호", ["행사", "이벤트"], budget_krw=50_000_000, tags=["ambiguous"]),
    case("ambiguous_print", "홍보자료 제작 업체", "모호", ["홍보", "인쇄", "디자인"], budget_krw=30_000_000, tags=["ambiguous"], policy=True),
]


TYPO = [
    case("typo_cctv_kor", "씨씨티비 설치 업체", "오타/구어", ["cctv", "씨씨티비", "영상감시", "카메라"], budget_krw=60_000_000, tags=["typo"], policy=True),
    case("typo_desktop", "데스크탑 피씨 구매 업체", "오타/구어", ["컴퓨터", "데스크탑", "pc", "피씨"], budget_krw=40_000_000, tags=["typo"], policy=True),
    case("typo_aircon", "에어콘 냉난방 구매 업체", "오타/구어", ["에어컨", "냉난방", "공기조화"], budget_krw=60_000_000, tags=["typo"], policy=True),
    case("typo_projector", "빔프로젝트 구매 업체", "오타/구어", ["프로젝터", "비디오"], budget_krw=40_000_000, tags=["typo"], policy=True),
    case("typo_toner", "토너 카트리지 업체", "오타/구어", ["토너", "카트리지"], budget_krw=20_000_000, tags=["typo"], policy=True, avoid_top1=["축산", "식육", "식품"]),
    case("typo_disinfect", "방역 소독업체", "오타/구어", ["방역", "소독"], budget_krw=30_000_000, tags=["typo"], avoid_top1=["손소독제", "살균제"]),
    case("typo_event", "행사대행 업체", "오타/구어", ["행사", "대행", "이벤트"], budget_krw=60_000_000, tags=["typo"]),
    case("typo_translation", "통번역 업체", "오타/구어", ["통역", "번역"], budget_krw=40_000_000, tags=["typo"]),
    case("typo_fire", "소방 공사업체", "오타/구어", ["소방"], budget_krw=100_000_000, tags=["typo"], convenience=["capacity"]),
    case("typo_elastic", "탄성 포장 업체", "오타/구어", ["탄성", "포장"], budget_krw=90_000_000, tags=["typo"], policy=True),
]


POLICY = [
    case("policy_women_led", "여성기업 LED 조명 업체", "정책기업", ["led", "조명"], budget_krw=50_000_000, tags=["policy"], policy=True, policy_label="여성기업"),
    case("policy_women_event", "여성기업 행사 용역 업체", "정책기업", ["행사", "이벤트"], budget_krw=50_000_000, tags=["policy"], policy_label="여성기업"),
    case("policy_women_print", "여성기업 인쇄물 업체", "정책기업", ["인쇄", "홍보물"], budget_krw=30_000_000, tags=["policy"], policy=True, policy_label="여성기업"),
    case("policy_disabled_cleaning", "장애인기업 청소용역 업체", "정책기업", ["청소", "환경미화"], budget_krw=50_000_000, tags=["policy"], policy_label="장애인기업"),
    case("policy_disabled_print", "장애인기업 인쇄 업체", "정책기업", ["인쇄"], budget_krw=30_000_000, tags=["policy"], policy=True, policy_label="장애인기업"),
    case("policy_social_computer", "사회적기업 컴퓨터 구매 업체", "정책기업", ["컴퓨터"], budget_krw=40_000_000, tags=["policy"], policy=True, policy_label="사회적기업"),
    case("policy_social_event", "사회적기업 행사 업체", "정책기업", ["행사"], budget_krw=50_000_000, tags=["policy"], policy_label="사회적기업"),
    case("policy_venture_sw", "벤처기업 소프트웨어 구매 업체", "정책기업", ["소프트웨어", "프로그램"], budget_krw=40_000_000, tags=["policy"], policy=True, policy_label="벤처기업"),
    case("policy_startup_drone", "창업기업 드론 업체", "정책기업", ["드론"], budget_krw=40_000_000, tags=["policy"], policy=True, policy_label="창업기업"),
    case("policy_small_business_furniture", "소상공인 사무용가구 업체", "정책기업", ["가구", "책상", "의자"], budget_krw=30_000_000, tags=["policy"], policy=True, policy_label="소상공인"),
]


CONVENIENCE = [
    case("conv_mas_led", "LED 조명 MAS 등록 부산업체", "편의조건", ["led", "조명"], budget_krw=80_000_000, tags=["convenience"], policy=True, convenience=["mas"]),
    case("conv_shopping_pc", "종합쇼핑몰 등록 데스크톱 컴퓨터 업체", "편의조건", ["컴퓨터", "데스크톱"], budget_krw=40_000_000, tags=["convenience"], policy=True, convenience=["shopping"]),
    case("conv_direct_print", "직접생산 가능한 인쇄물 업체", "편의조건", ["인쇄"], budget_krw=30_000_000, tags=["convenience"], policy=True, convenience=["direct_production"]),
    case("conv_sme_furniture", "중기간경쟁제품 사무용가구 업체", "편의조건", ["가구", "책상", "의자"], budget_krw=60_000_000, tags=["convenience"], policy=True, convenience=["direct_production", "sme_competition"]),
    case("conv_capacity_fire", "시공능력 확인 가능한 소방시설공사 업체", "편의조건", ["소방"], budget_krw=150_000_000, tags=["convenience"], convenience=["capacity"]),
    case("conv_venture_switchboard", "분전반 벤처나라 거래실적 업체", "편의조건", ["분전반", "배전반"], budget_krw=50_000_000, tags=["convenience"], policy=True, convenience=["venture_order"], top1_any=["세풍전기"]),
    case("conv_direct_banner", "현수막 직접생산 업체", "편의조건", ["현수막"], budget_krw=20_000_000, tags=["convenience"], policy=True, convenience=["direct_production"]),
    case("conv_direct_desk", "책상 직접생산증명서 보유 업체", "편의조건", ["책상"], budget_krw=40_000_000, tags=["convenience"], policy=True, convenience=["direct_production"]),
    case("conv_shopping_cctv", "종합쇼핑몰 CCTV 업체", "편의조건", ["cctv", "카메라"], budget_krw=70_000_000, tags=["convenience"], policy=True, convenience=["shopping"]),
    case("conv_mas_switchboard", "MAS 분전반 부산 업체", "편의조건", ["분전반", "배전반"], budget_krw=100_000_000, tags=["convenience"], policy=True, convenience=["mas"]),
]


AMOUNT = [
    case("amount_led_20m", "LED 조명 2천만원 이하 바로 구매 업체", "금액", ["led", "조명"], budget_krw=20_000_000, tags=["amount"], policy=True, convenience=["shopping_or_mas"]),
    case("amount_led_80m", "LED 조명 8천만원 구매 MAS 업체", "금액", ["led", "조명"], budget_krw=80_000_000, tags=["amount"], policy=True, convenience=["mas"]),
    case("amount_pc_20m", "컴퓨터 2천만원 구매 업체", "금액", ["컴퓨터"], budget_krw=20_000_000, tags=["amount"], policy=True),
    case("amount_pc_100m", "컴퓨터 1억원 구매 업체", "금액", ["컴퓨터"], budget_krw=100_000_000, tags=["amount"], policy=True),
    case("amount_print_10m", "인쇄물 1천만원 수의계약 업체", "금액", ["인쇄"], budget_krw=10_000_000, tags=["amount"], policy=True),
    case("amount_print_60m", "인쇄물 6천만원 직접생산 업체", "금액", ["인쇄"], budget_krw=60_000_000, tags=["amount"], policy=True, convenience=["direct_production"]),
    case("amount_clean_20m", "청소용역 2천만원 업체", "금액", ["청소"], budget_krw=20_000_000, tags=["amount"]),
    case("amount_clean_100m", "청소용역 1억원 업체", "금액", ["청소"], budget_krw=100_000_000, tags=["amount"]),
    case("amount_fire_100m", "소방공사 1억원 업체", "금액", ["소방"], budget_krw=100_000_000, tags=["amount"], convenience=["capacity"]),
    case("amount_fire_300m", "소방공사 3억원 시공능력 업체", "금액", ["소방"], budget_krw=300_000_000, tags=["amount"], convenience=["capacity"]),
]


def build_cases(target_count: int = 200) -> list[dict[str, Any]]:
    cases = [*BASE, *MIXED, *AMBIGUOUS, *TYPO, *POLICY, *CONVENIENCE, *AMOUNT]
    templates: list[tuple[str, str, list[str], bool]] = [
        ("LED 조명", "물품", ["led", "조명"], True),
        ("CCTV", "물품", ["cctv", "카메라", "영상감시"], True),
        ("컴퓨터", "물품", ["컴퓨터"], True),
        ("노트북", "물품", ["노트북", "컴퓨터"], True),
        ("토너", "물품", ["토너"], True),
        ("비디오프로젝터", "물품", ["프로젝터"], True),
        ("분전반", "물품", ["분전반", "배전반"], True),
        ("인쇄물", "물품", ["인쇄"], True),
        ("사무용가구", "물품", ["가구", "책상", "의자"], True),
        ("청소용역", "용역", ["청소"], False),
        ("경비용역", "용역", ["경비"], False),
        ("시설관리", "용역", ["시설관리", "건물관리", "건물(시설)관리"], False),
        ("행사용역", "용역", ["행사"], False),
        ("번역용역", "용역", ["번역", "통역"], False),
        ("전기공사", "공사", ["전기공사"], False),
        ("소방시설공사", "공사", ["소방"], False),
        ("정보통신공사", "공사", ["정보통신"], False),
    ]
    budgets = [10_000_000, 20_000_000, 40_000_000, 80_000_000, 150_000_000]
    phrasings = [
        "{item} 업체 추천",
        "{item} 부산 지역업체 찾아줘",
        "{item} 예산 {budget_label} 후보",
        "{item} 계약 편한 업체",
        "{item} 조달 등록 업체",
    ]
    idx = 0
    while len(cases) < target_count:
        item, intent, must, policy = templates[idx % len(templates)]
        budget = budgets[(idx // len(templates)) % len(budgets)]
        label = f"{budget // 10_000:,}만원"
        phrasing = phrasings[(idx // (len(templates) * len(budgets))) % len(phrasings)]
        q = phrasing.format(item=item, budget_label=label)
        conv: list[str] = []
        if "계약 편한" in q and intent == "물품":
            conv = ["shopping_or_mas"]
        if intent == "공사":
            conv = ["capacity"]
        cases.append(case(f"generated_{idx:03d}", q, intent, must, budget_krw=budget, tags=["generated"], policy=policy, convenience=conv))
        idx += 1
    return cases[:target_count]


CASES = build_cases(200)


def row_text(row: dict[str, Any]) -> str:
    keys = (
        "company_name",
        "main_products",
        "license_or_business_type",
        "matched_query_label",
        "shopping_mall_product_summary",
        "shopping_mall_match",
        "mas_product_summary",
        "mas_match",
        "direct_production_certificate_products",
        "direct_production_summary",
        "direct_production_match",
        "certified_product_summary",
        "construction_capacity_summary",
        "construction_license_match",
        "construction_capacity_match",
        "construction_capacity_amount",
        "venture_nara_product_summary",
        "venture_nara_order_summary",
    )
    return " ".join(str(row.get(key) or "") for key in keys)


def convenience_ok(rows: list[dict[str, Any]], name: str, top_n: int = 5) -> bool:
    sample = rows[:top_n]
    if name == "shopping_or_mas":
        return any(
            is_positive(row.get("shopping_mall_status_label"))
            or is_positive(row.get("mas_status_label"))
            or is_positive(row.get("shopping_mall_match"))
            or is_positive(row.get("mas_match"))
            or is_positive(row.get("shopping_mall_product_summary"))
            or is_positive(row.get("mas_product_summary"))
            for row in sample
        )
    if name == "shopping":
        return any(
            is_positive(row.get("shopping_mall_status_label"))
            or is_positive(row.get("shopping_mall_match"))
            or is_positive(row.get("shopping_mall_product_summary"))
            for row in sample
        )
    if name == "mas":
        return any(
            is_positive(row.get("mas_status_label"))
            or is_positive(row.get("mas_match"))
            or is_positive(row.get("mas_product_summary"))
            for row in sample
        )
    if name == "direct_production":
        return any(
            is_positive(row.get("direct_production_certificate_status"))
            or is_positive(row.get("direct_production_match"))
            or is_positive(row.get("direct_production_certificate_products"))
            or is_positive(row.get("direct_production_summary"))
            for row in sample
        )
    if name == "sme_competition":
        return any(is_positive(row.get("sme_competition_product_label")) for row in sample)
    if name == "capacity":
        return any(
            is_positive(row.get("construction_capacity_summary"))
            or is_positive(row.get("construction_license_match"))
            or is_positive(row.get("construction_capacity_match"))
            or is_positive(row.get("construction_capacity_amount"))
            for row in sample
        )
    if name == "venture_order":
        return any(is_positive(row.get("venture_nara_order_summary")) for row in sample)
    return True


def evaluate(base_url: str, c: dict[str, Any], timeout_sec: float, max_latency_ms: int) -> dict[str, Any]:
    params = {
        "q": c["q"],
        "region": "busan",
        "limit": 10,
        "budget_krw": c.get("budget_krw") or "",
        "include_product_policy": "true",
    }
    started = time.perf_counter()
    resp = requests.get(f"{base_url.rstrip('/')}/vendor-recommendations/search", params=params, timeout=timeout_sec)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        data = resp.json()
    except Exception:
        data = {}
    rows = [row for row in data.get("rows") or [] if isinstance(row, dict)]
    top = rows[0] if rows else {}
    top1_text = row_text(top)
    top3_text = " ".join(row_text(row) for row in rows[:3])
    top5_text = " ".join(row_text(row) for row in rows[:5])
    policy_summary = data.get("item_policy_summary") or {}
    policy_pref = data.get("policy_preference_summary") or {}
    bad_status = [
        row.get("company_name")
        for row in rows
        if str(row.get("business_status") or "").lower() in {"closed", "suspended", "inactive"}
    ]
    requested_convenience = c.get("convenience") or []
    convenience_results = {name: convenience_ok(rows, name) for name in requested_convenience}
    policy_label = c.get("policy_label")
    policy_label_ok = True
    if policy_label:
        top10_policy = " ".join(str(row.get("policy_company_labels") or "") for row in rows[:10])
        pref_status = str(policy_pref.get("status") or "")
        policy_label_ok = policy_label in top10_policy or pref_status in {"matched", "not_found_in_candidates"}
    avoid_ok = True
    if c.get("avoid_top1"):
        avoid_ok = not contains_any(top1_text, c["avoid_top1"])
    top1_requested_ok = True
    if c.get("top1_any"):
        top1_requested_ok = contains_any(top1_text, c["top1_any"])
    policy_ok = True
    if c.get("policy"):
        policy_ok = policy_summary.get("status") == "matched" and bool(policy_summary.get("matched_products"))
    else:
        policy_ok = policy_summary.get("status") in {"not_requested", "matched", "not_found_or_unavailable"}
    labels_ok = bool(top.get("company_name")) and bool(top.get("business_status_label")) and bool(top.get("recommended_checks"))
    checks = {
        "status_code_ok": resp.status_code == 200,
        "count_ok": len(rows) > 0,
        "latency_ok": elapsed_ms <= max_latency_ms,
        "top1_match": contains_any(top1_text, c["must"]),
        "top3_match": contains_any(top3_text, c["must"]),
        "top5_match": contains_any(top5_text, c["must"]),
        "status_ok": not bad_status,
        "labels_ok": labels_ok,
        "policy_ok": policy_ok,
        "policy_label_ok": policy_label_ok,
        "avoid_ok": avoid_ok,
        "top1_requested_ok": top1_requested_ok,
        "convenience_ok": all(convenience_results.values()) if requested_convenience else True,
    }
    weights = {
        "status_code_ok": 5,
        "count_ok": 10,
        "latency_ok": 5,
        "top1_match": 25,
        "top3_match": 15,
        "top5_match": 5,
        "status_ok": 10,
        "labels_ok": 5,
        "policy_ok": 5,
        "policy_label_ok": 5,
        "avoid_ok": 5,
        "top1_requested_ok": 3,
        "convenience_ok": 2,
    }
    score = sum(weights[key] for key, ok in checks.items() if ok)
    grade = "양호" if score >= 88 else "보통" if score >= 75 else "미흡"
    return {
        "id": c["id"],
        "q": c["q"],
        "intent": c["intent"],
        "tags": c.get("tags") or [],
        "elapsed_ms": elapsed_ms,
        "score": score,
        "grade": grade,
        "checks": checks,
        "convenience_results": convenience_results,
        "policy_status": policy_summary.get("status"),
        "policy_preference_status": policy_pref.get("status"),
        "bad_status_rows": bad_status,
        "first_company": top.get("company_name", ""),
        "first_match": top.get("matched_query_label", ""),
        "first_review_score": top.get("review_score", ""),
        "first_business_status": top.get("business_status_label", ""),
        "rows_sample": [
            {
                "company_name": row.get("company_name"),
                "matched_query_label": row.get("matched_query_label"),
                "business_status_label": row.get("business_status_label"),
                "policy_company_labels": row.get("policy_company_labels"),
                "shopping_mall_status_label": row.get("shopping_mall_status_label"),
                "shopping_mall_match": row.get("shopping_mall_match"),
                "mas_status_label": row.get("mas_status_label"),
                "mas_match": row.get("mas_match"),
                "direct_production_certificate_status": row.get("direct_production_certificate_status"),
                "direct_production_match": row.get("direct_production_match"),
                "direct_production_certificate_products": row.get("direct_production_certificate_products"),
                "sme_competition_product_label": row.get("sme_competition_product_label"),
                "construction_license_match": row.get("construction_license_match"),
                "construction_capacity_match": row.get("construction_capacity_match"),
                "construction_capacity_amount": row.get("construction_capacity_amount"),
                "construction_capacity_summary": row.get("construction_capacity_summary"),
                "venture_nara_order_summary": row.get("venture_nara_order_summary"),
                "review_score": row.get("review_score"),
            }
            for row in rows[:5]
        ],
    }


def write_report(path: Path, records: list[dict[str, Any]], base_url: str) -> None:
    scores = [int(r["score"]) for r in records]
    latencies = [int(r["elapsed_ms"]) for r in records]
    grades = {g: sum(1 for r in records if r["grade"] == g) for g in ("양호", "보통", "미흡")}
    tag_stats: dict[str, dict[str, Any]] = {}
    for r in records:
        for tag in r.get("tags") or ["untagged"]:
            stat = tag_stats.setdefault(tag, {"count": 0, "scores": [], "weak": 0})
            stat["count"] += 1
            stat["scores"].append(int(r["score"]))
            if r["grade"] != "양호":
                stat["weak"] += 1
    lines = [
        "# 업체추천 200개 종합 Q&A 신뢰도 평가",
        "",
        f"- generated_at: {datetime.now().isoformat(timespec='seconds')}",
        f"- base_url: {base_url}",
        f"- total_cases: {len(records)}",
        f"- average_score: {round(statistics.mean(scores), 1) if scores else 0}/100",
        f"- median_score: {round(statistics.median(scores), 1) if scores else 0}/100",
        f"- min_score: {min(scores) if scores else 0}/100",
        f"- grade_counts: 양호 {grades['양호']} / 보통 {grades['보통']} / 미흡 {grades['미흡']}",
        f"- average_latency_ms: {round(statistics.mean(latencies), 1) if latencies else 0}",
        f"- p95_latency_ms: {sorted(latencies)[int(len(latencies) * 0.95) - 1] if latencies else 0}",
        "",
        "## Tag Summary",
        "",
        "| tag | count | avg_score | weak |",
        "|---|---:|---:|---:|",
    ]
    for tag in sorted(tag_stats):
        stat = tag_stats[tag]
        lines.append(f"| {tag} | {stat['count']} | {round(statistics.mean(stat['scores']), 1)} | {stat['weak']} |")
    lines.extend([
        "",
        "## Weak Cases",
        "",
    ])
    weak = [r for r in records if r["grade"] != "양호"]
    if not weak:
        lines.append("- 없음")
    else:
        for r in weak:
            failed = [k for k, v in r["checks"].items() if not v]
            lines.append(f"- {r['id']} ({r['q']}): score={r['score']}, failed={failed}, first={r['first_company']} / {r['first_match']}")
    lines.extend([
        "",
        "## Summary Table",
        "",
        "| id | tags | score | grade | ms | top1 | top3 | policy | conv | first_company |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---|",
    ])
    for r in records:
        c = r["checks"]
        lines.append(
            f"| {r['id']} | {','.join(r.get('tags') or [])} | {r['score']} | {r['grade']} | {r['elapsed_ms']} | "
            f"{c['top1_match']} | {c['top3_match']} | {c['policy_ok']} | {c['convenience_ok']} | {r['first_company']} |"
        )
    lines.extend(["", "## Case Samples", ""])
    for r in records:
        if r["grade"] == "양호" and not any(tag in {"mixed", "ambiguous", "typo", "convenience"} for tag in r.get("tags") or []):
            continue
        lines.append(f"### {r['id']} - {r['q']}")
        lines.append(f"- tags={','.join(r.get('tags') or [])} score={r['score']} grade={r['grade']} elapsed_ms={r['elapsed_ms']}")
        lines.append(f"- first={r['first_company']} / {r['first_match']} / {r['first_business_status']} / review_score={r['first_review_score']}")
        lines.append(f"- checks={json.dumps(r['checks'], ensure_ascii=False)}")
        for row in r["rows_sample"][:3]:
            lines.append("- " + json.dumps(row, ensure_ascii=False, default=str))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://49.50.133.160:8001")
    parser.add_argument("--timeout-sec", type=float, default=15)
    parser.add_argument("--max-latency-ms", type=int, default=3000)
    parser.add_argument("--out-dir", default="artifacts/vendor_recommendation_quality_qa")
    parser.add_argument("--target-count", type=int, default=200)
    args = parser.parse_args()

    selected = CASES[: args.target_count]
    records = [evaluate(args.base_url, c, args.timeout_sec, args.max_latency_ms) for c in selected]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"vendor_recommendation_comprehensive_qa_{time.strftime('%Y%m%d_%H%M%S')}"
    jsonl_path = out_dir / f"{stem}.jsonl"
    md_path = out_dir / f"{stem}.md"
    jsonl_path.write_text("\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in records) + "\n", encoding="utf-8")
    write_report(md_path, records, args.base_url)
    good = sum(1 for r in records if r["grade"] == "양호")
    print(f"jsonl={jsonl_path}")
    print(f"report={md_path}")
    print(f"good={good}/{len(records)}")
    for r in records:
        if r["grade"] != "양호":
            print("WEAK", json.dumps({"id": r["id"], "q": r["q"], "score": r["score"], "tags": r["tags"], "checks": r["checks"], "first": r["first_company"], "match": r["first_match"]}, ensure_ascii=False))
    return 0 if good == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
