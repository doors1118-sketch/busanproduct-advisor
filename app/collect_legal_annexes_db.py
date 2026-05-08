"""
Collect annex/form data for the internal legal database.

Inputs:
  app/data/law_articles_db.json
  app/data/admin_rules_db.json

Outputs:
  app/data/law_annexes_db.json
  app/data/admin_rule_annexes_db.json
  app/data/legal_annex_collection_report.json
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
LAW_DB_PATH = DATA_DIR / "law_articles_db.json"
ADMIN_DB_PATH = DATA_DIR / "admin_rules_db.json"
LAW_ANNEX_OUT = DATA_DIR / "law_annexes_db.json"
ADMIN_ANNEX_OUT = DATA_DIR / "admin_rule_annexes_db.json"
REPORT_OUT = DATA_DIR / "legal_annex_collection_report.json"

OC = os.getenv("LAW_API_OC", "busanproduct1")
BASE = "http://www.law.go.kr/DRF"
KST = timezone(timedelta(hours=9))
ANNEX_TERMS = ("별표", "별지", "서식", "기준표", "점수표", "평가표", "배점표", "요율표")


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


def api_get(endpoint: str, params: dict[str, Any], retries: int = 2) -> ET.Element:
    params = {**params, "OC": OC, "type": "XML"}
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(f"{BASE}/{endpoint}", params=params, timeout=30)
            response.raise_for_status()
            return ET.fromstring(response.content)
        except Exception as exc:  # pragma: no cover - network-dependent retry path
            last_error = exc
            if attempt < retries:
                time.sleep(0.7 * (attempt + 1))
    raise RuntimeError(f"{endpoint} failed: {last_error}")


def related_articles(text: str) -> list[str]:
    values = []
    seen = set()
    for match in re.finditer(r"제\d+조(?:의\d+)?(?:제\d+항)?", text or ""):
        value = match.group(0)
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values[:10]


def annex_kind(title: str, text: str) -> str:
    sample = f"{title}\n{text}"
    if "별지" in sample or "서식" in sample:
        return "form"
    return "annex"


def annex_key(prefix: str, no: str, idx: int, existing: dict[str, Any]) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z가-힣의]+", "_", no or "").strip("_")
    base = f"{prefix}_{cleaned}" if cleaned else f"{prefix}_{idx:03}"
    key = base
    dup = 2
    while key in existing:
        key = f"{base}__dup{dup}"
        dup += 1
    return key


def parse_annex_units(root: ET.Element, source_name: str) -> dict[str, Any]:
    annexes: dict[str, Any] = {}
    for idx, unit in enumerate(root.findall(".//별표단위"), start=1):
        no = xt(unit, "별표번호")
        title = xt(unit, "별표제목") or xt(unit, "별표서식명")
        text = xt(unit, "별표내용")
        if not title and not text:
            continue
        key = annex_key("별표", no, idx, annexes)
        annexes[key] = {
            "annex_no": no,
            "title": title,
            "kind": annex_kind(title, text),
            "text": text,
            "related_articles": related_articles(f"{title}\n{text}"),
            "lookup_key": f"{source_name} {title or no or key}",
        }

    if annexes:
        return annexes

    # Some administrative rules expose annex text without 별표단위.
    for idx, content in enumerate(root.findall(".//별표내용"), start=1):
        text = clean(content.text)
        if not text:
            continue
        title = text.splitlines()[0][:80].strip()
        key = annex_key("별표", "", idx, annexes)
        annexes[key] = {
            "annex_no": "",
            "title": title,
            "kind": annex_kind(title, text),
            "text": text,
            "related_articles": related_articles(f"{title}\n{text}"),
            "lookup_key": f"{source_name} {title or key}",
        }
    return annexes


def find_attachment_references(source: dict[str, Any], limit: int = 12) -> list[dict[str, str]]:
    refs = []
    for article_no, article in (source.get("articles") or {}).items():
        text = article.get("text", "")
        if not text or not any(term in text for term in ANNEX_TERMS):
            continue
        refs.append({
            "article_no": article_no,
            "title": article.get("title", ""),
            "text": text[:2500],
        })
        if len(refs) >= limit:
            break
    return refs


def collect_law_annexes(laws: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output: dict[str, Any] = {}
    report: list[dict[str, Any]] = []
    for source_name, source in laws.items():
        mst = source.get("mst")
        entry_report = {"name": source_name, "source_type": "law", "status": "pending", "annex_count": 0}
        try:
            if not mst:
                raise RuntimeError("missing MST")
            root = api_get("lawService.do", {"target": "law", "MST": mst})
            annexes = parse_annex_units(root, source_name)
            entry = {
                "mst": mst,
                "law_id": source.get("law_id") or xt(root, ".//법령ID"),
                "full_name": source.get("full_name") or xt(root, ".//법령명_한글"),
                "short_name": source.get("short_name") or source_name,
                "source_type": "law_annex",
                "source": "법제처 API 직접 별표단위",
                "effective_date": xt(root, ".//시행일자") or source.get("effective_date", ""),
                "collected_at": datetime.now(KST).isoformat(),
                "annex_count": len(annexes),
                "annexes": annexes,
            }
            output[source_name] = entry
            entry_report.update({"status": "ok", "annex_count": len(annexes)})
        except Exception as exc:
            output[source_name] = {
                "mst": mst or "",
                "law_id": source.get("law_id", ""),
                "full_name": source.get("full_name", source_name),
                "short_name": source.get("short_name", source_name),
                "source_type": "law_annex",
                "source": "법제처 API 직접 별표단위",
                "effective_date": source.get("effective_date", ""),
                "collected_at": datetime.now(KST).isoformat(),
                "annex_count": 0,
                "annexes": {},
                "error": str(exc),
            }
            entry_report.update({"status": "failed", "error": str(exc)})
        report.append(entry_report)
        time.sleep(0.15)
    return output, report


def collect_admin_annexes(admin_rules: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output: dict[str, Any] = {}
    report: list[dict[str, Any]] = []
    for source_name, source in admin_rules.items():
        seq = source.get("admrul_seq")
        entry_report = {
            "name": source_name,
            "source_type": "admin_rule",
            "status": "pending",
            "annex_count": 0,
            "attachment_reference_count": 0,
        }
        annexes: dict[str, Any] = {}
        error = ""
        try:
            if seq:
                root = api_get("lawService.do", {"target": "admrul", "ID": seq})
                annexes = parse_annex_units(root, source_name)
        except Exception as exc:
            error = str(exc)

        attachment_refs = find_attachment_references(source)
        entry = {
            "mst": "",
            "law_id": source.get("law_id", ""),
            "admrul_seq": seq or "",
            "full_name": source.get("full_name", source_name),
            "short_name": source.get("short_name", source_name),
            "source_type": "admin_rule_annex",
            "source": "법제처 행정규칙 API 별표/첨부 색인",
            "effective_date": source.get("effective_date", ""),
            "issuing_org": source.get("issuing_org", ""),
            "attachment_links": source.get("attachment_links") or [],
            "attachment_paths": source.get("attachment_paths") or [],
            "attachment_references": attachment_refs,
            "collected_at": datetime.now(KST).isoformat(),
            "annex_count": len(annexes),
            "annexes": annexes,
        }
        if error:
            entry["error"] = error
        output[source_name] = entry
        entry_report.update({
            "status": "ok" if not error else "partial",
            "annex_count": len(annexes),
            "attachment_reference_count": len(attachment_refs),
            "attachment_count": len(entry["attachment_links"]),
            "error": error,
        })
        report.append(entry_report)
        time.sleep(0.15)
    return output, report


def write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    laws = json.loads(LAW_DB_PATH.read_text(encoding="utf-8"))
    admin_rules = json.loads(ADMIN_DB_PATH.read_text(encoding="utf-8"))

    print(f"별표 DB 수집 시작 / OC={OC} / laws={len(laws)}, admin_rules={len(admin_rules)}")
    law_annexes, law_report = collect_law_annexes(laws)
    admin_annexes, admin_report = collect_admin_annexes(admin_rules)

    write_json(LAW_ANNEX_OUT, law_annexes)
    write_json(ADMIN_ANNEX_OUT, admin_annexes)

    report = {
        "collected_at": datetime.now(KST).isoformat(),
        "law_source_count": len(law_annexes),
        "admin_rule_source_count": len(admin_annexes),
        "law_annex_count": sum(x.get("annex_count", 0) for x in law_annexes.values()),
        "admin_rule_annex_count": sum(x.get("annex_count", 0) for x in admin_annexes.values()),
        "admin_rule_attachment_reference_count": sum(len(x.get("attachment_references") or []) for x in admin_annexes.values()),
        "law_report": law_report,
        "admin_report": admin_report,
    }
    write_json(REPORT_OUT, report)

    print(f"법령 별표: {report['law_annex_count']}건 / 행정규칙 XML 별표: {report['admin_rule_annex_count']}건")
    print(f"행정규칙 첨부/별표 언급 색인: {report['admin_rule_attachment_reference_count']}건")
    print(f"저장: {LAW_ANNEX_OUT}")
    print(f"저장: {ADMIN_ANNEX_OUT}")
    print(f"리포트: {REPORT_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
