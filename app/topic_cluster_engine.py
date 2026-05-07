"""
주제 클러스터 기반 조문 매핑 엔진 v2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[기관유형 × 계약유형 × 주제]로 필요한 조문 클러스터를 반환.
금액 판단은 LLM이 조문 원문을 읽고 직접 수행.

v2 변경:
  - BASE_ARTICLES: 어떤 질문이든 항상 포함되는 핵심 조문 세트
  - 키워드 미감지 시에도 기본 조문 세트 반환 (안전망)
  - 인접 주제 핵심 조문 자동 포함 (관대한 조문 선택)
"""
import json
import os
import re

# ━━━ 기관유형별 법령 체계 ━━━
LAW_SYSTEMS = {
    "local": {
        "law": "지방계약법",
        "decree": "지방계약법 시행령",
        "rule": "지방계약법 시행규칙",
        "admin_rules": [
            "지방자치단체 입찰 및 계약집행기준",
            "지방자치단체 입찰시 낙찰자 결정기준",
        ],
    },
    "national": {
        "law": "국가계약법",
        "decree": "국가계약법 시행령",
        "rule": "국가계약법 시행규칙",
        "admin_rules": [
            "(계약예규) 정부 입찰·계약 집행기준",
        ],
    },
    "public_corp": {
        "law": "국가계약법",
        "decree": "국가계약법 시행령",
        "rule": "국가계약법 시행규칙",
        "admin_rules": [
            "공기업계약사무규칙",
            "기타공공기관 계약사무 운영규정",
        ],
    },
    "invested": {
        "law": "지방계약법",
        "decree": "지방계약법 시행령",
        "rule": "지방계약법 시행규칙",
        "admin_rules": [
            "지방자치단체 입찰 및 계약집행기준",
            "지방자치단체 입찰시 낙찰자 결정기준",
        ],
    },
}

# ━━━ 항상 포함되는 기본 조문 세트 (안전망) ━━━
# 어떤 키워드도 감지되지 않아도 이 조문들은 반드시 포함됨
# → LLM이 넓은 컨텍스트에서 관련 부분을 찾아 답변
BASE_ARTICLES = {
    "local": [
        ("law", ["제9조"]),           # 계약 방법 (수의/경쟁)
        ("decree", ["제13조"]),       # 일반경쟁입찰 원칙
        ("decree", ["제25조"]),       # 수의계약 요건
        ("decree", ["제30조"]),       # 수의계약 금액 기준
        ("decree", ["제20조"]),       # 제한경쟁 사유
    ],
    "national": [
        ("law", ["제7조"]),
        ("decree", ["제14조"]),
        ("decree", ["제26조"]),
        ("decree", ["제30조"]),
        ("decree", ["제21조"]),
    ],
    "public_corp": [
        ("law", ["제7조"]),
        ("decree", ["제14조"]),
        ("decree", ["제26조"]),
        ("decree", ["제30조"]),
    ],
}

# ━━━ 인접 주제 매핑 ━━━
# 특정 주제 감지 시 함께 가져올 인접 주제의 핵심 조문
ADJACENT_TOPICS = {
    "direct_contract": ["bid", "price"],     # 수의계약 → 입찰+예정가격 핵심도 함께
    "bid": ["direct_contract", "price"],     # 입찰 → 수의계약+예정가격도 함께
    "price": ["direct_contract", "bid"],     # 예정가격 → 수의계약+입찰도 함께
    "joint_contract": ["bid"],               # 공동계약 → 입찰도 함께
    "evaluation": ["bid"],                   # 가점/평가 → 입찰도 함께
    "policy_company": ["direct_contract"],   # 정책기업 → 수의계약도 함께
}

# 인접 주제에서 가져올 핵심 조문 (전체가 아닌 핵심만)
ADJACENT_CORE_ONLY = {
    "direct_contract": {
        "local": [("decree", ["제25조", "제30조"])],
        "national": [("decree", ["제26조", "제30조"])],
    },
    "bid": {
        "local": [("decree", ["제13조", "제20조"])],
        "national": [("decree", ["제14조", "제21조"])],
    },
    "price": {
        "local": [("decree", ["제7조", "제9조"])],
        "national": [("decree", ["제7조", "제9조"])],
    },
}

