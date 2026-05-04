"""
classify_legal_update_impact_v0_1_1.py
Impact Level에 따라 recommended_action을 정확하게 매핑한다.
- low → auto_update_source
- medium → update_source_but_hold_interpretation
- high → hold_rule_until_review
- critical → fail_closed_until_review
"""
import json

SENSITIVE_KEYWORDS_HIGH = ["수의계약", "낙찰자 결정", "한도", "금액", "계약방식", "예외"]
SENSITIVE_KEYWORDS_CRITICAL = ["적용기간", "폐지", "삭제", "전면개정"]

ACTION_MAP = {
    "low": "auto_update_source",
    "medium": "update_source_but_hold_interpretation",
    "high": "hold_rule_until_review",
    "critical": "fail_closed_until_review"
}


def classify_impact(diff_report, source_meta):
    """
    diff_report의 changed_articles와 source_meta의 activation_mode를 함께 분석하여
    impact_level을 산정하고 적절한 recommended_action을 반환한다.
    """
    impact_level = "low"
    matched_keywords = []

    changed_articles = diff_report.get("changed_articles", [])

    # Critical keyword scan
    for article in changed_articles:
        for kw in SENSITIVE_KEYWORDS_CRITICAL:
            if kw in article:
                impact_level = "critical"
                matched_keywords.append(kw)

    # High keyword scan (critical보다 낮은 등급)
    if impact_level != "critical":
        for article in changed_articles:
            for kw in SENSITIVE_KEYWORDS_HIGH:
                if kw in article:
                    impact_level = "high"
                    matched_keywords.append(kw)

    # Core routing logic 변경은 최소 medium
    if impact_level == "low":
        act_mode = source_meta.get("activation_mode")
        if act_mode in ("core_common", "procurement_route_required"):
            impact_level = "medium"

    recommended_action = ACTION_MAP[impact_level]
    requires_review = impact_level in ("medium", "high", "critical")

    return {
        "source_id": diff_report["source_id"],
        "source_title": diff_report.get("title", ""),
        "active_for_rule": source_meta.get("active_for_rule", False),
        "activation_mode": source_meta.get("activation_mode"),
        "changed_articles": changed_articles,
        "matched_sensitive_keywords": list(set(matched_keywords)),
        "impact_level": impact_level,
        "requires_interpretation_review": requires_review,
        "recommended_action": recommended_action
    }


if __name__ == "__main__":
    # Self-test: verify action mapping
    for level, action in ACTION_MAP.items():
        print(f"  {level} → {action}")
    print("Impact classifier v0.1.1 loaded successfully.")
