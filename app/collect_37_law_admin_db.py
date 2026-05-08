"""
37종 법령·행정규칙 재수집 파이프라인.

출력:
  app/data/law_articles_db.json   - 법률/시행령/시행규칙
  app/data/admin_rules_db.json    - 행정규칙/예규/고시/훈령/집행기준
  app/data/ordinances_db.json     - 조례/자치법규 (참고 보관용, 4단계 체인 제외)
  app/data/legal_collection_report.json

법제처 API에서 XML 조문이 비어 있는 행정규칙은 첨부 PDF를 내려받아
조문 단위로 분할한다. 내부 조회 모듈은 법령 DB와 행정규칙 DB만 통합 로드한다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import requests

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

LAW_OUT = DATA_DIR / "law_articles_db.json"
ADMIN_OUT = DATA_DIR / "admin_rules_db.json"
ORDINANCE_OUT = DATA_DIR / "ordinances_db.json"
REPORT_OUT = DATA_DIR / "legal_collection_report.json"
ATTACH_DIR = DATA_DIR / "admin_rule_attachments"
ATTACH_DIR.mkdir(exist_ok=True)

OC = os.getenv("LAW_API_OC", "busanproduct1")
BASE = "http://www.law.go.kr/DRF"
KST = timezone(timedelta(hours=9))


SEEDS: list[dict[str, Any]] = [
    {"id": "local_contract_act", "name": "지방계약법", "query": "지방자치단체를 당사자로 하는 계약에 관한 법률", "type": "law", "group": "A"},
    {"id": "local_contract_decree", "name": "지방계약법 시행령", "query": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "type": "law", "group": "A"},
    {"id": "local_contract_rule", "name": "지방계약법 시행규칙", "query": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "type": "law", "group": "A"},
    {"id": "national_contract_act", "name": "국가계약법", "query": "국가를 당사자로 하는 계약에 관한 법률", "type": "law", "group": "A"},
    {"id": "national_contract_decree", "name": "국가계약법 시행령", "query": "국가를 당사자로 하는 계약에 관한 법률 시행령", "type": "law", "group": "A"},
    {"id": "national_contract_rule", "name": "국가계약법 시행규칙", "query": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "type": "law", "group": "A"},
    {"id": "procurement_act", "name": "조달사업법", "query": "조달사업에 관한 법률", "type": "law", "group": "A"},
    {"id": "procurement_decree", "name": "조달사업법 시행령", "query": "조달사업에 관한 법률 시행령", "type": "law", "group": "A"},
    {"id": "procurement_rule", "name": "조달사업법 시행규칙", "query": "조달사업에 관한 법률 시행규칙", "type": "law", "group": "A"},
    {"id": "local_bid_execution", "name": "지방자치단체 입찰 및 계약집행기준", "query": "지방자치단체 입찰 및 계약집행기준", "type": "admrul", "group": "B"},
    {"id": "local_bid_winner", "name": "지방자치단체 입찰시 낙찰자 결정기준", "query": "지방자치단체 입찰시 낙찰자 결정기준", "type": "admrul", "group": "B"},
    {"id": "gov_bid_execution", "name": "정부 입찰·계약 집행기준", "query": "정부 입찰 계약 집행기준", "type": "admrul", "group": "B"},
    {"id": "contract_regulation", "name": "계약예규", "query": "(계약예규) 공동계약운용요령", "type": "admrul", "group": "B"},
    {"id": "pps_mas_standard", "name": "조달청 다수공급자계약 관련 기준", "query": "다수공급자계약 추가특수조건", "type": "admrul", "group": "B"},
    {"id": "shopping_mall_ops", "name": "나라장터 종합쇼핑몰 운영 관련 기준", "query": "국가종합전자조달시스템 종합쇼핑몰 운영규정", "type": "admrul", "group": "B"},
    {"id": "mas_processing", "name": "물품 다수공급자계약 업무처리규정", "query": "물품 다수공급자계약 업무처리규정", "type": "admrul", "group": "B"},
    {"id": "mas_2step", "name": "MAS 2단계경쟁 관련 기준", "query": "물품 다수공급자계약 업무처리규정", "type": "admrul", "group": "B", "store_key": "MAS 2단계경쟁 관련 기준"},
    {"id": "sme_purchase_act", "name": "중소기업제품 구매촉진 및 판로지원법", "query": "중소기업제품 구매촉진 및 판로지원에 관한 법률", "type": "law", "group": "C"},
    {"id": "sme_purchase_decree", "name": "중소기업제품 구매촉진법 시행령", "query": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "type": "law", "group": "C"},
    {"id": "sme_competition_items", "name": "중소기업자간 경쟁제품 지정내역", "query": "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역", "type": "admrul", "group": "C"},
    {"id": "direct_production", "name": "직접생산확인 관련 기준", "query": "조달청 제조물품 직접생산확인 기준", "type": "admrul", "group": "C"},
    {"id": "women_enterprise_act", "name": "여성기업지원법", "query": "여성기업지원에 관한 법률", "type": "law", "group": "C"},
    {"id": "women_enterprise_decree", "name": "여성기업지원법 시행령", "query": "여성기업지원에 관한 법률 시행령", "type": "law", "group": "C"},
    {"id": "disabled_enterprise_act", "name": "장애인기업활동 촉진법", "query": "장애인기업활동 촉진법", "type": "law", "group": "C"},
    {"id": "disabled_enterprise_decree", "name": "장애인기업활동 촉진법 시행령", "query": "장애인기업활동 촉진법 시행령", "type": "law", "group": "C"},
    {"id": "social_enterprise_act", "name": "사회적기업 육성법", "query": "사회적기업 육성법", "type": "law", "group": "C"},
    {"id": "social_enterprise_decree", "name": "사회적기업 육성법 시행령", "query": "사회적기업 육성법 시행령", "type": "law", "group": "C"},
    {"id": "innovation_product", "name": "혁신제품 관련 조달청 고시·지침", "query": "혁신제품 구매 운영 규정", "type": "admrul", "group": "D"},
    {"id": "innovation_prototype", "name": "혁신시제품 지정 및 구매 관련 기준", "query": "혁신제품 시범구매계약 추가특수조건", "type": "admrul", "group": "D"},
    {"id": "excellent_procurement", "name": "우수조달물품 지정관리 규정", "query": "우수조달물품 지정관리 규정", "type": "admrul", "group": "D"},
    {"id": "tech_priority_purchase", "name": "기술개발제품 우선구매 관련 기준", "query": "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙", "type": "admrul", "group": "D"},
    {"id": "busan_local_product", "name": "부산광역시 지역상품 우선구매 관련 조례", "query": "부산광역시 중소기업제품 구매촉진 및 판로지원 조례", "type": "ordin", "group": "E"},
    {"id": "busan_local_company", "name": "부산광역시 지역업체·지역상품 우대 관련 자치법규", "query": "부산광역시 지역건설산업 활성화 촉진에 관한 조례", "type": "ordin", "group": "E"},
    {"id": "public_institution_act", "name": "공공기관의 운영에 관한 법률", "query": "공공기관의 운영에 관한 법률", "type": "law", "group": "F"},
    {"id": "public_institution_decree", "name": "공공기관의 운영에 관한 법률 시행령", "query": "공공기관의 운영에 관한 법률 시행령", "type": "law", "group": "F"},
    {"id": "public_corp_contract_rule", "name": "공기업ㆍ준정부기관 계약사무규칙", "query": "공기업ㆍ준정부기관 계약사무규칙", "type": "law", "group": "F"},
    {"id": "public_corp_accounting_rule", "name": "공기업ㆍ준정부기관 회계사무규칙", "query": "공기업ㆍ준정부기관 회계사무규칙", "type": "law", "group": "F"},
]


def api_get(endpoint: str, params: dict[str, Any]) -> ET.Element:
    params = {**params, "OC": OC, "type": "XML"}
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    r.raise_for_status()
    return ET.fromstring(r.content)


def clean(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def xt(el: ET.Element, path: str) -> str:
    found = el.find(path)
    return clean(found.text if found is not None else "")


def article_key_from_text(text: str, fallback_no: str = "", branch_no: str = "") -> str:
    m = re.match(r"\s*(제\d+조(?:의\d+)?)", text or "")
    if m:
        return m.group(1)
    if fallback_no:
        key = f"제{fallback_no}조" if not fallback_no.startswith("제") else fallback_no
        if branch_no and branch_no not in ("0", "00", "None"):
            key += f"의{int(branch_no)}"
        return key
    return ""


def article_key_from_seq(seq: int, text: str) -> str:
    m = re.match(r"\s*(제\d+조(?:의\d+)?)", text or "")
    if m:
        return m.group(1)
    chapter = re.match(r"\s*(제\d+[장절관])\s*(.*)", text or "")
    if chapter:
        return f"{chapter.group(1)}_{seq:03d}"
    return f"본문_{seq:03d}"


def unique_key(base: str, existing: dict[str, Any]) -> str:
    if base not in existing:
        return base
    i = 2
    while f"{base}__dup{i}" in existing:
        i += 1
    return f"{base}__dup{i}"


def extract_refs(text: str) -> list[dict[str, str]]:
    refs = []
    seen = set()
    for m in re.finditer(r"「([^」]+)」[^제]{0,15}(제\d+조(?:의\d+)?)", text or ""):
        key = (m.group(1), m.group(2))
        if key in seen:
            continue
        seen.add(key)
        refs.append({"law": key[0], "article": key[1]})
    return refs


def search(target: str, query: str, display: int = 10) -> list[dict[str, str]]:
    root = api_get("lawSearch.do", {"target": target, "query": query, "display": display})
    tag = "law" if target in ("law", "ordin") else "admrul"
    rows = []
    for item in root.findall(f".//{tag}"):
        row = {child.tag: clean(child.text) for child in item}
        if row:
            rows.append(row)
    return rows


def score_row(seed: dict[str, Any], row: dict[str, str]) -> int:
    expected = re.sub(r"\s+", "", seed["query"].replace("ㆍ", "·"))
    if seed["type"] == "law":
        name = row.get("법령명한글", "") or row.get("법령명_한글", "")
    elif seed["type"] == "ordin":
        name = row.get("자치법규명", "")
    else:
        name = row.get("행정규칙명", "")
    normalized = re.sub(r"\s+", "", name.replace("ㆍ", "·"))
    score = 0
    if normalized == expected:
        score += 100
    if expected in normalized or normalized in expected:
        score += 60
    for token in re.split(r"\s+|·|ㆍ", seed["query"]):
        token = token.strip("() ")
        if len(token) >= 2 and token in name:
            score += 5
    if row.get("현행연혁구분") == "현행" or row.get("현행연혁코드") == "현행":
        score += 10
    return score


def pick_best(seed: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda r: score_row(seed, r), reverse=True)[0]


def collect_law(seed: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    rows = search("law", seed["query"], display=10)
    top = pick_best(seed, rows)
    if not top:
        raise RuntimeError("law search returned no results")
    mst = top.get("법령일련번호")
    root = api_get("lawService.do", {"target": "law", "MST": mst})
    articles: dict[str, Any] = {}
    for jo in root.findall(".//조문단위"):
        body_parts = [xt(jo, "조문내용")]
        for tag in ("항내용", "호내용", "목내용"):
            for el in jo.findall(f".//{tag}"):
                part = clean(el.text)
                if part and part not in body_parts:
                    body_parts.append(part)
        text = clean("\n".join(p for p in body_parts if p))
        if not text:
            continue
        key = article_key_from_text(text, xt(jo, "조문번호"), xt(jo, "조문가지번호"))
        if not key:
            continue
        key = unique_key(key, articles)
        articles[key] = {
            "title": xt(jo, "조문제목"),
            "text": text,
            "lookup_key": f"{seed['name']} {key}",
            "cross_refs": extract_refs(text),
        }
    source = {
        "mst": mst,
        "law_id": xt(root, ".//법령ID") or top.get("법령ID", ""),
        "full_name": xt(root, ".//법령명_한글") or top.get("법령명한글", seed["query"]),
        "short_name": seed["name"],
        "source_type": "law",
        "source": "법제처 API 직접",
        "effective_date": xt(root, ".//시행일자") or top.get("시행일자", ""),
        "collected_at": datetime.now(KST).isoformat(),
        "article_count": len(articles),
        "articles": articles,
    }
    return seed["name"], source, {"matched_name": source["full_name"], "mst": mst, "raw": top}


def attachment_links(root: ET.Element) -> list[dict[str, str]]:
    names = [clean(x.text) for x in root.findall(".//첨부파일명")]
    links = [clean(x.text) for x in root.findall(".//첨부파일링크")]
    return [{"name": n, "url": u} for n, u in zip(names, links) if n and u]


def download_pdf_text(seed_id: str, links: list[dict[str, str]]) -> tuple[str, list[str]]:
    if fitz is None:
        return "", []
    pdfs = [x for x in links if x["name"].lower().endswith(".pdf")]
    if not pdfs:
        return "", []
    chosen = pdfs[0]
    url = chosen["url"]
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()[:12]
    path = ATTACH_DIR / f"{seed_id}_{digest}.pdf"
    path.write_bytes(r.content)
    text_parts = []
    with fitz.open(stream=r.content, filetype="pdf") as doc:
        for page in doc:
            text_parts.append(page.get_text("text"))
    return clean("\n".join(text_parts)), [str(path)]


def split_text_to_articles(text: str) -> dict[str, Any]:
    articles: dict[str, Any] = {}
    if not text:
        return articles
    matches = list(re.finditer(r"(?m)(제\d+조(?:의\d+)?)(?:\s*[（(][^)）]+[）)])?", text))
    if not matches:
        articles["전문"] = {"title": "", "text": text, "lookup_key": "", "cross_refs": extract_refs(text)}
        return articles
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = clean(text[start:end])
        if len(chunk) < 10:
            continue
        key = unique_key(m.group(1), articles)
        title_match = re.match(r"제\d+조(?:의\d+)?[（(]([^)）]+)[）)]", chunk)
        articles[key] = {
            "title": title_match.group(1) if title_match else "",
            "text": chunk,
            "lookup_key": "",
            "cross_refs": extract_refs(chunk),
        }
    return articles


def collect_admin(seed: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    rows = search("admrul", seed["query"], display=20)
    top = pick_best(seed, rows)
    if not top:
        raise RuntimeError("admrul search returned no results")
    seq = top.get("행정규칙일련번호")
    root = api_get("lawService.do", {"target": "admrul", "ID": seq})
    articles: dict[str, Any] = {}
    for idx, el in enumerate(root.findall(".//조문내용"), 1):
        text = clean(el.text)
        if not text:
            continue
        key = unique_key(article_key_from_seq(idx, text), articles)
        title_match = re.match(r"제\d+조(?:의\d+)?[（(]([^)）]+)[）)]", text)
        articles[key] = {
            "title": title_match.group(1) if title_match else "",
            "text": text,
            "lookup_key": f"{seed['name']} {key}",
            "cross_refs": extract_refs(text),
        }
    links = attachment_links(root)
    attachment_paths: list[str] = []
    attachment_used = False
    if not articles or sum(len(a["text"]) for a in articles.values()) < 500:
        pdf_text, attachment_paths = download_pdf_text(seed["id"], links)
        pdf_articles = split_text_to_articles(pdf_text)
        if pdf_articles:
            articles = pdf_articles
            attachment_used = True
    official = xt(root, ".//행정규칙명") or top.get("행정규칙명", seed["query"])
    for key, art in articles.items():
        art["lookup_key"] = f"{official} {key}"
    source = {
        "mst": "",
        "law_id": xt(root, ".//행정규칙ID") or top.get("행정규칙ID", ""),
        "admrul_seq": seq,
        "full_name": official,
        "short_name": seed["name"],
        "source_type": "admin_rule",
        "source": "법제처 API 직접" + (" + 첨부PDF" if attachment_used else ""),
        "effective_date": xt(root, ".//시행일자") or top.get("시행일자", ""),
        "issuing_org": xt(root, ".//소관부처명") or top.get("소관부처명", ""),
        "attachment_links": links,
        "attachment_paths": attachment_paths,
        "collected_at": datetime.now(KST).isoformat(),
        "article_count": len(articles),
        "articles": articles,
    }
    return seed.get("store_key") or official, source, {
        "matched_name": official,
        "admrul_seq": seq,
        "raw": top,
        "attachment_used": attachment_used,
        "attachment_count": len(links),
    }


def collect_ordin(seed: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    rows = search("ordin", seed["query"], display=20)
    top = pick_best({**seed, "type": "ordin"}, rows)
    if not top:
        raise RuntimeError("ordin search returned no results")
    mst = top.get("자치법규일련번호")
    root = api_get("lawService.do", {"target": "ordin", "MST": mst})
    articles: dict[str, Any] = {}
    for jo in root.findall(".//조"):
        text = xt(jo, "조내용")
        if not text:
            continue
        key = article_key_from_text(text, xt(jo, "조문번호"), xt(jo, "조문가지번호"))
        if not key:
            key = article_key_from_seq(len(articles) + 1, text)
        key = unique_key(key, articles)
        articles[key] = {
            "title": xt(jo, "조제목"),
            "text": text,
            "lookup_key": f"{seed['name']} {key}",
            "cross_refs": extract_refs(text),
        }
    official = xt(root, ".//자치법규명") or top.get("자치법규명", seed["query"])
    for key, art in articles.items():
        art["lookup_key"] = f"{official} {key}"
    source = {
        "mst": mst,
        "law_id": xt(root, ".//자치법규ID") or top.get("자치법규ID", ""),
        "full_name": official,
        "short_name": seed["name"],
        "source_type": "ordinance",
        "source": "법제처 자치법규 API 직접",
        "effective_date": xt(root, ".//시행일자") or top.get("시행일자", ""),
        "issuing_org": xt(root, ".//지자체기관명") or top.get("지자체기관명", ""),
        "collected_at": datetime.now(KST).isoformat(),
        "article_count": len(articles),
        "articles": articles,
    }
    return seed["name"], source, {"matched_name": official, "mst": mst, "raw": top}


def validate_db(
    law_db: dict[str, Any],
    admin_db: dict[str, Any],
    ordinance_db: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    merged = {**law_db, **admin_db, **ordinance_db}
    duplicate_article_keys = []
    for name, data in merged.items():
        keys = list(data.get("articles", {}).keys())
        if len(keys) != len(set(keys)):
            duplicate_article_keys.append(name)
    branch_checks = {}
    for law_name in ["지방계약법 시행령", "국가계약법 시행령"]:
        arts = merged.get(law_name, {}).get("articles", {})
        branch_checks[law_name] = {
            "has_제6조": "제6조" in arts,
            "has_제6조의2": "제6조의2" in arts,
            "branch_key_count": len([k for k in arts if "의" in k and not "__dup" in k]),
        }
    empty_sources = [
        name for name, data in merged.items()
        if data.get("source_type") != "skip_api" and len(data.get("articles", {})) == 0
    ]
    return {
        "law_source_count": len(law_db),
        "admin_source_count": len(admin_db),
        "ordinance_source_count": len(ordinance_db),
        "total_source_count": len(rows),
        "law_article_count": sum(len(v.get("articles", {})) for v in law_db.values()),
        "admin_article_count": sum(len(v.get("articles", {})) for v in admin_db.values()),
        "ordinance_article_count": sum(len(v.get("articles", {})) for v in ordinance_db.values()),
        "duplicate_article_key_sources": duplicate_article_keys,
        "branch_article_checks": branch_checks,
        "empty_sources": empty_sources,
        "failed_sources": [r for r in rows if r["status"] != "verified"],
    }


def main() -> int:
    law_db: dict[str, Any] = {}
    admin_db: dict[str, Any] = {}
    ordinance_db: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    print(f"37종 법령·행정규칙 재수집 시작 / OC={OC}")
    for i, seed in enumerate(SEEDS, 1):
        print(f"[{i:02d}/{len(SEEDS)}] {seed['group']} {seed['type']} {seed['name']}")
        row = {"seed_id": seed["id"], "seed_name": seed["name"], "type": seed["type"], "group": seed["group"], "status": "pending"}
        try:
            if seed["type"] == "skip_api":
                row.update({"status": "skipped", "reason": "법제처 API 대상 아님"})
            elif seed["type"] == "law":
                key, data, meta = collect_law(seed)
                law_db[key] = data
                row.update({"status": "verified", "stored_key": key, "article_count": data["article_count"], **meta})
            elif seed["type"] == "admrul":
                key, data, meta = collect_admin(seed)
                admin_db[key] = data
                row.update({"status": "verified", "stored_key": key, "article_count": data["article_count"], **meta})
            elif seed["type"] == "ordin":
                key, data, meta = collect_ordin(seed)
                ordinance_db[key] = data
                row.update({"status": "verified", "stored_key": key, "article_count": data["article_count"], **meta})
            else:
                row.update({"status": "failed", "reason": "unknown type"})
        except Exception as exc:
            row.update({"status": "failed", "reason": f"{type(exc).__name__}: {exc}"})
        rows.append(row)
        print(f"    -> {row['status']} articles={row.get('article_count', 0)} match={row.get('matched_name', '')}")
        time.sleep(0.35)

    validation = validate_db(law_db, admin_db, ordinance_db, rows)
    LAW_OUT.write_text(json.dumps(law_db, ensure_ascii=False, indent=2), encoding="utf-8")
    ADMIN_OUT.write_text(json.dumps(admin_db, ensure_ascii=False, indent=2), encoding="utf-8")
    ORDINANCE_OUT.write_text(json.dumps(ordinance_db, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "collected_at": datetime.now(KST).isoformat(),
        "oc": OC,
        "rows": rows,
        "validation": validation,
    }
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if validation["empty_sources"] or validation["duplicate_article_key_sources"] or validation["failed_sources"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