# ━━━ 주제별 조문 클러스터 ━━━
TOPIC_CLUSTERS = {
    # ── 수의계약 ──
    "direct_contract": {
        "local": {
            "core": [
                ("law", ["제9조"]),
                ("decree", ["제25조", "제26조", "제30조"]),
                ("rule", ["제28조", "제29조", "제30조"]),
            ],
            "by_type": {
                "goods": [("decree", ["제25조", "제30조"])],
                "construction": [("decree", ["제25조", "제30조", "제30조의2"])],
                "service": [("decree", ["제25조", "제30조"])],
            },
            "admin": [
                ("지방자치단체 입찰 및 계약집행기준", ["전문"]),
            ],
        },
        "national": {
            "core": [
                ("law", ["제7조"]),
                ("decree", ["제26조", "제27조", "제30조"]),
                ("rule", ["제28조", "제29조", "제30조"]),
            ],
            "by_type": {
                "goods": [("decree", ["제26조", "제30조"])],
                "construction": [("decree", ["제26조", "제30조"])],
                "service": [("decree", ["제26조", "제30조"])],
            },
            "admin": [
                ("(계약예규) 정부 입찰·계약 집행기준", ["전문"]),
            ],
        },
        "public_corp": {
            "core": [
                ("law", ["제7조"]),
                ("decree", ["제26조", "제27조", "제30조"]),
            ],
            "by_type": {},
            "admin": [
                ("공기업계약사무규칙", ["전문"]),
                ("기타공공기관 계약사무 운영규정", ["전문"]),
            ],
        },
    },

    # ── 입찰 (경쟁입찰/제한입찰/지명입찰) ──
    "bid": {
        "local": {
            "core": [
                ("law", ["제9조", "제12조", "제13조", "제14조"]),
                ("decree", ["제13조", "제14조", "제20조", "제21조", "제22조", "제42조"]),
                ("rule", ["제24조"]),
            ],
            "by_type": {
                "construction": [("decree", ["제20조", "제42조"])],
                "service": [("decree", ["제20조", "제42조"])],
            },
            "admin": [
                ("지방자치단체 입찰시 낙찰자 결정기준", ["전문"]),
                ("지방자치단체 입찰 및 계약집행기준", ["전문"]),
            ],
        },
        "national": {
            "core": [
                ("law", ["제7조", "제10조"]),
                ("decree", ["제14조", "제21조", "제22조", "제42조"]),
                ("rule", ["제24조"]),
            ],
            "by_type": {},
            "admin": [
                ("(계약예규) 정부 입찰·계약 집행기준", ["전문"]),
            ],
        },
        "public_corp": {
            "core": [
                ("law", ["제7조", "제10조"]),
                ("decree", ["제14조", "제21조", "제22조"]),
            ],
            "by_type": {},
            "admin": [
                ("공기업계약사무규칙", ["전문"]),
            ],
        },
    },

    # ── 예정가격/원가계산 ──
    "price": {
        "local": {
            "core": [
                ("law", ["제6조"]),
                ("decree", ["제7조", "제8조", "제9조", "제10조"]),
                ("rule", ["제5조", "제6조"]),
            ],
            "by_type": {},
            "admin": [
                ("지방자치단체 입찰 및 계약집행기준", ["전문"]),
            ],
        },
        "national": {
            "core": [
                ("law", ["제4조", "제6조"]),
                ("decree", ["제7조", "제8조", "제9조", "제10조"]),
                ("rule", ["제5조", "제6조"]),
            ],
            "by_type": {},
            "admin": [
                ("(계약예규) 정부 입찰·계약 집행기준", ["전문"]),
            ],
        },
        "public_corp": {
            "core": [
                ("law", ["제4조", "제6조"]),
                ("decree", ["제7조", "제8조", "제9조"]),
            ],
            "by_type": {},
            "admin": [
                ("공기업계약사무규칙", ["전문"]),
            ],
        },
    },

    # ── 공동계약 ──
    "joint_contract": {
        "local": {
            "core": [
                ("law", ["제15조"]),
                ("decree", ["제74조", "제75조", "제76조"]),
            ],
            "by_type": {},
            "admin": [
                ("(계약예규) 공동계약운용요령", ["전문"]),
            ],
        },
        "national": {
            "core": [
                ("law", ["제25조"]),
                ("decree", ["제72조", "제73조", "제74조", "제75조", "제76조"]),
            ],
            "by_type": {},
            "admin": [
                ("(계약예규) 공동계약운용요령", ["전문"]),
            ],
        },
        "public_corp": {
            "core": [
                ("law", ["제25조"]),
                ("decree", ["제72조", "제73조"]),
            ],
            "by_type": {},
            "admin": [
                ("(계약예규) 공동계약운용요령", ["전문"]),
            ],
        },
    },

    # ── MAS/다수공급자계약 ──
    "mas": {
        "_common": {
            "core": [
                ("조달사업법", ["제9조", "제9조의2"]),
                ("조달사업법 시행령", ["제14조", "제15조", "제16조"]),
            ],
            "by_type": {},
            "admin": [
                ("물품 다수공급자계약 업무처리규정", ["전문"]),
                ("국가종합전자조달시스템 종합쇼핑몰 운영규정", ["전문"]),
            ],
        },
    },

    # ── 우선구매/중소기업제품 ──
    "priority_purchase": {
        "_common": {
            "core": [
                ("중소기업구매촉진법", ["제6조", "제7조", "제8조", "제9조", "제12조", "제13조", "제14조"]),
                ("중소기업구매촉진법 시행령", ["제7조", "제8조", "제9조", "제10조"]),
            ],
            "by_type": {},
            "admin": [
                ("중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역", ["전문"]),
                ("조달청 제조물품 직접생산확인 기준", ["전문"]),
            ],
        },
    },

    # ── 가점/평가 ──
    "evaluation": {
        "local": {
            "core": [("decree", ["제42조"])],
            "by_type": {
                "construction": [("decree", ["제42조"])],
                "service": [("decree", ["제42조"])],
            },
            "admin": [
                ("지방자치단체 입찰시 낙찰자 결정기준", ["전문"]),
            ],
        },
        "national": {
            "core": [("decree", ["제42조"])],
            "by_type": {},
            "admin": [
                ("(계약예규) 정부 입찰·계약 집행기준", ["전문"]),
            ],
        },
        "public_corp": {
            "core": [],
            "by_type": {},
            "admin": [
                ("기타공공기관 계약사무 운영규정", ["전문"]),
            ],
        },
    },

    # ── 우수조달/혁신제품 ──
    "excellence": {
        "_common": {
            "core": [("조달사업법", ["제9조의2"])],
            "by_type": {},
            "admin": [
                ("우수조달공동상표 물품 지정 관리규정", ["전문"]),
                ("혁신제품 구매 운영 규정", ["전문"]),
                ("중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙", ["전문"]),
            ],
        },
    },

    # ── 정책기업 수의계약 특례 ──
    "policy_company": {
        "local": {
            "core": [("decree", ["제25조", "제30조"])],
            "by_type": {},
            "admin": [],
        },
        "national": {
            "core": [("decree", ["제26조", "제30조"])],
            "by_type": {},
            "admin": [],
        },
        "public_corp": {
            "core": [],
            "by_type": {},
            "admin": [("공기업계약사무규칙", ["전문"])],
        },
    },

    # ── 공사 계약 ──
    "construction": {
        "_common": {
            "core": [],
            "by_type": {},
            "admin": [("(계약예규) 공사계약일반조건", ["전문"])],
        },
    },

    # ── 용역 계약 ──
    "service": {
        "_common": {
            "core": [],
            "by_type": {},
            "admin": [
                ("(계약예규) 용역계약일반조건", ["전문"]),
                ("(계약예규) 용역입찰유의서", ["전문"]),
            ],
        },
    },
}


