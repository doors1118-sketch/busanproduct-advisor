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

PUBLIC_CONTRACT_LIFECYCLE_TOPICS: list[dict[str, Any]] = [
    {
        "topic": "lifecycle_planning_budget",
        "title": "계약 1단계: 기본계획 수립·예산 확보",
        "flow_stage": "planning",
        "stage_order": 10,
        "keywords": ["기본계획", "예산 확보", "계약업무 흐름도", "발주계획", "사전검토", "사업계획"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약 전에는 사업목적, 예산, 발주 필요성, 조달방식, 일정과 사전심의 여부를 먼저 정리해야 한다.",
        "checklist": ["사업목적과 필요성 문서화", "예산 편성·집행 가능성 확인", "조달요청 또는 자체발주 여부 확인", "사전심의·계약심사 대상 확인"],
    },
    {
        "topic": "lifecycle_preliminary_review",
        "title": "계약 2단계: 발주 전 사전절차",
        "flow_stage": "preliminary_review",
        "stage_order": 20,
        "keywords": ["발주 전", "사전절차", "계약심사", "일상감사", "심의위원회", "건설기술심의"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "입찰공고 전에 계약심사, 일상감사, 기술심의, 조달요청 의무 같은 사전절차 누락 여부를 점검해야 한다.",
        "checklist": ["계약심사 대상 여부 확인", "일상감사·사전컨설팅 필요성 확인", "기술심의·설계심의 대상 확인", "사전절차 완료 전 공고 금지"],
    },
    {
        "topic": "lifecycle_law_and_agency_system",
        "title": "계약 3단계: 적용 법체계·기관유형 확정",
        "flow_stage": "legal_system",
        "stage_order": 30,
        "keywords": ["적용 법령", "국가계약법", "지방계약법", "공기업", "준정부기관", "위탁", "조달요청"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "국가기관, 지방자치단체, 공기업·준정부기관, 출자·출연기관별 적용 법체계가 달라 먼저 기관유형을 확정해야 한다.",
        "checklist": ["발주기관 유형 확인", "위탁·대행 계약의 적용 법령 확인", "자체 계약규정 우선 여부 확인", "국가·지방 기준 혼용 방지"],
    },
    {
        "topic": "lifecycle_contract_type_selection",
        "title": "계약 4단계: 계약 종류 선택",
        "flow_stage": "contract_type",
        "stage_order": 40,
        "keywords": ["계약의 종류", "확정계약", "개산계약", "총액계약", "단가계약", "장기계속계약", "계속비계약", "공동계약"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "총액·단가·장기계속·계속비·공동계약 등 계약 종류를 사업 성격과 예산 구조에 맞게 선택해야 한다.",
        "checklist": ["총액·단가계약 적합성 확인", "장기계속·계속비 구분", "공동계약 필요성 확인", "사후정산 가능 여부 확인"],
    },
    {
        "topic": "lifecycle_contract_method_selection",
        "title": "계약 5단계: 계약방법 결정",
        "flow_stage": "contract_method",
        "stage_order": 50,
        "keywords": ["계약의 방법", "일반경쟁", "제한경쟁", "지명경쟁", "수의계약", "재공고입찰", "지역제한"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "일반경쟁을 원칙으로 하되 제한경쟁·지명경쟁·수의계약은 법령상 사유와 제한 범위를 확인해야 한다.",
        "checklist": ["일반경쟁 원칙 검토", "제한경쟁 사유와 제한요건 확인", "수의계약 사유와 견적방식 분리", "지역제한·중소기업 제한의 중복 제한 검토"],
    },
    {
        "topic": "lifecycle_requirements_specification",
        "title": "계약 6단계: 규격·과업·참가자격 설계",
        "flow_stage": "requirements",
        "stage_order": 60,
        "keywords": ["규격서", "과업지시서", "시방서", "입찰참가자격", "면허", "실적제한", "기술지원확약서", "특정규격"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "규격·과업·참가자격은 계약목적 달성에 필요한 범위 안에서 객관적으로 설계해야 하며 과도한 제한은 감사 리스크가 된다.",
        "checklist": ["특정업체 유리 조건 제거", "실적·면허·기술 제한의 필요성 문서화", "규격·과업의 객관성 확인", "지역업체 활용은 정당한 평가요소로 연결"],
    },
    {
        "topic": "lifecycle_price_estimation",
        "title": "계약 7단계: 추정가격·예정가격 작성",
        "flow_stage": "price_estimation",
        "stage_order": 70,
        "keywords": ["추정가격", "예정가격", "기초금액", "원가계산", "거래실례가격", "감정가격", "견적가격", "가격조사"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "추정가격과 예정가격은 계약방법·공고기간·낙찰자 결정방식에 영향을 주므로 산정 근거와 가격자료를 남겨야 한다.",
        "checklist": ["추정가격·예정가격·추정금액 구분", "가격자료 적용 순위 확인", "원가계산 근거 보관", "재공고·계약방법 변경 시 예정가격 변경 가능성 확인"],
    },
    {
        "topic": "lifecycle_bid_notice",
        "title": "계약 8단계: 입찰공고·입찰 진행",
        "flow_stage": "bid_notice",
        "stage_order": 80,
        "keywords": ["입찰공고", "공고기간", "입찰서", "산출내역서", "입찰보증금", "입찰무효", "공동수급협정서"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "입찰공고에는 참가자격, 계약조건, 평가기준, 제출서류, 무효 사유가 명확히 들어가야 하며 공고 후 임의 변경은 주의해야 한다.",
        "checklist": ["공고기간 확인", "입찰참가자격과 평가기준 일치", "제출서류·입찰무효 사유 명확화", "공동계약 서류 제출기한 확인"],
    },
    {
        "topic": "lifecycle_award_decision",
        "title": "계약 9단계: 낙찰자 결정",
        "flow_stage": "award",
        "stage_order": 90,
        "keywords": ["낙찰자 결정", "적격심사", "종합심사", "종합평가", "협상에 의한 계약", "2단계 경쟁", "설계공모", "제안서평가"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "낙찰자 결정은 계약목적과 평가방식에 따라 적격심사, 종합평가, 협상계약, 2단계 경쟁 등을 구분해야 한다.",
        "checklist": ["낙찰자 결정방식 적합성 확인", "평가위원회 구성과 평가결과 공개 기준 확인", "지역업체 참여도·신인도 반영 가능성 확인", "무효 제안서·부적격자 후속 처리 확인"],
    },
    {
        "topic": "lifecycle_contract_execution",
        "title": "계약 10단계: 계약체결·계약문서 확정",
        "flow_stage": "contract_execution",
        "stage_order": 100,
        "keywords": ["계약체결", "계약문서", "계약보증금", "구비서류", "계약조건", "특수조건", "권리의무"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "낙찰자 선정 후에는 계약보증, 계약문서, 특수조건, 산출내역서 등 계약상 권리·의무를 명확히 확정해야 한다.",
        "checklist": ["계약체결 구비서류 확인", "계약보증금·면제사유 확인", "특수조건의 법령 위반 여부 확인", "계약문서 간 우선순위 확인"],
    },
    {
        "topic": "lifecycle_change_adjustment",
        "title": "계약 11단계: 이행 중 변경·계약금액 조정",
        "flow_stage": "change_adjustment",
        "stage_order": 110,
        "keywords": ["계약금액 조정", "설계변경", "물가변동", "과업변경", "변경계약", "공기연장", "간접비"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "이행 중 설계변경·물가변동·과업변경은 변경 사유, 귀책, 증빙, 단가 적용 기준을 분리해 검토해야 한다.",
        "checklist": ["변경 사유와 귀책 구분", "변경 전 승인 필요성 확인", "단가·간접비 산정 근거 확보", "준공 후 조정 가능성 제한 확인"],
    },
    {
        "topic": "lifecycle_inspection_payment",
        "title": "계약 12단계: 검사·검수·대가지급",
        "flow_stage": "inspection_payment",
        "stage_order": 120,
        "keywords": ["검사", "검수", "기성", "준공", "대가지급", "선금", "준공금", "하자보수보증금"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "검사·검수와 대가지급은 납품·성과물·공사 이행 확인, 기성·준공 처리, 하자담보와 연계해 처리해야 한다.",
        "checklist": ["검사·검수 기준과 증빙 확보", "기성·준공 범위 확인", "선금·대가지급 요건 확인", "하자보수보증·검사 지연 리스크 확인"],
    },
    {
        "topic": "lifecycle_termination_dispute_sanction",
        "title": "계약 13단계: 해제·해지·분쟁·제재",
        "flow_stage": "termination_dispute",
        "stage_order": 130,
        "keywords": ["해제", "해지", "분쟁", "이의신청", "조정위원회", "중재", "부정당업자", "지체상금", "지연배상금"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약 해제·해지, 분쟁, 부정당업자 제재, 지체상금은 법령상 사유와 절차, 귀책, 증빙을 엄격히 구분해야 한다.",
        "checklist": ["해제·해지 사유와 절차 확인", "분쟁해결 경로 확인", "부정당업자 제재 요건 확인", "지체상금 산정 기준과 공제 대상 확인"],
    },
]

PUBLIC_CONTRACT_CONCEPT_TOPICS: list[dict[str, Any]] = [
    {
        "topic": "concept_contract_objects",
        "title": "개념 설명: 공사·용역·물품 계약 구분",
        "concept_group": "contract_object",
        "keywords": ["공사", "용역", "물품", "계약대상", "계약유형", "업무내용", "자격요건", "구분", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약대상은 공사·용역·물품으로 나뉘며, 각 유형별 필요한 자격요건과 적용 절차가 달라진다.",
        "checklist": ["계약 목적물이 공사·용역·물품 중 무엇인지 구분", "필요 면허·등록·직접생산 여부 확인", "혼합 계약이면 주된 목적과 분리발주 가능성 검토"],
    },
    {
        "topic": "concept_contract_types",
        "title": "개념 설명: 계약 종류",
        "concept_group": "contract_type",
        "keywords": ["확정계약", "개산계약", "사후원가검토", "총액계약", "단가계약", "장기계속계약", "계속비계약", "공동계약", "종합계약", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약 종류는 금액 확정 방식, 단가·총액 구조, 회계연도 처리, 공동수급 여부에 따라 나뉜다.",
        "checklist": ["총액·단가 구조 구분", "확정·개산·사후원가검토 구분", "장기계속·계속비 예산 구조 확인", "공동계약 방식 구분"],
    },
    {
        "topic": "concept_contract_methods",
        "title": "개념 설명: 일반경쟁·제한경쟁·지명경쟁·수의계약",
        "concept_group": "contract_method",
        "keywords": ["일반경쟁", "제한경쟁", "지명경쟁", "수의계약", "계약방법", "경쟁입찰", "입찰방법", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약방법은 경쟁성의 정도와 법령상 허용 사유에 따라 일반경쟁, 제한경쟁, 지명경쟁, 수의계약으로 구분된다.",
        "checklist": ["일반경쟁 원칙 확인", "제한경쟁은 제한 사유와 범위 확인", "지명경쟁은 지명 사유 확인", "수의계약은 사유와 견적방식 분리"],
    },
    {
        "topic": "concept_price_terms",
        "title": "개념 설명: 추정가격·예정가격·기초금액·추정금액",
        "concept_group": "price_terms",
        "keywords": ["추정가격", "예정가격", "기초금액", "추정금액", "원가계산", "거래실례가격", "가격", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "가격 관련 용어는 계약방법, 공고기간, 낙찰자 결정, 예산 집행에 영향을 주므로 서로 구분해야 한다.",
        "checklist": ["부가가치세 포함 여부 등 산정 기준 확인", "추정가격과 예정가격의 역할 구분", "기초금액 공개·산정 근거 확인", "가격조사 자료 보관"],
    },
    {
        "topic": "concept_award_methods",
        "title": "개념 설명: 낙찰자 결정방법",
        "concept_group": "award_method",
        "keywords": ["낙찰자 결정", "적격심사", "종합심사", "종합평가", "협상에 의한 계약", "2단계 경쟁", "규격가격", "설계공모", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "낙찰자 결정방법은 최저가격만 보는지, 수행능력·기술·가격을 종합 평가하는지에 따라 달라진다.",
        "checklist": ["계약목적에 맞는 낙찰방식 선택", "평가항목과 배점의 객관성 확인", "가격평가와 기술평가 분리", "평가결과 공개·이의제기 절차 확인"],
    },
    {
        "topic": "concept_contract_documents",
        "title": "개념 설명: 계약문서·시방서·과업지시서·특수조건",
        "concept_group": "contract_documents",
        "keywords": ["계약문서", "시방서", "과업지시서", "제안요청서", "특수조건", "산출내역서", "계약조건", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약문서는 계약상 권리·의무의 기준이 되며, 시방서·과업지시서·특수조건·산출내역서의 역할을 구분해야 한다.",
        "checklist": ["계약문서 구성 확인", "시방서·과업지시서와 공고문 불일치 확인", "특수조건의 법령 위반 여부 확인", "산출내역서 제출시기와 효력 확인"],
    },
    {
        "topic": "concept_change_and_dispute",
        "title": "개념 설명: 설계변경·물가변동·지체상금·부정당업자 제재",
        "concept_group": "change_dispute",
        "keywords": ["설계변경", "물가변동", "계약금액 조정", "지체상금", "지연배상금", "부정당업자", "제재", "해지", "해제", "뜻", "개념", "차이"],
        "contract_objects": ["goods", "service", "construction"],
        "summary": "계약 이행 중 변경·지연·해지·제재는 사유, 귀책, 절차와 증빙을 구분해야 하는 고위험 영역이다.",
        "checklist": ["변경 사유와 귀책 구분", "계약금액 조정 요건 확인", "지체일수 산정 근거 확인", "부정당업자 제재 절차 확인"],
    },
]

TOPICS.extend(PUBLIC_CONTRACT_LIFECYCLE_TOPICS)
TOPICS.extend(PUBLIC_CONTRACT_CONCEPT_TOPICS)


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
            "flow_stage": topic.get("flow_stage"),
            "stage_order": topic.get("stage_order"),
            "concept_group": topic.get("concept_group"),
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