# ━━━ 질문에서 주제 감지 ━━━
TOPIC_KEYWORDS = {
    "direct_contract": ["수의계약", "수의", "견적", "1인견적", "2인견적", "소액수의", "수의시담",
                        "소액", "견적서", "수의계약서"],
    "bid": ["입찰", "경쟁입찰", "제한경쟁", "일반경쟁", "지명경쟁", "낙찰", "적격심사",
            "투찰", "개찰", "유찰", "재공고", "입찰공고", "제한입찰"],
    "price": ["예정가격", "추정가격", "기초금액", "원가계산", "예가", "투찰률",
              "사정률", "낙찰률", "설계변경", "계약보증금", "하자보증", "지체상금", "선금", "기성"],
    "joint_contract": ["공동계약", "공동도급", "공동수급", "JV", "컨소시엄"],
    "mas": ["종합쇼핑몰", "MAS", "다수공급", "쇼핑몰", "3자단가", "제3자", "나라장터",
            "카탈로그", "단가계약"],
    "priority_purchase": ["우선구매", "의무구매", "중소기업제품", "직접생산", "경쟁제품",
                          "중소기업자간"],
    "evaluation": ["가점", "배점", "평가기준", "평가항목", "심사기준", "신인도",
                   "신용평가", "종합평가", "기술평가", "제안서평가"],
    "excellence": ["우수조달", "우수물품", "혁신제품", "혁신", "기술개발", "신기술",
                   "신제품", "성능인증", "품질인증", "녹색제품", "NEP", "NET"],
    "policy_company": ["여성기업", "장애인기업", "사회적기업", "청년창업", "소기업",
                       "소상공인", "정책기업", "자활기업", "마을기업"],
    "construction": ["공사", "건설", "시공", "건축"],
    "service": ["용역", "설계", "감리", "컨설팅", "엔지니어링",
                "안전진단", "점검", "조사", "평가용역", "위탁", "대행", "맡기"],
}

CONTRACT_TYPE_KEYWORDS = {
    "goods": ["물품", "구매", "납품", "구입", "사무용품", "소모품", "장비", "기자재",
              "컴퓨터", "가구", "차량", "프린터", "에어컨", "서버", "비품"],
    "construction": ["공사", "건설", "시공", "건축", "종합공사", "전문공사"],
    "service": ["용역", "설계", "감리", "컨설팅", "엔지니어링", "기술용역",
                "안전진단", "점검", "위탁", "대행", "맡기"],
}

AGENCY_KEYWORDS = {
    "national": ["국가기관", "중앙부처", "국가"],
    "public_corp": ["공기업", "준정부기관", "공공기관"],
    "invested": ["출자출연", "지방공기업", "부산도시공사", "부산교통공사", "부산시설공단"],
    "local": ["지자체", "지방자치단체", "부산시", "부산", "구청", "시청"],
}


def detect_topics(user_message: str) -> list:
    """질문에서 주제를 감지하여 리스트로 반환."""
    detected = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in user_message for kw in keywords):
            detected.append(topic)
    # 기본 안전망: 아무것도 감지 안 되면 수의계약 + 입찰 + 예정가격 (가장 빈번한 3주제)
    if not detected:
        detected = ["direct_contract", "bid", "price"]
    return detected


def detect_contract_type(user_message: str) -> str:
    """질문에서 계약유형(물품/공사/용역) 감지."""
    for ctype, keywords in CONTRACT_TYPE_KEYWORDS.items():
        if any(kw in user_message for kw in keywords):
            return ctype
    return "unspecified"


def detect_agency_type(user_message: str, agency_type: str = None) -> str:
    """기관유형 감지. API 파라미터 우선, 없으면 키워드 감지."""
    if agency_type:
        at = agency_type.lower().replace(" ", "")
        if at in ("national_agency", "국가기관", "중앙부처", "central_government"):
            return "national"
        if at in ("public_corporation", "공기업", "준정부기관", "public_agency"):
            return "public_corp"
        if at in ("invested_institution", "출자출연기관", "busan_entity"):
            return "invested"
        return "local"
    
    for atype, keywords in AGENCY_KEYWORDS.items():
        if any(kw in user_message for kw in keywords):
            return atype
    return "local"  # 기본값: 지자체


def get_article_refs(agency: str, topics: list, contract_type: str = "unspecified") -> list:
    """
    주제 클러스터 기반으로 필요한 조문 참조 목록을 생성합니다.
    v2: 기본 세트 + 인접 주제 핵심 조문 자동 포함
    """
    law_system = LAW_SYSTEMS.get(agency, LAW_SYSTEMS["local"])
    refs = []
    seen = set()
    
    def add_ref(law_name: str, article_no: str):
        key = f"{law_name}:{article_no}"
        if key not in seen:
            seen.add(key)
            refs.append((law_name, article_no))
    
    def resolve_law_key(key: str) -> str:
        if key in law_system:
            return law_system[key]
        return key

    # ── 1단계: 기본 세트 (항상 포함) ──
    base = BASE_ARTICLES.get(agency, BASE_ARTICLES.get("local", []))
    for law_key, art_list in base:
        resolved = resolve_law_key(law_key)
        for art_no in art_list:
            add_ref(resolved, art_no)

    # ── 2단계: 감지된 주제별 클러스터 ──
    for topic in topics:
        cluster = TOPIC_CLUSTERS.get(topic)
        if not cluster:
            continue
        
        if "_common" in cluster:
            topic_data = cluster["_common"]
        elif agency in cluster:
            topic_data = cluster[agency]
        elif "local" in cluster:
            topic_data = cluster["local"]
        else:
            continue
        
        # core 조문
        for law_key, art_list in topic_data.get("core", []):
            resolved = resolve_law_key(law_key)
            for art_no in art_list:
                add_ref(resolved, art_no)
        
        # 계약유형별 추가 조문
        if contract_type != "unspecified":
            for law_key, art_list in topic_data.get("by_type", {}).get(contract_type, []):
                resolved = resolve_law_key(law_key)
                for art_no in art_list:
                    add_ref(resolved, art_no)
        
        # 행정규칙
        for admin_name, art_list in topic_data.get("admin", []):
            for art_no in art_list:
                add_ref(admin_name, art_no)

    # ── 3단계: 인접 주제 핵심 조문 (관대한 확장) ──
    adjacent_added = set()
    for topic in topics:
        for adj_topic in ADJACENT_TOPICS.get(topic, []):
            if adj_topic in topics or adj_topic in adjacent_added:
                continue  # 이미 감지된 주제이거나 추가됨
            adjacent_added.add(adj_topic)
            adj_core = ADJACENT_CORE_ONLY.get(adj_topic, {})
            adj_articles = adj_core.get(agency, adj_core.get("local", []))
            for law_key, art_list in adj_articles:
                resolved = resolve_law_key(law_key)
                for art_no in art_list:
                    add_ref(resolved, art_no)
    
    return refs


def build_preflight_plan(user_message: str, agency_type: str = None) -> list:
    """
    질문을 분석하여 MCP Preflight 실행 계획을 생성합니다.
    """
    agency = detect_agency_type(user_message, agency_type)
    topics = detect_topics(user_message)
    contract_type = detect_contract_type(user_message)
    
    article_refs = get_article_refs(agency, topics, contract_type)
    
    plan = []
    seen = set()
    
    for law_name, article_no in article_refs:
        if article_no == "전문":
            tool = "search_admin_rule"
            query = law_name
        else:
            tool = "search_law"
            query = f"{law_name} {article_no}"
        
        key = f"{tool}:{query}"
        if key not in seen:
            seen.add(key)
            plan.append({"name": tool, "args": {"query": query}})
    
    print(f"  [TOPIC_CLUSTER] agency={agency}, topics={topics}, type={contract_type}, "
          f"refs={len(article_refs)}, plan={len(plan)}")
    
    return plan
