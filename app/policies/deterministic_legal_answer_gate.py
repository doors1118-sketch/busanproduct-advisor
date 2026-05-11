"""
Deterministic legal answer gate for high-frequency procurement standards.

These answers cover narrow, repeatedly asked 기준/정의/한도 questions where
free-form LLM generation tends to add noise or mix unrelated thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

try:
    from policies.numeric_basis_policy import get_numeric_display, get_numeric_value, get_rule_source_titles
except ImportError:
    from importlib import import_module

    _numeric_basis_policy = import_module("app.policies.numeric_basis_policy")
    get_numeric_display = _numeric_basis_policy.get_numeric_display
    get_numeric_value = _numeric_basis_policy.get_numeric_value
    get_rule_source_titles = _numeric_basis_policy.get_rule_source_titles


@dataclass(frozen=True)
class DeterministicLegalAnswer:
    answer: str
    reason: str
    schema_version: str


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _item_hint(text: str) -> str:
    for term in (
        "냉난방기", "보안용카메라", "CCTV", "노트북", "컴퓨터", "프린터",
        "서버", "LED조명", "LED", "사무가구", "가구",
    ):
        if term.lower() in (text or "").lower():
            return "LED 조명" if term == "LED" else term
    return ""


def _num(parameter_ref: str, fallback: str = "기준값 확인 필요") -> str:
    return get_numeric_display(parameter_ref) or fallback


def _money_limit(parameter_ref: str, suffix: str = " 이하") -> str:
    display = get_numeric_display(parameter_ref)
    return f"{display}{suffix}" if display else "기준값 확인 필요"


def _regional_amount_line(agency: str, parameter_ref: str, basis: str) -> list[str]:
    amount = _money_limit(parameter_ref, " 미만")
    return [
        f"- **{agency}**: **{amount}**",
        f"  근거: {basis}",
    ]


def match_deterministic_legal_answer(user_message: str) -> DeterministicLegalAnswer | None:
    q = _compact(user_message)

    if _is_agency_law_conflict(q):
        return None

    if _is_policy_company_product_counted_as_sme_performance(q):
        return DeterministicLegalAnswer(
            answer=_policy_company_product_counted_as_sme_performance_answer(),
            reason="policy_company_product_counted_as_sme_performance_fast_answer",
            schema_version="policy_company_product_counted_as_sme_performance_v1",
        )

    if _is_sme_small_business_priority_procurement(q):
        return DeterministicLegalAnswer(
            answer=_sme_small_business_priority_procurement_answer(),
            reason="sme_small_business_priority_procurement_fast_answer",
            schema_version="sme_small_business_priority_procurement_v1",
        )

    if _is_performance_certified_product_documents_question(q):
        return DeterministicLegalAnswer(
            answer=_performance_certified_product_documents_answer(),
            reason="performance_certified_product_documents_fast_answer",
            schema_version="performance_certified_product_documents_v1",
        )

    if _is_department_performance_score_question(q):
        return DeterministicLegalAnswer(
            answer=_department_performance_score_answer(),
            reason="department_performance_score_fast_answer",
            schema_version="department_performance_score_v1",
        )

    if _is_sme_competition_no_local_direct_producer_question(q):
        return DeterministicLegalAnswer(
            answer=_sme_competition_no_local_direct_producer_answer(),
            reason="sme_competition_no_local_direct_producer_fast_answer",
            schema_version="sme_competition_no_local_direct_producer_v1",
        )

    if _is_expired_small_business_certificate_question(q):
        return DeterministicLegalAnswer(
            answer=_expired_small_business_certificate_answer(),
            reason="expired_small_business_certificate_fast_answer",
            schema_version="expired_small_business_certificate_v1",
        )

    if _is_policy_performance_double_count_question(q):
        return DeterministicLegalAnswer(
            answer=_policy_performance_double_count_answer(),
            reason="policy_performance_double_count_fast_answer",
            schema_version="policy_performance_double_count_v1",
        )

    if _is_public_material_local_review_committee_question(q):
        return DeterministicLegalAnswer(
            answer=_public_material_local_review_committee_answer(),
            reason="public_material_local_review_committee_fast_answer",
            schema_version="public_material_local_review_committee_v1",
        )

    if _is_sme_competition_policy_company_direct_contract_question(q):
        return DeterministicLegalAnswer(
            answer=_sme_competition_policy_company_direct_contract_answer(),
            reason="sme_competition_policy_company_direct_contract_fast_answer",
            schema_version="sme_competition_policy_company_direct_contract_v1",
        )

    if _is_startup_product_priority_purchase_question(q):
        return DeterministicLegalAnswer(
            answer=_startup_product_priority_purchase_answer(),
            reason="startup_product_priority_purchase_fast_answer",
            schema_version="startup_product_priority_purchase_v1",
        )

    if _is_coop_recommendation_direct_contract_question(q):
        return DeterministicLegalAnswer(
            answer=_coop_recommendation_direct_contract_answer(),
            reason="coop_recommendation_direct_contract_fast_answer",
            schema_version="coop_recommendation_direct_contract_v1",
        )

    if _is_cancelled_direct_production_contract_question(q):
        return DeterministicLegalAnswer(
            answer=_cancelled_direct_production_contract_answer(),
            reason="cancelled_direct_production_contract_fast_answer",
            schema_version="cancelled_direct_production_contract_v1",
        )

    if _is_early_payment_local_small_business_question(q):
        return DeterministicLegalAnswer(
            answer=_early_payment_local_small_business_answer(),
            reason="early_payment_local_small_business_fast_answer",
            schema_version="early_payment_local_small_business_v1",
        )

    if _is_shopping_mall_busan_vendor_filter_question(q):
        return DeterministicLegalAnswer(
            answer=_shopping_mall_busan_vendor_filter_answer(),
            reason="shopping_mall_busan_vendor_filter_fast_answer",
            schema_version="shopping_mall_busan_vendor_filter_v1",
        )

    if _is_desktop_mas_second_stage_threshold_question(q):
        return DeterministicLegalAnswer(
            answer=_desktop_mas_second_stage_threshold_answer(),
            reason="desktop_mas_second_stage_threshold_fast_answer",
            schema_version="desktop_mas_second_stage_threshold_v1",
        )

    if _is_mas_candidate_must_include_local_vendor_question(q):
        return DeterministicLegalAnswer(
            answer=_mas_candidate_must_include_local_vendor_answer(),
            reason="mas_candidate_must_include_local_vendor_fast_answer",
            schema_version="mas_candidate_must_include_local_vendor_v1",
        )

    if _is_mas_regional_point_amount_question(q):
        return DeterministicLegalAnswer(
            answer=_mas_regional_point_amount_answer(),
            reason="mas_regional_point_amount_fast_answer",
            schema_version="mas_regional_point_amount_v1",
        )

    if _is_local_vendor_higher_price_audit_risk_question(q):
        return DeterministicLegalAnswer(
            answer=_local_vendor_higher_price_audit_risk_answer(),
            reason="local_vendor_higher_price_audit_risk_fast_answer",
            schema_version="local_vendor_higher_price_audit_risk_v1",
        )

    if _is_third_party_local_specialty_innovation_search_question(q):
        return DeterministicLegalAnswer(
            answer=_third_party_local_specialty_innovation_search_answer(),
            reason="third_party_local_specialty_innovation_search_fast_answer",
            schema_version="third_party_local_specialty_innovation_search_v1",
        )

    if _is_mas_non_lowest_local_vendor_selection_question(q):
        return DeterministicLegalAnswer(
            answer=_mas_non_lowest_local_vendor_selection_answer(),
            reason="mas_non_lowest_local_vendor_selection_fast_answer",
            schema_version="mas_non_lowest_local_vendor_selection_v1",
        )

    if _is_excellent_procurement_shopping_mall_order_question(q):
        return DeterministicLegalAnswer(
            answer=_excellent_procurement_shopping_mall_order_answer(),
            reason="excellent_procurement_shopping_mall_order_fast_answer",
            schema_version="excellent_procurement_shopping_mall_order_v1",
        )

    if _is_innovative_prototype_pilot_purchase_question(q):
        return DeterministicLegalAnswer(
            answer=_innovative_prototype_pilot_purchase_answer(),
            reason="innovative_prototype_pilot_purchase_fast_answer",
            schema_version="innovative_prototype_pilot_purchase_v1",
        )

    if _is_supplier_shopping_mall_entry_support_question(q):
        return DeterministicLegalAnswer(
            answer=_supplier_shopping_mall_entry_support_answer(),
            reason="supplier_shopping_mall_entry_support_fast_answer",
            schema_version="supplier_shopping_mall_entry_support_v1",
        )

    if _is_mas_local_participation_score_increase_question(q):
        return DeterministicLegalAnswer(
            answer=_mas_local_participation_score_increase_answer(),
            reason="mas_local_participation_score_increase_fast_answer",
            schema_version="mas_local_participation_score_increase_v1",
        )

    if _is_desired_quantity_bid_split_delivery_question(q):
        return DeterministicLegalAnswer(
            answer=_desired_quantity_bid_split_delivery_answer(),
            reason="desired_quantity_bid_split_delivery_fast_answer",
            schema_version="desired_quantity_bid_split_delivery_v1",
        )

    if _is_unregistered_shopping_mall_local_product_direct_contract_question(q):
        return DeterministicLegalAnswer(
            answer=_unregistered_shopping_mall_local_product_direct_contract_answer(),
            reason="unregistered_shopping_mall_local_product_direct_contract_fast_answer",
            schema_version="unregistered_shopping_mall_local_product_direct_contract_v1",
        )

    if _is_shopping_mall_lower_spec_higher_price_justification_question(q):
        return DeterministicLegalAnswer(
            answer=_shopping_mall_lower_spec_higher_price_justification_answer(),
            reason="shopping_mall_lower_spec_higher_price_justification_fast_answer",
            schema_version="shopping_mall_lower_spec_higher_price_justification_v1",
        )

    if _is_mas_two_local_vendors_only_question(q):
        return DeterministicLegalAnswer(
            answer=_mas_two_local_vendors_only_answer(),
            reason="mas_two_local_vendors_only_fast_answer",
            schema_version="mas_two_local_vendors_only_v1",
        )

    if _is_streetlight_fixture_public_material_question(q):
        return DeterministicLegalAnswer(
            answer=_streetlight_fixture_public_material_answer(),
            reason="streetlight_fixture_public_material_fast_answer",
            schema_version="streetlight_fixture_public_material_v1",
        )

    if _is_info_telecom_cctv_separate_procurement_question(q):
        return DeterministicLegalAnswer(
            answer=_info_telecom_cctv_separate_procurement_answer(),
            reason="info_telecom_cctv_separate_procurement_fast_answer",
            schema_version="info_telecom_cctv_separate_procurement_v1",
        )

    if _is_construction_waste_distance_restriction_question(q):
        return DeterministicLegalAnswer(
            answer=_construction_waste_distance_restriction_answer(),
            reason="construction_waste_distance_restriction_fast_answer",
            schema_version="construction_waste_distance_restriction_v1",
        )

    if _is_distance_based_regional_restriction_question(q):
        return DeterministicLegalAnswer(
            answer=_distance_based_regional_restriction_answer(),
            reason="distance_based_regional_restriction_fast_answer",
            schema_version="distance_based_regional_restriction_v1",
        )

    if _is_landscape_local_tree_spec_question(q):
        return DeterministicLegalAnswer(
            answer=_landscape_local_tree_spec_answer(),
            reason="landscape_local_tree_spec_fast_answer",
            schema_version="landscape_local_tree_spec_v1",
        )

    if _is_split_contract_to_distribute_local_vendors_question(q):
        return DeterministicLegalAnswer(
            answer=_split_contract_to_distribute_local_vendors_answer(),
            reason="split_contract_to_distribute_local_vendors_fast_answer",
            schema_version="split_contract_to_distribute_local_vendors_v1",
        )

    if _is_design_service_with_printing_question(q):
        return DeterministicLegalAnswer(
            answer=_design_service_with_printing_answer(),
            reason="design_service_with_printing_fast_answer",
            schema_version="design_service_with_printing_v1",
        )

    if _is_electrical_work_split_performance_joint_question(q):
        return DeterministicLegalAnswer(
            answer=_electrical_work_split_performance_joint_answer(),
            reason="electrical_work_split_performance_joint_fast_answer",
            schema_version="electrical_work_split_performance_joint_v1",
        )

    if _is_contractor_bankruptcy_remaining_work_direct_contract_question(q):
        return DeterministicLegalAnswer(
            answer=_contractor_bankruptcy_remaining_work_direct_contract_answer(),
            reason="contractor_bankruptcy_remaining_work_direct_contract_fast_answer",
            schema_version="contractor_bankruptcy_remaining_work_direct_contract_v1",
        )

    if _is_public_material_small_construction_exception_question(q):
        return DeterministicLegalAnswer(
            answer=_public_material_small_construction_exception_answer(),
            reason="public_material_small_construction_exception_fast_answer",
            schema_version="public_material_small_construction_exception_v1",
        )

    if _is_regional_bid_no_bid_reannouncement_expand_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_bid_no_bid_reannouncement_expand_answer(),
            reason="regional_bid_no_bid_reannouncement_expand_fast_answer",
            schema_version="regional_bid_no_bid_reannouncement_expand_v1",
        )

    if _is_annual_unit_price_contract_local_share_question(q):
        return DeterministicLegalAnswer(
            answer=_annual_unit_price_contract_local_share_answer(),
            reason="annual_unit_price_contract_local_share_fast_answer",
            schema_version="annual_unit_price_contract_local_share_v1",
        )

    if _is_event_service_local_artist_scope_statement_question(q):
        return DeterministicLegalAnswer(
            answer=_event_service_local_artist_scope_statement_answer(),
            reason="event_service_local_artist_scope_statement_fast_answer",
            schema_version="event_service_local_artist_scope_statement_v1",
        )

    if _is_software_maintenance_resident_staff_question(q):
        return DeterministicLegalAnswer(
            answer=_software_maintenance_resident_staff_answer(),
            reason="software_maintenance_resident_staff_fast_answer",
            schema_version="software_maintenance_resident_staff_v1",
        )

    if _is_local_product_purchase_goal_calculation_question(q):
        return DeterministicLegalAnswer(
            answer=_local_product_purchase_goal_calculation_answer(),
            reason="local_product_purchase_goal_calculation_fast_answer",
            schema_version="local_product_purchase_goal_calculation_v1",
        )

    if _is_public_contract_monitoring_local_purchase_ratio_question(q):
        return DeterministicLegalAnswer(
            answer=_public_contract_monitoring_local_purchase_ratio_answer(),
            reason="public_contract_monitoring_local_purchase_ratio_fast_answer",
            schema_version="public_contract_monitoring_local_purchase_ratio_v1",
        )

    if _is_local_purchase_performance_branch_or_dealer_question(q):
        return DeterministicLegalAnswer(
            answer=_local_purchase_performance_branch_or_dealer_answer(q),
            reason="local_purchase_performance_branch_or_dealer_fast_answer",
            schema_version="local_purchase_performance_branch_or_dealer_v1",
        )

    if _is_local_vendor_direct_contract_reason_template_question(q):
        return DeterministicLegalAnswer(
            answer=_local_vendor_direct_contract_reason_template_answer(),
            reason="local_vendor_direct_contract_reason_template_fast_answer",
            schema_version="local_vendor_direct_contract_reason_template_v1",
        )

    if _is_active_administration_audit_defense_question(q):
        return DeterministicLegalAnswer(
            answer=_active_administration_audit_defense_answer(),
            reason="active_administration_audit_defense_fast_answer",
            schema_version="active_administration_audit_defense_v1",
        )

    if _is_local_purchase_award_evidence_question(q):
        return DeterministicLegalAnswer(
            answer=_local_purchase_award_evidence_answer(),
            reason="local_purchase_award_evidence_fast_answer",
            schema_version="local_purchase_award_evidence_v1",
        )

    if _is_chatbot_recommended_paper_company_responsibility_question(q):
        return DeterministicLegalAnswer(
            answer=_chatbot_recommended_paper_company_responsibility_answer(),
            reason="chatbot_recommended_paper_company_responsibility_fast_answer",
            schema_version="chatbot_recommended_paper_company_responsibility_v1",
        )

    if _is_busan_local_purchase_guideline_pdf_question(q):
        return DeterministicLegalAnswer(
            answer=_busan_local_purchase_guideline_pdf_answer(),
            reason="busan_local_purchase_guideline_pdf_fast_answer",
            schema_version="busan_local_purchase_guideline_pdf_v1",
        )

    if _is_procurement_api_credit_check_question(q):
        return DeterministicLegalAnswer(
            answer=_procurement_api_credit_check_answer(),
            reason="procurement_api_credit_check_fast_answer",
            schema_version="procurement_api_credit_check_v1",
        )

    if _is_low_local_purchase_ratio_penalty_question(q):
        return DeterministicLegalAnswer(
            answer=_low_local_purchase_ratio_penalty_answer(),
            reason="low_local_purchase_ratio_penalty_fast_answer",
            schema_version="low_local_purchase_ratio_penalty_v1",
        )

    if _is_innovation_product_purchase_review(q):
        return DeterministicLegalAnswer(
            answer=_innovation_product_purchase_review_answer(),
            reason="innovation_product_purchase_fast_answer",
            schema_version="innovation_product_purchase_v1",
        )

    if _is_public_corp_direct_contract_difference(q):
        return DeterministicLegalAnswer(
            answer=_public_corp_direct_contract_difference_answer(),
            reason="public_corp_direct_contract_difference_fast_answer",
            schema_version="public_corp_direct_contract_difference_v1",
        )

    if _is_construction_repair_direct_limit_question(q):
        return DeterministicLegalAnswer(
            answer=_construction_repair_direct_limit_answer(),
            reason="construction_repair_direct_limit_fast_answer",
            schema_version="construction_repair_direct_limit_v1",
        )

    if _is_factory_location_regional_restriction_question(q):
        return DeterministicLegalAnswer(
            answer=_factory_location_regional_restriction_answer(),
            reason="factory_location_regional_restriction_fast_answer",
            schema_version="factory_location_regional_restriction_v1",
        )

    if _is_specific_regional_restriction_amount_question(q):
        return DeterministicLegalAnswer(
            answer=_specific_regional_restriction_amount_answer(q),
            reason="specific_regional_restriction_amount_fast_answer",
            schema_version="specific_regional_restriction_amount_v1",
        )

    if _is_regional_restriction_location_date_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_restriction_location_date_answer(),
            reason="regional_restriction_location_date_fast_answer",
            schema_version="regional_restriction_location_date_v1",
        )

    if _is_single_bidder_rebid_question(q):
        return DeterministicLegalAnswer(
            answer=_single_bidder_rebid_answer(),
            reason="single_bidder_rebid_fast_answer",
            schema_version="single_bidder_rebid_v1",
        )

    if _is_info_telecom_large_bid_strategy_question(q):
        return DeterministicLegalAnswer(
            answer=_info_telecom_large_bid_strategy_answer(q),
            reason="info_telecom_large_bid_strategy_fast_answer",
            schema_version="info_telecom_large_bid_strategy_v1",
        )

    if _is_combined_adjacent_region_restriction_question(q):
        return DeterministicLegalAnswer(
            answer=_combined_adjacent_region_restriction_answer(),
            reason="combined_adjacent_region_restriction_fast_answer",
            schema_version="combined_adjacent_region_restriction_v1",
        )

    if _is_service_regional_limit_law_comparison_question(q):
        return DeterministicLegalAnswer(
            answer=_service_regional_limit_law_comparison_answer(),
            reason="service_regional_limit_law_comparison_fast_answer",
            schema_version="service_regional_limit_law_comparison_v1",
        )

    if _is_local_performance_requirement_question(q):
        return DeterministicLegalAnswer(
            answer=_local_performance_requirement_answer(),
            reason="local_performance_requirement_fast_answer",
            schema_version="local_performance_requirement_v1",
        )

    if _is_negotiated_contract_regional_point_question(q):
        return DeterministicLegalAnswer(
            answer=_negotiated_contract_regional_point_answer(),
            reason="negotiated_contract_regional_point_fast_answer",
            schema_version="negotiated_contract_regional_point_v1",
        )

    if _is_sme_small_business_regional_combined_bid_question(q):
        return DeterministicLegalAnswer(
            answer=_sme_small_business_regional_combined_bid_answer(q),
            reason="sme_small_business_regional_combined_bid_fast_answer",
            schema_version="sme_small_business_regional_combined_bid_v1",
        )

    if _is_regional_representative_joint_score_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_representative_joint_score_answer(),
            reason="regional_representative_joint_score_fast_answer",
            schema_version="regional_representative_joint_score_v1",
        )

    if _is_international_bid_local_preference_question(q):
        return DeterministicLegalAnswer(
            answer=_international_bid_local_preference_answer(),
            reason="international_bid_local_preference_fast_answer",
            schema_version="international_bid_local_preference_v1",
        )

    if _is_branch_only_regional_restriction_question(q):
        return DeterministicLegalAnswer(
            answer=_branch_only_regional_restriction_answer(),
            reason="branch_only_regional_restriction_fast_answer",
            schema_version="branch_only_regional_restriction_v1",
        )

    if _is_large_goods_no_regional_support_question(q):
        return DeterministicLegalAnswer(
            answer=_large_goods_no_regional_support_answer(q),
            reason="large_goods_no_regional_support_fast_answer",
            schema_version="large_goods_no_regional_support_v1",
        )

    if _is_ordinance_upper_law_conflict_question(q):
        return DeterministicLegalAnswer(
            answer=_ordinance_upper_law_conflict_answer(),
            reason="ordinance_upper_law_conflict_fast_answer",
            schema_version="ordinance_upper_law_conflict_v1",
        )

    if _is_joint_contract_agreement_breach_question(q):
        return DeterministicLegalAnswer(
            answer=_joint_contract_agreement_breach_answer(),
            reason="joint_contract_agreement_breach_fast_answer",
            schema_version="joint_contract_agreement_breach_v1",
        )

    if _is_sme_competition_local_mandatory_purchase_question(q):
        return DeterministicLegalAnswer(
            answer=_sme_competition_local_mandatory_purchase_answer(q),
            reason="sme_competition_local_mandatory_purchase_fast_answer",
            schema_version="sme_competition_local_mandatory_purchase_v1",
        )

    if _is_direct_production_busan_vendor_search_question(q):
        return DeterministicLegalAnswer(
            answer=_direct_production_busan_vendor_search_answer(),
            reason="direct_production_busan_vendor_search_fast_answer",
            schema_version="direct_production_busan_vendor_search_v1",
        )

    if _is_public_material_direct_purchase_busan_list_question(q):
        return DeterministicLegalAnswer(
            answer=_public_material_direct_purchase_busan_list_answer(),
            reason="public_material_direct_purchase_busan_list_fast_answer",
            schema_version="public_material_direct_purchase_busan_list_v1",
        )

    if _is_sme_product_priority_vs_busan_local_question(q):
        return DeterministicLegalAnswer(
            answer=_sme_product_priority_vs_busan_local_answer(q),
            reason="sme_product_priority_vs_busan_local_fast_answer",
            schema_version="sme_product_priority_vs_busan_local_v1",
        )

    if _is_regional_restriction(q):
        return DeterministicLegalAnswer(
            answer=_regional_restriction_answer(q),
            reason="regional_restriction_standard_fast_answer",
            schema_version="regional_restriction_standard_v1",
        )

    if _is_two_quote_regional_limit_question(q):
        return DeterministicLegalAnswer(
            answer=_two_quote_regional_limit_answer(),
            reason="two_quote_regional_limit_fast_answer",
            schema_version="two_quote_regional_limit_v1",
        )

    if _is_vat_threshold_basis_question(q):
        return DeterministicLegalAnswer(
            answer=_vat_threshold_basis_answer(),
            reason="vat_threshold_basis_fast_answer",
            schema_version="vat_threshold_basis_v1",
        )

    if _is_sole_contract(q):
        return DeterministicLegalAnswer(
            answer=_sole_contract_answer(q),
            reason="sole_contract_standard_fast_answer",
            schema_version="sole_contract_standard_v1",
        )

    if _is_local_company_point(q):
        return DeterministicLegalAnswer(
            answer=_local_company_point_answer(q),
            reason="local_company_point_standard_fast_answer",
            schema_version="local_company_point_standard_v1",
        )

    if _is_mas_second_stage_threshold_comparison(q):
        return DeterministicLegalAnswer(
            answer=_mas_second_stage_threshold_comparison_answer(),
            reason="mas_second_stage_threshold_comparison_fast_answer",
            schema_version="mas_second_stage_threshold_comparison_v1",
        )

    if _is_excellent_procurement_or_third_party(q):
        return DeterministicLegalAnswer(
            answer=_excellent_procurement_or_third_party_answer(),
            reason="excellent_procurement_third_party_fast_answer",
            schema_version="excellent_procurement_third_party_v1",
        )

    if _is_split_purchase_audit_review(q):
        return DeterministicLegalAnswer(
            answer=_split_purchase_audit_review_answer(q),
            reason="split_purchase_audit_fast_answer",
            schema_version="split_purchase_audit_v1",
        )

    if _is_audit_risk_review(q):
        return DeterministicLegalAnswer(
            answer=_audit_risk_review_answer(),
            reason="audit_risk_fast_answer",
            schema_version="audit_risk_v1",
        )

    if _is_mas_regional_review(q):
        if _should_defer_mas_purchase_to_route_flow(q):
            return None
        return DeterministicLegalAnswer(
            answer=_mas_regional_review_answer(q),
            reason="mas_regional_review_fast_answer",
            schema_version="mas_regional_review_v1",
        )

    if _is_regional_mandatory_point_exclusion_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_point_exclusion_answer(),
            reason="regional_mandatory_point_exclusion_fast_answer",
            schema_version="regional_mandatory_point_exclusion_v1",
        )

    if _is_regional_mandatory_joint_contract_invalid_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_joint_contract_invalid_answer(),
            reason="regional_mandatory_joint_contract_invalid_fast_answer",
            schema_version="regional_mandatory_joint_contract_invalid_v1",
        )

    if _is_regional_mandatory_joint_contract_share_question(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_joint_contract_share_answer(q),
            reason="regional_mandatory_joint_contract_share_fast_answer",
            schema_version="regional_mandatory_joint_contract_share_v1",
        )

    if _is_regional_mandatory_joint_contract(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_joint_contract_answer(q),
            reason="regional_mandatory_joint_contract_fast_answer",
            schema_version="regional_mandatory_joint_contract_v1",
        )

    return None


def _is_regional_restriction(q: str) -> bool:
    if not ("지역제한" in q or "지역제한경쟁" in q):
        return False
    if not any(term in q for term in ("기준", "금액", "얼마", "몇억", "100억", "150억", "88억", "비교")):
        return False
    if "종합공사" in q or "건설공사" in q:
        return True
    agency_compare = sum([
        "국가" in q,
        "공기업" in q or "준정부" in q or "공공기관" in q,
        "지방" in q or "지방자치단체" in q or "지자체" in q,
    ]) >= 2
    return agency_compare


def _is_specific_regional_restriction_amount_question(q: str) -> bool:
    has_regional_limit = any(term in q for term in ("지역제한", "지역을제한", "부산업체로만", "부산업체만", "부산제한"))
    has_amount = _extract_amount_won(q) is not None
    has_target = any(term in q for term in ("일반용역", "용역", "전문공사", "종합공사", "공사"))
    asks_possibility = any(term in q for term in ("가능", "수있", "되나", "되나요", "금액", "기준", "한도"))
    return has_regional_limit and has_amount and has_target and asks_possibility


def _specific_regional_restriction_amount_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_label = _format_won(amount) if amount is not None else "질문 금액"
    local_general = _money_limit("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    local_specialty = _money_limit("P_LOCAL_LIMITED_BID_SPECIALTY_CONSTRUCTION_THRESHOLD", " 미만")
    local_technical_service = _money_limit("P_LOCAL_LIMITED_BID_TECHNICAL_SERVICE_THRESHOLD", " 미만")
    local_safety_service = _money_limit("P_LOCAL_LIMITED_BID_SAFETY_DIAGNOSIS_SERVICE_THRESHOLD", " 미만")
    local_general_service = get_numeric_display("P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD")
    local_general_service_label = local_general_service or "행정안전부장관 고시금액 미만"
    busan_gu_gun = _money_limit("P_LOCAL_LIMITED_BID_SEOUL_BUSAN_INCHEON_GU_GUN_THRESHOLD", " 미만")

    if "전문공사" in q:
        threshold = get_numeric_value("P_LOCAL_LIMITED_BID_SPECIALTY_CONSTRUCTION_THRESHOLD")
        over = isinstance(threshold, (int, float)) and amount is not None and amount >= threshold
        conclusion = (
            f"결론부터 보면, **{amount_label} 전문공사는 부산 지역제한을 걸 수 있는 금액대를 초과합니다.**"
            if over
            else f"결론부터 보면, **{amount_label} 전문공사는 전문공사 지역제한 기준 안인지 확인할 수 있는 구간입니다.**"
        )
        return "\n".join([
            f"### 전문공사 {amount_label} 부산 지역제한 검토",
            f"- {conclusion}",
            f"- 지방계약의 전문공사 및 그 밖의 공사 관련 법령에 따른 공사 지역제한 기준은 **추정가격 {local_specialty}**입니다.",
            "- 기준을 넘으면 `부산 업체만 입찰`로 참가자격을 묶기보다 일반경쟁 또는 전국입찰을 기본으로 두고, 지역의무 공동도급과 지역업체 참여도 평가를 따로 검토해야 합니다.",
            "",
            "| 구분 | 판단 |",
            "|---|---|",
            f"| 지역제한 | {local_specialty} 기준과 비교 |",
            f"| 질문 금액 | {amount_label} |",
            "| 대안 | 지역의무 공동도급, 공동수급 허용, 적격심사 지역업체 참여도, 현장 대응성 평가 |",
            "",
            "근거: 「지방계약법 시행규칙」 제24조, 「지방계약법 시행령」 제20조, 공동계약 관련 예규",
        ])

    if "종합공사" in q:
        threshold = get_numeric_value("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD")
        over = isinstance(threshold, (int, float)) and amount is not None and amount >= threshold
        conclusion = (
            f"결론부터 보면, **{amount_label} 종합공사는 지방계약 지역제한 기준을 초과하므로 부산 업체만 참가하게 하는 지역제한은 어렵습니다.**"
            if over
            else f"결론부터 보면, **{amount_label} 종합공사는 지방계약 종합공사 지역제한 기준 안인지 검토할 수 있습니다.**"
        )
        return "\n".join([
            f"### 종합공사 {amount_label} 부산 지역제한 검토",
            f"- {conclusion}",
            f"- 지방계약의 종합공사 지역제한 기준은 **추정가격 {local_general}**입니다.",
            "- 기준을 넘는 경우에는 부산 지역제한 대신 지역의무 공동도급, 지역업체 참여도 평가, 공동수급체 구성 조건을 검토합니다.",
            "",
            "근거: 「지방계약법 시행규칙」 제24조, 「지방계약법 시행령」 제20조",
        ])

    if "일반용역" in q or "용역" in q:
        return "\n".join([
            f"### 일반용역 {amount_label} 부산 지역제한 검토",
            "- 결론부터 보면, **일반용역은 공사 기준이나 기술용역 기준을 그대로 가져오면 안 됩니다.**",
            f"- 일반용역·물품의 시·도 지역제한은 **{local_general_service_label}**인지 확인해야 하고, 서울·부산·인천 관할 군·구 기준은 **{busan_gu_gun}**입니다.",
            f"- 질문 금액이 {amount_label}이면 적어도 `부산 관할 군·구 {busan_gu_gun}` 기준은 경계 또는 초과로 보아, 부산 업체만으로 제한한다고 바로 단정하면 위험합니다.",
            "",
            "| 용역 구분 | 지역제한 기준 | 주의점 |",
            "|---|---:|---|",
            f"| 일반용역 | {local_general_service_label} | 최신 행안부 고시금액 확인 필요 |",
            f"| 건설기술·설계·엔지니어링 용역 | {local_technical_service} | 일반용역에 기계적으로 적용하지 않음 |",
            f"| 안전점검·정밀안전진단 용역 | {local_safety_service} | 별도 낮은 기준 적용 |",
            f"| 부산 관할 군·구 일반용역·물품 | {busan_gu_gun} | `미만` 기준이므로 5억원은 포함되지 않음 |",
            "",
            "### 실무 대안",
            "- 지역제한 기준을 넘는다면 전국입찰 또는 일반경쟁을 기본으로 두고, 지역 현장 대응성·수행조직·긴급 대응·부산 지역 이해도를 평가항목으로 설계합니다.",
            "- 용역에는 공사식 지역의무 공동도급을 기계적으로 강제하지 말고, 공동수급 허용이나 지역업체 참여계획 평가가 해당 낙찰방식에서 가능한지 확인하세요.",
            "근거: 「지방계약법 시행규칙」 제24조, 「지방계약법 시행령」 제20조",
        ])

    return _regional_restriction_answer(q)


def _format_won(amount: int | None) -> str:
    if amount is None:
        return "질문 금액"
    if amount >= 100_000_000 and amount % 100_000_000 == 0:
        return f"{amount // 100_000_000}억원"
    if amount >= 10_000 and amount % 10_000 == 0:
        man = amount // 10_000
        if man >= 10_000:
            eok = man // 10_000
            rest = man % 10_000
            return f"{eok}억 {rest:,}만원" if rest else f"{eok}억원"
        return f"{man:,}만원"
    return f"{amount:,}원"


def _is_factory_location_regional_restriction_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역제한", "지역을제한", "지역제한입찰"))
        and any(term in q for term in ("공장", "제조공장", "생산공장", "제조장"))
        and any(term in q for term in ("물품", "구매", "제조", "입찰"))
    )


def _factory_location_regional_restriction_answer() -> str:
    return "\n".join([
        "### 물품 구매 입찰의 지역제한 기준",
        "- 결론부터 보면, **지역제한 입찰은 제조 공장 소재지가 아니라 주된 영업소, 즉 본점 소재지를 기준으로 설계하는 것이 원칙입니다.**",
        "- `부산에 제조 공장이 있는 업체만 참여`처럼 공장 소재지를 직접 제한하면 과도한 참가자격 제한이나 특정업체 유도 조건으로 볼 위험이 큽니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 지역제한 | 입찰공고일 전일부터 입찰일까지 주된 영업소가 부산광역시에 있는 업체로 제한 |",
        "| 제조능력 확인 | 직접생산확인증명서, 공장등록증, 생산설비, 납품능력은 품목 적격성 자료로 확인 |",
        "| 부산 제조업체 지원 | 본점 소재지 제한과 직접생산·납품능력 요건을 분리해 설계 |",
        "",
        "### 권장 문구",
        "- `입찰공고일 전일부터 입찰일까지 주된 영업소의 소재지가 부산광역시에 있는 업체`",
        "- 중소기업자간 경쟁제품이면 `직접생산확인증명서 보유 업체` 조건을 별도로 둡니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「지방계약법 시행규칙」 제24조",
    ])


def _is_regional_restriction_location_date_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역제한", "지역제한입찰", "지역제한경쟁"))
        and any(term in q for term in ("본점", "주된영업소", "소재지"))
        and any(term in q for term in ("기준일", "공고일", "입찰일", "계약일", "계약체결일", "언제"))
    )


def _regional_restriction_location_date_answer() -> str:
    return "\n".join([
        "### 지역제한 입찰의 본점 소재지 기준일",
        "- 결론부터 보면, **지역제한 입찰의 주된 영업소 소재지는 입찰공고일 전일을 기준으로 보고, 낙찰자는 계약체결일까지 그 소재지를 유지해야 합니다.**",
        "- 입찰일 하루만 부산이면 되는 구조가 아니므로 공고문과 나라장터 참가자격 설정을 함께 맞춰야 합니다.",
        "",
        "| 시점 | 실무 판단 |",
        "|---|---|",
        "| 입찰공고일 전일 | 법인등기부상 본점 또는 개인사업자 사업장 소재지 판단 기준 |",
        "| 입찰일 | 입찰일까지 부산 소재 요건 유지 필요 |",
        "| 계약체결일 | 낙찰자는 계약체결일까지 부산 소재 요건 유지 필요 |",
        "",
        "### 권장 공고문 문구",
        "- `입찰공고일 전일부터 입찰일까지 주된 영업소의 소재지가 부산광역시에 있는 업체이어야 하며, 낙찰자는 계약체결일까지 이를 유지하여야 합니다.`",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「지방계약법 시행규칙」 제24조, 「지방자치단체 입찰 및 계약집행기준」 제한입찰 운영 기준",
    ])


def _is_single_bidder_rebid_question(q: str) -> bool:
    return (
        any(term in q for term in ("1곳만", "1인만", "한곳만", "단독응찰", "1개업체", "1개사"))
        and any(term in q for term in ("투찰", "입찰", "응찰"))
        and any(term in q for term in ("재공고", "유찰", "해야", "하나요", "수의계약"))
    )


def _single_bidder_rebid_answer() -> str:
    return "\n".join([
        "### 지역제한 입찰에서 부산 업체 1곳만 투찰한 경우",
        "- 결론부터 보면, **유효한 입찰자가 1곳뿐이면 입찰이 성립하지 않은 것으로 보고 재공고입찰을 검토하는 것이 원칙입니다.**",
        "- 처음부터 바로 그 1개 업체와 수의계약으로 넘어가기보다, 동일 조건 재공고 또는 제한조건 완화 필요성을 먼저 검토해야 합니다.",
        "",
        "| 단계 | 처리 |",
        "|---|---|",
        "| 최초 공고 | 유효 입찰자가 1인뿐이면 유찰 처리 |",
        "| 재공고 | 같은 조건으로 재공고하되, 경쟁이 과도하게 제한됐는지 함께 점검 |",
        "| 재공고도 불성립·낙찰자 없음 | 시행령상 재공고입찰 후 수의계약 가능 사유 검토 |",
        "| 조건 변경 | 보증금·기한 외 최초 공고의 가격·조건 변경 제한 여부 확인 |",
        "",
        "### 실무 체크",
        "- 부산 지역제한, 실적제한, 면허·장비 조건이 중복되어 경쟁을 지나치게 줄였는지 시장조사표를 남기세요.",
        "- 재공고 후 수의계약을 검토하더라도 예정가격, 참가자격, 가격 적정성, 수의계약 배제사유 확인은 그대로 필요합니다.",
        "",
        "근거: 「지방계약법 시행령」의 입찰 성립·재공고입찰·재공고입찰 후 수의계약 규정",
    ])


def _is_info_telecom_large_bid_strategy_question(q: str) -> bool:
    amount = _extract_amount_won(q)
    return (
        "정보통신공사" in q
        and amount is not None
        and amount >= 1_000_000_000
        and any(term in q for term in ("부산업체", "부산", "지역업체"))
        and any(term in q for term in ("보호", "효과", "입찰방식", "발주", "방식", "전략"))
    )


def _info_telecom_large_bid_strategy_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_label = _format_won(amount) if amount is not None else "질문 금액"
    local_specialty = _money_limit("P_LOCAL_LIMITED_BID_SPECIALTY_CONSTRUCTION_THRESHOLD", " 미만")
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    min_company_count = _num("P_LOCAL_JOINT_CONTRACT_MIN_QUALIFIED_COMPANY_COUNT")
    return "\n".join([
        f"### 정보통신공사 {amount_label} 부산업체 보호 입찰 방식",
        f"- 결론부터 보면, **{amount_label} 정보통신공사는 부산 지역제한 입찰보다는 전국입찰을 기본으로 두고 지역의무 공동도급을 검토하는 방식이 안전합니다.**",
        f"- 정보통신공사 같은 그 밖의 공사 관련 법령에 따른 공사의 지역제한 기준은 **추정가격 {local_specialty}**로 보아야 하므로, 이 금액을 넘으면 부산 업체만 참가하게 제한하기 어렵습니다.",
        "",
        "| 장치 | 이 건 판단 | 실무 의미 |",
        "|---|---|---|",
        f"| 지역제한 | {local_specialty} 초과 시 곤란 | 부산업체만 투찰하도록 묶는 방식은 부당제한 위험 |",
        f"| 지역의무 공동도급 | {min_share} 원칙, 필요 시 {max_share} 이하 검토 | 외지 업체가 들어오더라도 부산업체 실제 시공 지분 확보 |",
        "| 면허요건 | 정보통신공사업 등록 확인 | 정보통신공사업법상 업종·등록 요건 명시 |",
        "| 분리발주 | 정보통신공사업법상 분리발주 원칙 확인 | 건축·전기 등과 임의 통합하거나 쪼개지 않도록 관리 |",
        "",
        "### 공고 전 확인",
        f"- 지역의무 공동도급을 넣기 전, 부산 내 정보통신공사업 등록업체 중 참여비율을 충족할 업체가 **{min_company_count} 이상**인지 확인하세요.",
        "- 50억원을 10억원 이하로 나누는 방식은 분할발주·쪼개기 발주로 감사 리스크가 큽니다.",
        "- 공고문에는 `지역의무 공동도급`, `부산업체 최소 시공참여비율`, `공동수급협정서 제출`, `정보통신공사업 등록`을 분리해 적는 것이 좋습니다.",
        "",
        "근거: 「지방계약법 시행규칙」 제24조, 「지방계약법 시행령」 제88조, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령, 「정보통신공사업법」",
    ])


def _is_combined_adjacent_region_restriction_question(q: str) -> bool:
    return (
        any(term in q for term in ("부산과경남", "부산경남", "부울경", "부산·경남", "부산,경남"))
        and any(term in q for term in ("지역제한", "지역을제한", "공동지역제한", "묶어서"))
        and any(term in q for term in ("허용", "가능", "되나요", "법적"))
    )


def _combined_adjacent_region_restriction_answer() -> str:
    return "\n".join([
        "### 부산·경남을 묶는 지역제한 가능성",
        "- 결론부터 보면, **지역제한은 원칙적으로 공사 현장·납품지·용역 결과물 납품지가 있는 시·도 단위로 제한합니다.**",
        "- 따라서 단순히 부산업체 참여를 늘리거나 경쟁률을 조절하려는 목적으로 `부산+경남`을 임의로 묶는 방식은 조심해야 합니다.",
        "",
        "| 구분 | 판단 |",
        "|---|---|",
        "| 원칙 | 해당 현장·납품지 소재 시·도 관할구역 안의 본점 소재 업체로 제한 |",
        "| 예외 1 | 공사 현장·납품지 등이 인접 시·도에 걸쳐 있는 경우 인접 시·도 포함 가능 |",
        "| 예외 2 | 인접 시·도에 납품지 또는 유지·보수·관리 대상 시설이 있는 경우 포함 가능 |",
        "| 예외 3 | 해당 지역에 사업 이행에 필요한 자격을 갖춘 업체가 10인 미만인 경우 인접 시·도 포함 가능 |",
        "",
        "### 실무 처리",
        "- 부산만으로 경쟁 가능한 업체 수가 충분하면 `부산광역시` 제한을 기본으로 봅니다.",
        "- 부산 업체가 10인 미만이거나 현장·납품지가 경남과 실질적으로 연결되는 경우에는 시장조사표와 법적 사유를 남긴 뒤 인접 시·도 포함을 검토하세요.",
        "- 공고문에는 `부산·경남 공동 지역제한`이라고만 쓰지 말고, 어떤 예외 사유 때문에 인접 시·도를 포함하는지 명시해야 합니다.",
        "",
        "근거: 「지방계약법 시행규칙」 제25조제3항",
    ])


def _is_service_regional_limit_law_comparison_question(q: str) -> bool:
    return (
        "용역" in q
        and any(term in q for term in ("지역제한", "지역제한금액", "한도", "금액"))
        and "국가계약법" in q
        and "지방계약법" in q
        and any(term in q for term in ("다른", "차이", "비교", "어떻게"))
    )


def _service_regional_limit_law_comparison_answer() -> str:
    national_goods_service = _money_limit("P_NATIONAL_LIMITED_BID_GOODS_SERVICE_THRESHOLD", " 미만")
    local_technical = _money_limit("P_LOCAL_LIMITED_BID_TECHNICAL_SERVICE_THRESHOLD", " 미만")
    local_safety = _money_limit("P_LOCAL_LIMITED_BID_SAFETY_DIAGNOSIS_SERVICE_THRESHOLD", " 미만")
    local_general_service = get_numeric_display("P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD")
    local_general_service_label = local_general_service or "행정안전부장관 고시금액 미만"
    local_busan_gu = _money_limit("P_LOCAL_LIMITED_BID_SEOUL_BUSAN_INCHEON_GU_GUN_THRESHOLD", " 미만")
    return "\n".join([
        "### 용역 지역제한 금액: 국가계약법과 지방계약법 비교",
        "- 결론부터 보면, **용역은 일반용역인지 기술용역인지 먼저 나눈 뒤 국가계약법과 지방계약법 기준을 비교해야 합니다.**",
        "- `지방계약 용역은 전부 3억 3천만원`처럼 답하면 안 됩니다. 3억 3천만원은 건설기술·설계·엔지니어링 등 기술용역 기준입니다.",
        "",
        "| 구분 | 국가계약법 기준 | 지방계약법 기준 |",
        "|---|---:|---:|",
        f"| 일반용역 | 국가계약법 제4조 고시금액 연동, 내부 기준 {national_goods_service} | {local_general_service_label}. 부산 관할 군·구 등은 {local_busan_gu} |",
        f"| 건설기술·건축설계·엔지니어링 용역 | 고시금액 연동 | {local_technical} |",
        f"| 안전점검·정밀안전진단 용역 | 고시금액 연동 | {local_safety} |",
        "",
        "### 실무 포인트",
        "- 국가기관·공기업·지방자치단체는 적용 법체계가 다르므로 지방계약의 부산 지역제한 기준을 국가계약에 그대로 가져오면 안 됩니다.",
        "- 일반용역은 최신 고시금액 확인이 필요한 값이고, 기술용역은 지방계약 시행규칙 제24조의 별도 금액을 적용합니다.",
        "",
        "근거: 「국가계약법 시행규칙」 제24조, 「지방계약법 시행규칙」 제24조",
    ])


def _is_local_performance_requirement_question(q: str) -> bool:
    return (
        any(term in q for term in ("부산내공사실적", "부산공사실적", "부산내실적", "부산지역실적", "부산소재기관실적"))
        and any(term in q for term in ("입찰참가자격", "참가자격", "필수", "넣어도", "가능"))
    )


def _local_performance_requirement_answer() -> str:
    return "\n".join([
        "### 입찰참가자격에 부산 내 공사 실적을 필수로 넣는 문제",
        "- 결론부터 보면, **`부산 내 공사 실적`을 필수 참가자격으로 두는 것은 특정 지역 실적 제한이어서 부당제한 위험이 큽니다.**",
        "- 지역업체 구매 실적을 높이려는 목적은 이해되지만, 실적제한은 과업 수행능력과 직접 관련된 동일·유사 실적으로 설계해야 하고 특정 지역 수행실적만 요구하면 안 됩니다.",
        "",
        "| 원하는 효과 | 안전한 설계 | 피해야 할 설계 |",
        "|---|---|---|",
        "| 부산업체 참여 확대 | 금액 기준이 맞으면 부산광역시 지역제한 | 부산 소재 기관 수행실적 필수 |",
        "| 공사 수행능력 확인 | 최근 10년 이내 동일·유사 공사 실적, 규모·금액 기준 | 부산 내 공사만 인정 |",
        "| 대형공사 지역 참여 | 지역의무 공동도급, 지역업체 참여도 평가 | 특정 부산 업체가 가진 실적에 맞춘 조건 |",
        "",
        "### 공고문 문구 방향",
        "- 실적은 `최근 ○년 이내 ○○공사 수행실적`처럼 과업의 종류·규모·난이도로 제한하세요.",
        "- 부산업체 보호는 지역제한, 지역의무 공동도급, 공동수급 허용, 지역업체 참여도 평가로 별도 설계하는 편이 안전합니다.",
        "",
        "근거: 「지방계약법 시행규칙」 제17조, 제25조",
    ])


def _is_two_quote_regional_limit_question(q: str) -> bool:
    return (
        ("수의계약" in q or "수의" in q)
        and any(term in q for term in ("2인이상견적", "견적제출", "견적"))
        and any(term in q for term in ("지역제한", "지역을제한", "부산광역시로제한", "부산으로제한", "부산제한"))
        and any(term in q for term in ("한도", "금액", "마지노선", "얼마"))
    )


def _two_quote_regional_limit_answer() -> str:
    general_construction = get_numeric_display("P_LOCAL_DIRECT_GENERAL_CONSTRUCTION_THRESHOLD") or "4억원"
    specialty_construction = get_numeric_display("P_LOCAL_DIRECT_SPECIALTY_CONSTRUCTION_THRESHOLD") or "2억원"
    other_construction = get_numeric_display("P_LOCAL_DIRECT_OTHER_CONSTRUCTION_THRESHOLD") or "1억 6천만원"
    goods_service = get_numeric_display("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD") or "1억원"
    one_quote_general = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    one_quote_policy = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "### 수의계약에서 부산 지역제한을 검토할 수 있는 금액대",
        "- 결론부터 보면, **2인 이상 견적 제출 수의계약은 계약 목적물별 소액수의 금액과 견적 제출 절차를 함께 봐야 합니다.**",
        "- 부산 지역제한을 붙이려면 단순히 지역만 정하는 것이 아니라, 계약유형·금액·참가자격을 함께 맞춰야 합니다.",
        "",
        "| 계약 유형 | 소액수의 검토 금액 | 부산 지역제한 실무 판단 |",
        "|---|---:|---|",
        f"| 종합공사 | {general_construction} 이하 | 공종·면허와 경쟁 가능한 부산업체 수 확인 후 2인 이상 견적 또는 입찰 검토 |",
        f"| 전문공사 | {specialty_construction} 이하 | 전문건설업 등록·면허와 부산 소재 요건을 함께 확인 |",
        f"| 그 밖의 공사 | {other_construction} 이하 | 전기·정보통신·소방 등 개별 법령 공사는 이 기준을 먼저 확인 |",
        f"| 물품·용역 | {goods_service} 이하 | G2B 2인 이상 견적 공고에서 부산 소재와 소기업·소상공인 등 자격을 함께 검토 |",
        "",
        "### 1인 견적과 혼동하면 안 되는 부분",
        f"- 일반 1인 견적은 보통 **추정가격 {one_quote_general} 이하**가 기본입니다.",
        f"- 여성기업·장애인기업·사회적기업·사회적협동조합 등 정책기업도 **1인 견적은 {one_quote_policy} 이하**인지 먼저 봐야 합니다.",
        f"- 정책기업과 체결 가능한 수의계약 범위가 {goods_service}까지 열리는 경우가 있더라도, {one_quote_policy} 초과 구간은 2인 이상 견적 절차를 분리해서 검토하는 것이 안전합니다.",
    ])


def _is_agency_law_conflict(q: str) -> bool:
    has_national_or_public = any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관"))
    has_local_law = any(term in q for term in ("지방계약", "지방자치단체", "지자체"))
    has_conflict_ask = any(term in q for term in (
        "그대로", "다르", "안되", "안되지", "혼동", "우대",
        "참고", "준용", "적용", "충돌", "차이",
    ))
    return has_national_or_public and has_local_law and has_conflict_ask


def _should_defer_mas_purchase_to_route_flow(q: str) -> bool:
    """품목 구매 실행 질문은 원칙답변보다 경로·후보 결합 플로우로 보낸다."""
    has_mas = any(term in q for term in ("종합쇼핑몰", "mas", "다수공급자", "나라장터", "제3자단가"))
    has_purchase_action = any(term in q for term in ("구매", "구입", "사면", "살수", "발주", "납품", "처리", "도입"))
    has_local_signal = any(term in q for term in ("부산", "지역업체", "부산업체", "관내업체", "지역상품", "부산상품"))
    has_execution_ask = any(term in q for term in ("가능", "방법", "어떻게", "고려", "안내", "처리", "검토", "해야"))
    return has_mas and has_purchase_action and has_local_signal and has_execution_ask


def _is_policy_company_product_counted_as_sme_performance(q: str) -> bool:
    has_policy_company = any(term in q for term in ("여성기업", "장애인기업", "여성기업제품", "장애인기업제품"))
    has_sme_performance = "중소기업제품" in q and any(term in q for term in ("구매실적", "실적", "구매목표", "목표비율"))
    asks_counting = any(term in q for term in ("포함", "인정", "잡히", "되는지", "되나요", "되나", "맞는지"))
    return has_policy_company and has_sme_performance and asks_counting


def _is_mas_second_stage_threshold_comparison(q: str) -> bool:
    has_mas = any(term in q for term in ("mas", "종합쇼핑몰", "합쇼핑몰", "다수공급자", "나라장터"))
    has_second_stage = any(term in q for term in ("2단계", "이단계", "제안요청"))
    has_threshold_ask = any(term in q for term in ("기준", "금액", "한도", "달라", "다르", "비교", "의무"))
    compares_product_types = (
        any(term in q for term in ("일반물품", "일반제품", "일반수요물자", "일반"))
        and any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
    )
    return has_mas and has_second_stage and has_threshold_ask and compares_product_types


def _source_title_list(rule_id: str) -> str:
    titles = get_rule_source_titles(rule_id, include_related=False, limit=2)
    return ", ".join(f"「{title}」" for title in titles) if titles else "내부 법령ㆍ행정규칙 DB"


def _mas_second_stage_threshold_comparison_answer() -> str:
    general_threshold = _num("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
    sme_threshold = _num("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")
    optional_min = _num("P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MIN")
    optional_max = _num("P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MAX")
    general_sources = _source_title_list("R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT")
    sme_sources = _source_title_list("R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION")

    return "\n".join([
        "결론부터 말하면, **현재 내부 법령ㆍ행정규칙 DB 기준으로 MAS 2단계 경쟁 기준은 일반 물품과 중소기업자간 경쟁제품에서 달라집니다.**",
        "기준 금액은 계약법의 일반 수의계약 한도가 아니라, 조달청 행정규칙인 「물품 다수공급자계약 업무처리규정」의 2단계경쟁 대상 규정에서 확인해야 합니다.",
        "",
        "### 1. 기준 금액 비교",
        "| 구분 | 2단계 경쟁 의무 기준 | 기준 미만 처리 | 실무 포인트 | 근거 |",
        "|---|---:|---|---|---|",
        f"| 중소기업자간 경쟁제품 | **1회 납품요구대상 구매예산 {sme_threshold} 이상** | {sme_threshold} 미만이면 2단계 경쟁 의무 기준 미만 | 먼저 세부품명이 중소기업자간 경쟁제품인지, 직접생산확인 대상인지 확인합니다. | {sme_sources}, 제49조제1항제1호 |",
        f"| 중소기업자간 경쟁제품이 아닌 일반 수요물자 | **1회 납품요구대상 구매예산 {general_threshold} 이상** | {general_threshold} 미만이면 2단계 경쟁 의무 기준 미만 | 일반 물품은 중기경쟁제품보다 낮은 금액에서 2단계 경쟁 검토가 시작됩니다. | {general_sources}, 제49조제1항제2호 |",
        f"| 일반 수요물자 중 `중소기업 제조품목` 예외 | 원칙은 {general_threshold} 이상이나, **{optional_min} 이상 {optional_max} 미만** 구간에서 예외 가능 | 요건 충족 시 2단계 경쟁 없이 납품대상업체 선정 가능 | 계약상대자가 해당 계약품목의 제조자이면서 중소기업인지 확인해야 합니다. | 「물품 다수공급자계약 업무처리규정」 제49조제4항 |",
        "",
        "### 2. 법령과 행정규칙의 역할",
        "- **법령 근거**: 다수공급자계약 제도 자체는 「조달사업에 관한 법률」 및 같은 법 시행령의 다수공급자계약 체계에서 출발합니다.",
        "- **금액 기준**: 실제 `5천만원`, `1억원` 같은 2단계 경쟁 기준은 조달청 행정규칙인 「물품 다수공급자계약 업무처리규정」 제49조에서 확인합니다.",
        "- **중소기업자간 경쟁제품 여부**: 해당 품목이 중기경쟁제품인지 여부는 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 체계와 `중소기업자간 경쟁제품 지정 내역`을 함께 봅니다.",
        "",
        "### 3. 왜 기준이 달라지는가",
        "- MAS 2단계 경쟁은 종합쇼핑몰에 이미 계약된 여러 업체 중 어느 업체에 납품요구할지를 다시 경쟁시키는 절차입니다.",
        "- 중소기업자간 경쟁제품은 판로지원법 체계에서 중소기업 보호와 직접생산 확인이 함께 작동하므로, 일반 물품과 같은 방식으로만 보지 않습니다.",
        "- 반대로 일반 물품은 중소기업자간 경쟁제품이 아니므로 원칙 기준이 더 낮게 잡혀 있습니다. 다만 중소기업이 직접 제조하는 일반 물품은 별도 예외 구간을 둡니다.",
        "",
        "### 4. 실무 확인 순서",
        "| 순서 | 확인할 것 | 확인 이유 |",
        "|---|---|---|",
        "| 1 | 세부품명번호와 품목명 | 중소기업자간 경쟁제품인지 일반 수요물자인지 먼저 갈립니다. |",
        "| 2 | 1회 납품요구대상 구매예산 | 2단계 경쟁 기준은 `추정가격` 표현보다 MAS 규정상 1회 납품요구대상 구매예산 기준으로 봅니다. |",
        "| 3 | 중소기업 제조품목 예외 여부 | 일반 수요물자라도 제조자인 중소기업이면 5천만원 이상 1억원 미만 구간에서 예외 검토가 가능합니다. |",
        "| 4 | 복수 품목 구매 여부 | 물품별 기준이 다르면 가장 낮은 기준금액을 적용합니다. |",
        "| 5 | 분할 납품요구 여부 | 2단계 경쟁 회피 목적의 분할 납품요구는 금지됩니다. |",
        "",
        "### 5. 주의할 조항",
        "- 「물품 다수공급자계약 업무처리규정」 제49조제6항은 여러 물품을 함께 구매할 때 물품별 기준금액이 다르면 **가장 낮은 기준금액**을 적용하도록 합니다.",
        "- 같은 규정 제51조는 2단계 경쟁 회피를 목적으로 기준금액 미만으로 쪼개 납품요구하는 것을 금지합니다.",
        "- 제52조는 2단계 경쟁 시 원칙적으로 종합쇼핑몰을 통해 복수 계약상대자에게 제안요청하는 절차를 둡니다.",
        "",
        "정리하면, **중소기업자간 경쟁제품은 1억원 이상, 일반 수요물자는 5천만원 이상**부터 MAS 2단계 경쟁 기준을 먼저 확인합니다. 다만 일반 수요물자 중 중소기업 제조품목은 5천만원 이상 1억원 미만 예외 구간이 있으므로, `일반/중기경쟁제품/중소기업 제조품목`을 분리해 판단해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 「물품 다수공급자계약 업무처리규정」 및 중소기업자간 경쟁제품 지정 자료의 숫자값을 사용한 참고 안내입니다.",
    ])


def _policy_company_product_counted_as_sme_performance_answer() -> str:
    return "\n".join([
        "네. **여성기업제품과 장애인기업제품 구매액은 원칙적으로 중소기업제품 구매실적에도 포함됩니다.**",
        "핵심 이유는 두 기업 유형의 법적 정의가 모두 `중소기업자`를 전제로 하기 때문입니다.",
        "",
        "### 1. 판단 요약",
        "- 여성기업제품과 장애인기업제품은 각각 별도의 의무구매·우선구매 실적 항목으로 구분해 관리합니다.",
        "- 동시에 여성기업과 장애인기업은 법령상 중소기업자 범주 안의 특수 유형이므로, 해당 구매액은 중소기업제품 총 구매실적에도 함께 반영하는 구조입니다.",
        "- 따라서 `중소기업제품 총 실적`과 `여성기업제품/장애인기업제품 세부 실적`을 구분해 관리하되, 여성기업·장애인기업 구매액을 중소기업제품 총 실적에서 제외할 필요는 없습니다.",
        "",
        "### 2. 법적 근거와 포함관계",
        "| 구분 | 확인할 법령 | 실무상 의미 |",
        "|---|---|---|",
        "| 중소기업제품 | 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 제5조 | 공공기관은 중소기업제품 구매계획과 전년도 구매실적을 작성·통보합니다. 여성·장애인기업제품 실적이 올라갈 상위 항목입니다. |",
        "| 여성기업제품 | 「여성기업지원에 관한 법률」 제2조 및 제9조 | 여성기업은 `중소기업자` 중 여성이 소유·경영하는 기업을 전제로 하고, 여성기업제품 구매계획·실적은 별도 항목으로 구분 관리됩니다. |",
        "| 장애인기업제품 | 「장애인기업활동 촉진법」 제2조 및 제9조의2 | 장애인기업도 `중소기업자` 중 장애인이 소유·경영하거나 요건을 갖춘 기업을 전제로 하고, 장애인기업제품 구매계획·실적은 별도 항목으로 구분 관리됩니다. |",
        "",
        "### 3. 실적 집계 구조",
        "- 집합관계로 보면 `중소기업제품 실적`이라는 상위 집합 안에 `여성기업제품`, `장애인기업제품`, `기술개발제품`, `창업기업제품` 같은 세부 실적 항목이 들어갑니다.",
        "- 예를 들어 한 부산 업체가 여성기업이면서 장애인기업이고, 그 업체에서 1억 원을 구매했다면 실무 집계는 다음처럼 봅니다.",
        "",
        "| 실적 항목 | 반영 방식 | 주의점 |",
        "|---|---|---|",
        "| 중소기업제품 총 실적 | 1억 원 반영 | 상위 총량에는 구매액을 한 번만 반영합니다. |",
        "| 여성기업제품 실적 | 1억 원 반영 | 여성기업확인서 등 해당 지위가 유효해야 합니다. |",
        "| 장애인기업제품 실적 | 1억 원 반영 | 장애인기업확인서 등 해당 지위가 유효해야 합니다. |",
        "",
        "- 세부 실적을 단순 합산하면 중소기업제품 총 실적보다 커질 수 있습니다. 총량은 사업자번호·계약건 등 기준으로 중복을 제거하고, 세부 지표는 각 정책 항목별로 별도 집계하는 방식이 안전합니다.",
        "",
        "### 4. 실무 입력·감사 대응 체크포인트",
        "- **확인서 유효성**: 여성기업확인서, 장애인기업확인서가 실적 인정 기준일에 유효한지 확인합니다. 실제 입력 전에는 해당 연도 공공구매종합정보망 기준에서 계약일·납품일·지출일 중 어느 시점을 기준으로 보는지 확인하세요.",
        "- **직접생산확인**: 중소기업자간 경쟁제품이면 여성·장애인기업 여부와 별개로 세부품명에 맞는 직접생산확인증명서가 필요합니다.",
        "- **SMPP 입력**: 공공구매종합정보망에서는 중소기업제품 총 실적과 여성기업제품·장애인기업제품 세부 실적을 구분해 입력·검증합니다.",
        "- **중복 합산 방지**: 내부 보고서에서 `여성기업 + 장애인기업 + 기타 정책기업`을 단순 합산해 중소기업제품 총액으로 쓰면 과대계상 위험이 있습니다.",
        "- **별도 제도 구분**: 중증장애인생산품, 장애인표준사업장 생산품, 사회적기업 제품은 별도 법령·실적 기준이 겹칠 수 있으므로 해당 항목의 인정 기준도 따로 확인합니다.",
        "",
        "### 5. 정리",
        "- 여성기업·장애인기업은 `중소기업의 특수 유형`이므로, 해당 구매는 중소기업제품 실적에 포함됩니다.",
        "- 다만 총 중소기업제품 실적은 중복 없이 한 번만 잡고, 여성기업·장애인기업 실적은 세부 정책지표로 별도 관리하는 방식이 맞습니다.",
        "- 부산업체 중 여성기업이면서 직접생산확인·기술개발제품·혁신제품 지위를 함께 가진 업체를 발굴하면, 지역업체 구매와 정책구매 실적을 동시에 관리하기 좋습니다.",
        "",
        "⚖️ 본 답변은 내부 법령 DB와 매뉴얼 기준의 참고 안내입니다. 실적 입력 전에는 해당 연도 공공구매종합정보망 입력 지침을 함께 확인하세요.",
    ])


def _is_sme_small_business_priority_procurement(q: str) -> bool:
    has_sme_competition = any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
    has_small_business = "소기업" in q or "소상공인" in q
    has_small_amount = any(term in q for term in ("1억원미만", "1억미만", "일억원미만"))
    amount = _extract_amount_won(q)
    threshold = get_numeric_value("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD")
    if amount is not None and isinstance(threshold, (int, float)) and amount < threshold:
        has_small_amount = True
    asks_limit = any(term in q for term in ("입찰참가자격", "제한", "맞", "해야", "원칙", "우선조달"))
    return has_sme_competition and has_small_business and has_small_amount and asks_limit


def _sme_small_business_priority_procurement_answer() -> str:
    threshold = _num("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD")
    return "\n".join([
        f"네. 질문 조건처럼 **중소기업자간 경쟁제품**이고 추정가격이 **{threshold} 미만**인 물품·용역이라면, 먼저 **소기업 또는 소상공인 간 제한경쟁입찰** 적용 여부를 검토하는 구조가 맞습니다.",
        "",
        "### 1. 판단 요약",
        f"- 중소기업자간 경쟁제품이라는 점만으로 곧바로 `중소기업자 전체`로 넓히기보다, 추정가격이 {threshold} 미만이면 판로지원법 시행령의 **소기업·소상공인 우선조달계약** 기준을 먼저 봅니다.",
        "- 다만 품목의 세부품명, 직접생산확인 대상 여부, 유찰·긴급 등 예외 사유가 있는지는 별도 확인해야 합니다.",
        "",
        "### 2. 근거 축",
        f"- **중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령 제2조의2**: 추정가격 {threshold} 미만 물품 또는 용역은 소기업 또는 소상공인 간 제한경쟁입찰로 조달계약을 체결하는 구조를 둡니다.",
        "- **중소기업제품 구매촉진 및 판로지원에 관한 법률 제7조**: 경쟁제품은 중소기업자만을 대상으로 하는 제한경쟁 또는 지명경쟁 입찰로 조달하는 원칙을 둡니다.",
        "- **지방계약법 시행령 제20조**: 중소기업자간 경쟁제품, 소기업·소상공인 등 입찰참가자격 제한의 계약법상 연결 근거를 확인합니다.",
        "",
        "### 3. 실무 처리 순서",
        "- 먼저 세부품명 기준으로 해당 품목이 중소기업자간 경쟁제품인지 확인합니다.",
        f"- 추정가격이 {threshold} 미만인지 산정합니다. 맞다면 소기업·소상공인 제한경쟁입찰을 우선 검토합니다.",
        "- 직접생산확인증명서가 필요한 품목이면 입찰참가자격에 직접생산확인 범위와 유효기간 확인을 넣습니다.",
        "- 소기업·소상공인 입찰에서 유찰되거나 적격자가 없는 등 예외 사유가 생기면 중소기업자 간 제한경쟁으로 넓힐 수 있는지 근거를 남깁니다.",
        "- 부산 지역업체 참여까지 검토하려면 별도로 지역제한 가능 금액, 지역 내 경쟁 가능한 업체 수, 부당제한 여부를 확인해야 합니다.",
        "",
        f"정리하면, **{threshold} 미만이면 소기업·소상공인 제한을 먼저 검토하고, 예외 사유가 있을 때 중소기업자 간 제한으로 전환하는지 따져보는 순서**가 안전합니다.",
        "⚖️ 본 답변은 내부 법령 DB 기준의 참고 안내입니다. 공고 전에는 최신 조문 원문과 해당 품목 고시를 함께 확인하세요.",
    ])


def _is_sole_contract(q: str) -> bool:
    # 금액과 계약종류가 함께 들어온 실제 사안형 질문은 DB 근거를 붙인 LLM
    # 흐름으로 넘긴다. 여기서는 "한도/기준표" 설명형 질문만 빠르게 처리한다.
    if _is_vat_threshold_basis_question(q):
        return False

    if _extract_amount_won(q) is not None and _contract_kind(q) is not None:
        return False

    checklist_intent = any(
        term in q
        for term in ("확인사항", "확인할", "검토할때", "검토시", "체크", "유의", "주의", "절차", "흐름")
    )
    explicit_standard_intent = any(term in q for term in ("기준", "한도", "금액", "얼마"))
    if checklist_intent and not explicit_standard_intent:
        return False

    return (
        "수의계약" in q
        and any(term in q for term in ("기준", "한도", "금액", "얼마", "1인견적", "견적"))
    )


def _is_vat_threshold_basis_question(q: str) -> bool:
    compact = re.sub(r"\s+", "", q).lower()
    has_vat = any(term in compact for term in ("부가가치세", "부가세", "vat"))
    has_basis_intent = any(
        term in compact
        for term in ("포함", "제외", "빼", "산입", "계산", "기준", "추정가격", "예정가격")
    )
    has_contract_intent = any(
        term in compact
        for term in ("수의계약", "1인견적", "견적", "계약한도", "한도")
    )
    return has_vat and has_basis_intent and has_contract_intent


def _is_public_corp_direct_contract_difference(q: str) -> bool:
    return (
        ("공기업" in q or "준정부기관" in q)
        and "계약사무규칙" in q
        and "수의계약" in q
        and ("국가계약" in q or "뭐가달라" in q or "차이" in q)
    )


def _public_corp_direct_contract_difference_answer() -> str:
    return "\n".join([
        "공기업·준정부기관에서 **수의계약**을 볼 때는 「공기업·준정부기관 계약사무규칙」과 국가계약법령의 준용 구조를 나누어 확인해야 합니다.",
        "",
        "- **공기업·준정부기관 계약사무규칙**",
        "  - 기관 계약사무의 기본 규칙과 준용 범위를 먼저 봅니다.",
        "  - 규칙 자체에 별도 기준이 있으면 그 기준을 우선 확인하고, 별도 규정이 없으면 국가계약법령 준용 여부를 확인합니다.",
        "",
        "- **국가계약법과의 차이**",
        "  - 국가기관 기준을 그대로 복사하기보다, 해당 공기업·준정부기관의 내부 계약규정, 위임전결, 자체 지침을 함께 확인해야 합니다.",
        "  - 수의계약 사유, 견적 방식, 금액 기준은 기관 자체 기준에서 달라질 수 있으므로 공고·계약 전 원문 확인이 필요합니다.",
        "",
        "정리하면, 공기업·준정부기관은 국가계약법령을 참고하되 `국가기관과 완전히 동일`하다고 단정하지 말고, 계약사무규칙과 기관 내부 기준을 같이 보는 구조입니다.",
    ])


def _is_construction_repair_direct_limit_question(q: str) -> bool:
    return (
        ("보수공사" in q or "청사보수" in q)
        and "수의계약" in q
        and ("종합공사" in q or "전문공사" in q)
    )


def _construction_repair_direct_limit_answer() -> str:
    return "\n".join([
        "청사 **보수공사**는 먼저 공사 범위와 면허·업종을 나누어 **종합공사**인지 **전문공사**인지 판단해야 합니다.",
        "",
        "- 종합공사와 전문공사는 적용되는 수의계약 한도와 참가자격 검토가 달라질 수 있습니다.",
        "- 단순히 `보수`라는 명칭만으로 정하지 말고 설계서, 내역서, 공종, 주된 공사 내용, 필요한 면허를 함께 확인합니다.",
        "- 복수 공종이 섞이면 주된 공사와 부대공사 관계, 분리발주 필요성, 무면허 시공 리스크를 검토합니다.",
        "- 금액 한도는 최신 법령 DB와 source map resolved_value로 별도 확인해야 하며, 이 답변에서는 금액을 단정하지 않습니다.",
    ])


def _is_local_company_point(q: str) -> bool:
    if (
        any(term in q for term in ("공동도급", "지역제한"))
        and any(term in q for term in ("연결", "높이", "어떻게"))
    ):
        return False
    return (
        ("지역업체" in q or "지역기업" in q)
        and any(term in q for term in ("가점", "점수", "참여도", "신인도", "적격심사", "평가"))
    )


def _is_negotiated_contract_regional_point_question(q: str) -> bool:
    return (
        any(term in q for term in ("협상에 의한 계약", "협상계약", "제안서", "정량평가", "정량"))
        and any(term in q for term in ("지역업체", "부산업체", "지역 업체"))
        and any(term in q for term in ("3점", "배점", "점수", "참여도"))
    )


def _negotiated_contract_regional_point_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **협상에 의한 계약에서 지역업체 참여도 점수를 크게 잡아 부산업체만 유리하게 만드는 방식은 위험합니다.**",
        "정량평가에 지역 요소를 두더라도 「지방자치단체 입찰시 낙찰자 결정기준」 제7장 협상에 의한 계약 낙찰자 결정기준과 실제 제안요청서 평가표 범위 안에서만 설계해야 합니다.",
        "",
        "| 검토 항목 | 판단 |",
        "|---|---|",
        "| 3점 배점 | 적용 평가표가 허용하는 경우라면 검토 가능하지만, 그 자체가 자동 허용은 아닙니다. |",
        "| 3점 초과 배점 | 지역업체 우대가 과도해질 수 있어 부당한 평가기준으로 지적될 위험이 큽니다. |",
        "| 부산업체만 유리한 항목 | 계약이행과 무관하거나 발주기관 소재 지역업체만 유리한 평가항목은 금지 사례로 봐야 합니다. |",
        "| 안전한 대체 항목 | 지역명 자체보다 현장 대응계획, 긴급 유지보수, 민원 대응, 지역 현황 이해도처럼 과업 수행과 직접 관련된 요소로 설계합니다. |",
        "",
        "### 실무 설계 방식",
        "- 평가표에 `부산 소재 여부`를 독립 점수로 크게 두기보다, 과업 수행에 필요한 **현장 대응성ㆍ지역 이해도ㆍ전담 인력 운영계획**으로 바꿔 정성 또는 정량 평가합니다.",
        "- 지역업체 참여도를 정량평가에 넣을 때는 공고문에 적용 예규, 배점, 산식, 증빙서류를 명확히 적고 특정 업체에 유리한 기준이 아닌지 사전 검토합니다.",
        "- 단순 노무용역처럼 전문성ㆍ창의성이 낮은 용역은 협상계약 자체가 부적정할 수 있으므로 계약방식부터 다시 확인합니다.",
        "",
        "근거: 「지방자치단체 입찰시 낙찰자 결정기준」 제7장 협상에 의한 계약 낙찰자 결정기준, 「지방자치단체 입찰 및 계약집행기준」의 부당한 평가항목 금지 사례",
    ])


def _is_sme_small_business_regional_combined_bid_question(q: str) -> bool:
    return (
        any(term in q for term in ("소기업", "소상공인"))
        and any(term in q for term in ("부산", "지역"))
        and any(term in q for term in ("중복", "같이", "동시", "제한"))
        and any(term in q for term in ("물품", "용역", "구매", "입찰"))
    )


def _sme_small_business_regional_combined_bid_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_text = _format_won(amount) if amount else "해당 금액"
    return "\n".join([
        f"결론부터 말하면, **{amount_text} 물품 구매에서 `소기업ㆍ소상공인 제한`과 `부산 지역제한`을 함께 쓰려면 금액 구간을 먼저 나눠야 합니다.**",
        "지역제한 자체는 다른 제한요건과 병행 검토할 수 있지만, 소기업ㆍ소상공인 제한은 1억원 미만 구간과 1억원 이상 구간의 법리가 다릅니다.",
        "",
        "| 추정가격 구간 | 소기업ㆍ소상공인 제한 | 부산 지역제한 병행 | 실무 판단 |",
        "|---|---|---|---|",
        "| 1억원 미만 물품ㆍ용역 | 소기업 또는 소상공인 우선조달 제한을 먼저 검토 | 가능 여부를 함께 검토 | `부산 소재 소기업ㆍ소상공인`으로 소액수의/제한공고 설계 가능성이 큽니다. |",
        "| 1억원 이상 물품ㆍ용역 | 소기업ㆍ소상공인만으로 좁히는 방식은 신중 | 지역제한 가능 금액이면 별도 검토 | 중소기업자 제한, 중소기업자간 경쟁제품, 직접생산확인 등으로 넓혀 봐야 합니다. |",
        "| 중소기업자간 경쟁제품 | 품목별 직접생산확인 필요 | 부산 지역제한과 함께 과도 제한 여부 검토 | 세부품명, 직접생산확인증명서, 경쟁 가능한 업체 수가 핵심입니다. |",
        "",
        "### 3억원 이하라는 질문에 대한 적용",
        "- `3억원 이하`라고 해서 전 구간을 소기업ㆍ소상공인으로만 제한할 수 있는 것은 아닙니다.",
        "- 추정가격이 **1억원 미만**이면 소기업ㆍ소상공인 제한과 부산 지역제한의 결합을 우선 검토합니다.",
        "- 추정가격이 **1억원 이상**이면 지방계약법 시행령 제20조의 중소기업자 제한 구조와 판로지원법상 중소기업자간 경쟁제품 여부를 함께 보아야 하며, 단순히 `소기업ㆍ소상공인 + 부산`으로만 좁히면 부당제한 위험이 있습니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령」 제2조의2",
    ])


def _is_regional_representative_joint_score_question(q: str) -> bool:
    return (
        any(term in q for term in ("공동수급체", "공동도급", "컨소시엄"))
        and any(term in q for term in ("대표사", "대표자"))
        and any(term in q for term in ("지역업체", "부산업체", "부산 업체"))
        and any(term in q for term in ("가점", "점수", "혜택", "적격심사", "참여도"))
    )


def _regional_representative_joint_score_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 업체가 공동수급체 대표사라는 이유만으로 적격심사 가점이 자동 부여된다고 보면 안 됩니다.**",
        "지역업체 가점ㆍ참여도는 `대표사가 누구인지`보다 해당 낙찰자 결정기준의 별표가 **지역업체 참여비율을 어떻게 산정하는지**가 핵심입니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 지역의무공동도급 공사 | 지역업체 참여는 가점이 아니라 입찰참가 요건에 가깝습니다. 이 경우 지역업체 가산평가 적용대상에서 제외되는 기준이 있을 수 있습니다. |",
        "| 일반 공동수급 적격심사 | 공고문 별표가 정한 지역업체 참여비율, 구성원 지분율, 대표사 제외 여부를 확인해야 합니다. |",
        "| 부산 업체가 대표사인 경우 | 대표사 지위만으로 점수를 확정하지 말고, 지역업체 참여비율 산식에 대표사가 포함되는지 공고 기준을 봅니다. |",
        "| 부산 업체가 구성원인 경우 | 공동수급체 내 실제 지분율과 분담내용이 지역업체 참여도 산정의 핵심 자료입니다. |",
        "",
        "### 공고문에서 확인할 문구",
        "- `지역의무공동도급 대상 공사인지`",
        "- `지역업체 가산평가 적용 제외 여부`",
        "- `지역업체 참여비율 산정 시 대표사를 포함하는지 또는 제외하는지`",
        "- `공동수급협정서의 지분율과 분담내용`",
        "",
        "정리하면, 부산 업체가 대표사이면 지역업체 보호 효과는 있을 수 있지만 **가점 계산은 공고문과 낙찰자 결정기준 별표의 산식으로만 확정**해야 합니다. `대표사=가점`으로 단정하면 감사나 이의신청 리스크가 생깁니다.",
        "근거: 「지방자치단체 입찰시 낙찰자 결정기준」 지역업체 참여도 관련 별표, 「지방계약법 시행령」 제88조 공동계약 기준",
    ])


def _is_international_bid_local_preference_question(q: str) -> bool:
    return (
        any(term in q for term in ("국제입찰", "국제 입찰", "고시금액"))
        and any(term in q for term in ("대형", "초과", "대상"))
        and any(term in q for term in ("부산", "지역업체", "우대", "예외"))
        and "공사" in q
    )


def _international_bid_local_preference_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **국제입찰 대상 금액을 넘는 대형 공사에서는 부산 업체만 참가하도록 지역제한을 거는 방식은 어렵습니다.**",
        "다만 지역업체 참여를 전혀 못 하는 것은 아니고, 법령과 국제입찰 원칙을 해치지 않는 범위에서 참여도 평가, 공동수급 허용, 하도급ㆍ지역자재 권장 방식으로 설계해야 합니다.",
        "",
        "| 수단 | 적용 판단 | 실무 포인트 |",
        "|---|---|---|",
        "| 부산 지역제한 | 원칙적으로 부적정 | 국제입찰 대상에서 부산 업체만 입찰하게 하면 경쟁 제한·차별 이슈가 큽니다. |",
        "| 지역의무공동도급 | 외국건설업자 포함 등 국제입찰 구조에서는 적용 제외·제한 여부 확인 필요 | 공고 전 지방계약법 제29조, 시행령 제88조, 국제입찰 적용 여부를 함께 검토합니다. |",
        "| 지역업체 참여도 | 낙찰자 결정기준이 허용하는 범위에서 검토 | 공동수급체 내 지역업체 참여비율을 평가하는 방식은 가능성을 검토할 수 있습니다. |",
        "| 하도급·지역자재 권장 | 강제보다 권장·이행계획 평가가 안전 | 지역업체 하도급, 장비·자재 활용계획을 과업 수행계획이나 상생협력계획으로 평가합니다. |",
        "",
        "### 권장 방향",
        "- 입찰참가자격을 `부산 소재`로 제한하지 말고, 일반경쟁 또는 국제입찰 절차를 유지합니다.",
        "- 제안서나 종합평가에서 `지역업체 참여계획`, `지역 하도급 관리계획`, `지역 장비·자재 활용계획`을 과업 관련 평가요소로 설계할 수 있는지 확인합니다.",
        "- 하도급을 특정 부산 업체에 의무화하거나 자재납품업체를 특정하면 부당제한이 될 수 있으므로, 권장 비율·이행계획·사후관리 중심으로 씁니다.",
        "",
        "근거: 「지방계약법」 제29조, 「지방계약법 시행령」 제20조·제88조, 「지방자치단체 입찰시 낙찰자 결정기준」 지역업체 참여도 관련 기준",
    ])


def _is_branch_only_regional_restriction_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역 제한", "지역제한"))
        and any(term in q for term in ("지사", "지점", "출장소", "연락사무소"))
        and any(term in q for term in ("참여", "가능", "해석", "입찰"))
    )


def _branch_only_regional_restriction_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산에 지사나 지점만 있는 업체는 부산 지역제한 입찰의 지역요건을 충족한다고 보기 어렵습니다.**",
        "지방계약의 지역제한은 원칙적으로 법인등기부상 **본점 소재지**를 기준으로 판단합니다. 개인사업자는 사업자등록증 또는 관련 인허가 서류에 기재된 사업장 소재지를 봅니다.",
        "",
        "| 구분 | 참여 가능성 | 판단 기준 |",
        "|---|---|---|",
        "| 법인 본점이 부산 | 가능 검토 | 입찰공고일 전일부터 입찰일까지, 낙찰자는 계약체결일까지 유지 |",
        "| 법인 본점은 타 지역, 부산 지사만 있음 | 원칙적으로 불가 | 지사·지점·출장소는 본점 소재지 요건을 대체하지 못함 |",
        "| 개인사업자 | 사업장 소재지 기준 | 사업자등록증 또는 인허가·면허·등록 서류의 소재지 확인 |",
        "",
        "### 공고문 확인 문구",
        "- `법인등기부상 본점 소재지가 부산광역시에 있는 업체`",
        "- `개인사업자는 사업자등록증 또는 관련 법령에 따른 허가·인가·면허·등록·신고 서류상 사업장 소재지를 기준으로 함`",
        "- `낙찰자는 계약체결일까지 해당 자격을 유지해야 함`",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「지방자치단체 입찰 및 계약집행기준」 제한입찰 운영 기준",
    ])


def _is_large_goods_no_regional_support_question(q: str) -> bool:
    amount = _extract_amount_won(q)
    return (
        "물품" in q
        and any(term in q for term in ("지역 제한", "지역제한"))
        and any(term in q for term in ("걸 수 없", "불가", "안되", "지원", "다른 방법", "대안"))
        and (amount is None or amount >= 100_000_000)
    )


def _large_goods_no_regional_support_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_text = _format_won(amount) if amount else "지역제한 기준을 넘는 물품 구매"
    return "\n".join([
        f"결론부터 말하면, **{amount_text} 물품 구매에서 부산 지역제한을 걸 수 없다면 참가자격을 억지로 묶기보다 구매 경로와 평가요소를 바꿔야 합니다.**",
        "부산업체 지원은 `부산 소재` 자체를 강제하는 방식이 아니라, 법령상 허용되는 조달경로와 과업 수행 관련 평가요소 안에서 설계해야 합니다.",
        "",
        "| 대안 경로 | 적용 방법 | 주의점 |",
        "|---|---|---|",
        "| 종합쇼핑몰/MAS | 품목이 등록되어 있으면 MAS 납품요구 또는 2단계 경쟁을 먼저 검토 | 부산업체라는 이유만으로 가점 주기보다 납기, A/S, 현장지원, 유지보수 대응을 평가요소로 둡니다. |",
        "| 우수조달ㆍ혁신제품ㆍ기술개발제품 | 부산 업체 제품이 해당 인증·지정 제품이면 수의계약 또는 조달구매 특례 검토 | 인증명, 지정기간, 세부품명, 실제 구매품목 일치 여부가 필수입니다. |",
        "| 중소기업자간 경쟁제품 | 해당 품목이면 직접생산확인과 중소기업자 제한을 적용 | 부산업체 후보는 시장조사로 제시하되, 참가자격을 부당하게 좁히지 않습니다. |",
        "| 공동계약ㆍ분담이행 | 단순 물품구매가 아니라 제조·설치·유지관리 등 복합 계약이면 허용 여부 검토 | 공사에서 쓰는 지역의무공동도급을 물품 구매에 기계적으로 적용하면 안 됩니다. |",
        "| 사후관리 조건 | 납품 후 긴급 대응, 교육, 장애처리, 서비스센터 운영계획 평가 | 특정 부산업체 지정이 아니라 계약목적 수행에 필요한 조건이어야 합니다. |",
        "",
        "### 권장 순서",
        "1. 세부품명 기준으로 종합쇼핑몰/MAS 등록 여부를 확인합니다.",
        "2. MAS 2단계 경쟁 대상이면 제안요청서 평가항목에 납기ㆍA/Sㆍ현장지원처럼 품목 수행과 직접 관련된 요소를 넣습니다.",
        "3. 부산 소재 우수조달물품, 혁신제품, 성능인증 등 기술개발제품 후보가 있으면 특례 수의계약 또는 조달구매 가능성을 별도로 봅니다.",
        "4. 자체 입찰로 가야 한다면 중소기업자간 경쟁제품, 직접생산확인, 중소기업자 제한을 우선 확인하고, 부산 업체 후보는 시장조사 자료로 정리합니다.",
        "",
        "정리하면, **7억원 물품은 지역제한으로 부산업체만 묶기보다 MAS/인증제품/중기경쟁제품/사후관리 평가를 조합하는 방식**이 안전합니다.",
        "근거: 「지방계약법 시행령」 제20조, 「물품 다수공급자계약 업무처리규정」, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」, 우수조달물품ㆍ혁신제품 관련 규정",
    ])


def _is_ordinance_upper_law_conflict_question(q: str) -> bool:
    return (
        any(term in q for term in ("조례", "지역 상품", "지역상품"))
        and any(term in q for term in ("상위법", "지방계약법", "충돌", "대처"))
    )


def _ordinance_upper_law_conflict_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산시 조례의 지역상품 우선구매 원칙이 지방계약법령의 경쟁·제한 기준과 충돌하면 상위법인 지방계약법령을 우선 적용해야 합니다.**",
        "조례는 지역상품 구매를 촉진하는 정책 근거로 활용할 수 있지만, 법령이 허용하지 않는 지역제한ㆍ수의계약ㆍ특정업체 지정의 근거가 될 수는 없습니다.",
        "",
        "| 판단 단계 | 실무 처리 |",
        "|---|---|",
        "| 1. 상위법 우선 | 「지방계약법」 제4조에 따라 지방계약은 다른 법률에 특별한 규정이 있는 경우 외에는 지방계약법을 따릅니다. 조례가 법령상 경쟁 원칙을 넘을 수는 없습니다. |",
        "| 2. 부당 제한 점검 | 「지방계약법」 제6조의 계약 원칙과 부당한 특약 금지에 맞는지 봅니다. |",
        "| 3. 합법 경로로 전환 | 금액 기준에 맞는 지역제한입찰, 소액수의 2인 이상 견적, 정책기업 수의계약, MAS, 우수조달ㆍ혁신제품 경로로 바꿉니다. |",
        "| 4. 내부 근거 정리 | 조례는 `부산업체를 고려한 시장조사와 후보 발굴의 정책 근거`로 쓰고, 계약방법의 법적 근거는 지방계약법령 조항으로 씁니다. |",
        "",
        "### 대처 문구 예시",
        "- `부산광역시 지역상품 구매 촉진 취지를 고려하되, 계약방법과 참가자격은 지방계약법령 및 행정안전부 예규가 허용하는 범위에서 정한다.`",
        "- `지역제한 가능 금액을 초과하는 경우에는 부산 업체만으로 제한하지 않고, 납기ㆍA/Sㆍ현장 대응성 등 계약이행 관련 평가요소와 조달등록ㆍ인증제품 경로를 검토한다.`",
        "",
        "정리하면, **조례는 방향을 주고, 지방계약법은 한계를 정합니다.** 충돌 시에는 지방계약법 기준 안에서 지역제한, 수의계약 특례, MAS, 인증제품, 평가항목을 재설계하는 방식이 안전합니다.",
        "근거: 「지방계약법」 제4조ㆍ제6조, 「지방계약법 시행령」 제20조ㆍ제25조ㆍ제30조, 부산광역시 지역상품 우선구매 관련 조례·지침",
    ])


def _is_joint_contract_agreement_breach_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역의무", "의무공동", "공동도급", "공동수급"))
        and any(term in q for term in ("협약", "협정", "공동수급협정서", "컨소시엄"))
        and any(term in q for term in ("파기", "탈퇴", "이탈", "위반", "깨"))
    )


def _joint_contract_agreement_breach_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **지역의무 공동도급 공사에서 낙찰 후 타 지역 업체가 부산 업체와의 공동수급 협약을 파기하면 단순한 내부 분쟁이 아니라 입찰ㆍ계약 이행 문제로 봐야 합니다.**",
        "공동수급체 구성은 입찰참가 조건이므로, 지역업체 비율을 깨는 탈퇴나 협약 파기는 발주기관 승인, 결원 보충, 제재 가능성을 함께 검토해야 합니다.",
        "",
        "| 쟁점 | 실무 처리 |",
        "|---|---|",
        "| 협약 파기 또는 탈퇴 | 공동수급체 구성 변경 사유와 귀책 주체를 확인합니다. 정당한 사유 없는 이탈이면 부정당업자 제재 검토 대상이 될 수 있습니다. |",
        "| 부산 업체 비율 미달 | 잔존 구성원만으로 공고된 지역업체 최소 참여비율을 충족하는지 다시 계산합니다. |",
        "| 결원 보충 | 지역업체 비율이나 면허 요건을 못 맞추면 발주기관 승인 아래 새 지역업체 추가 또는 지분 조정을 검토합니다. |",
        "| 계약 유지 여부 | 공동수급체가 입찰참가자격과 계약이행능력을 유지하지 못하면 계약 해지, 낙찰 취소, 제재까지 연결될 수 있습니다. |",
        "",
        "### 계약담당자 조치 순서",
        "1. 공동수급협정서, 입찰공고의 지역의무 비율, 구성원별 지분율을 확인합니다.",
        "2. 협약 파기 사유가 정당한지와 귀책 주체를 문서로 소명받습니다.",
        "3. 잔존 구성원으로 지역업체 최소 참여비율과 면허·시공능력 요건이 유지되는지 검토합니다.",
        "4. 필요하면 발주기관 승인 절차를 거쳐 지역업체 보충 또는 지분 변경을 요구합니다.",
        "5. 정당한 사유 없는 파기라면 입찰참가자격 제한, 계약상 책임, 손해배상 가능성을 법무·감사 부서와 협의합니다.",
        "",
        "근거: 「지방계약법 시행령」 제88조 공동계약, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령, 부정당업자 제재 관련 규정",
    ])


def _is_sme_competition_local_mandatory_purchase_question(q: str) -> bool:
    return (
        any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
        and any(term in q for term in ("부산", "지역업체", "관내"))
        and any(term in q for term in ("반드시", "꼭", "의무", "사야", "구매"))
    )


def _sme_competition_local_mandatory_purchase_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_text = _format_won(amount) if amount else "해당 금액"
    return "\n".join([
        f"결론부터 말하면, **중소기업자간 경쟁제품 {amount_text} 구매라고 해서 반드시 부산 업체로부터 사야 하는 것은 아닙니다.**",
        "중소기업자간 경쟁제품은 `중소기업자 제한`과 `직접생산확인`이 핵심이고, 부산 지역제한은 법령상 요건이 맞을 때 선택할 수 있는 수단입니다.",
        "",
        "| 경로 | 가능 여부 | 확인 포인트 |",
        "|---|---|---|",
        "| 부산 지역제한 + 중기경쟁제품 | 가능 검토 | 금액 기준, 부산 내 적격 업체 수, 직접생산확인증명서 보유 여부를 확인합니다. |",
        "| 전국 중소기업자간 경쟁입찰 | 가능 | 부산 업체가 부족하거나 지역제한이 과도하면 전국 중소기업자 경쟁으로 진행할 수 있습니다. |",
        "| 종합쇼핑몰/MAS | 가능 검토 | 해당 세부품명이 쇼핑몰에 있으면 MAS 납품요구 또는 2단계 경쟁 기준을 함께 봅니다. |",
        "| 특정 부산업체 지정 | 원칙적으로 부적정 | 수의계약 특례나 인증제품 등 별도 사유가 없으면 특정 업체 지정은 위험합니다. |",
        "",
        "### 8,000만원 구간 실무 판단",
        "- 물품 8,000만원은 지역제한 소액수의 또는 제한경쟁을 검토할 수 있는 구간일 수 있지만, `반드시 부산`은 아닙니다.",
        "- 부산 업체가 2인 이상이고 세부품명·직접생산확인 요건을 충족하면 부산 지역제한 공고를 검토합니다.",
        "- 부산 내 적격 업체가 부족하거나 경쟁성이 낮으면 전국 중소기업자간 경쟁 또는 MAS 경로로 전환하는 것이 안전합니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」, 중소기업자간 경쟁제품 직접생산 확인기준, 「물품 다수공급자계약 업무처리규정」",
    ])


def _is_direct_production_busan_vendor_search_question(q: str) -> bool:
    return (
        any(term in q for term in ("직접생산확인", "직접생산 확인", "직생"))
        and any(term in q for term in ("부산", "지역업체", "업체"))
        and any(term in q for term in ("검색", "찾", "조회", "방법"))
    )


def _direct_production_busan_vendor_search_answer() -> str:
    return "\n".join([
        "직접생산확인증명서를 보유한 부산 업체는 **중소기업제품 공공구매종합정보망(SMPP)**에서 확인하는 것이 가장 정확합니다.",
        "",
        "| 단계 | 할 일 |",
        "|---|---|",
        "| 1 | SMPP 접속: https://www.smpp.go.kr 또는 https://smpp.go.kr |",
        "| 2 | `직접생산확인` 또는 `정보조회` 메뉴에서 직접생산확인 업체/제품 조회 화면으로 이동 |",
        "| 3 | 구매하려는 품목의 **세부품명번호 10자리** 또는 세부품명을 입력 |",
        "| 4 | 지역 조건에서 **부산광역시** 또는 본사 소재지 부산을 선택 |",
        "| 5 | 업체명, 사업자등록번호, 세부품명, 유효기간, 직접생산확인 상태를 확인 |",
        "| 6 | 나라장터 공고·계약 전에는 확인서 유효기간과 세부품명 일치 여부를 다시 출력 또는 저장 |",
        "",
        "### 실무 체크포인트",
        "- 직접생산확인은 `업체가 직접 생산할 수 있는 세부품명` 기준이므로, 업체명만 맞아도 세부품명이 다르면 참가자격이 맞지 않을 수 있습니다.",
        "- 지역제한을 같이 걸려면 부산 내 적격 업체가 충분한지, 본점 소재지 기준을 충족하는지 별도로 확인합니다.",
        "- 중소기업자간 경쟁제품이면 공고문에 `직접생산확인증명서 소지 업체`와 해당 세부품명번호를 정확히 적습니다.",
        "",
        "근거: 중소기업제품 공공구매종합정보망(SMPP), 중소기업자간 경쟁제품 직접생산 확인기준",
    ])


def _is_public_material_direct_purchase_busan_list_question(q: str) -> bool:
    return (
        any(term in q for term in ("관급자재", "공사 자재", "공사용 자재", "직접 구매", "직접구매"))
        and any(term in q for term in ("부산", "지역"))
        and any(term in q for term in ("생산", "제품", "리스트", "목록", "찾"))
    )


def _public_material_direct_purchase_busan_list_answer() -> str:
    return "\n".join([
        "고정된 `부산 생산 관급자재 리스트`가 따로 있다고 보기보다, **품목별로 SMPP와 나라장터 종합쇼핑몰에서 부산 업체ㆍ제품을 조회해 후보표를 만드는 방식**이 안전합니다.",
        "",
        "| 조회 경로 | 확인할 내용 |",
        "|---|---|",
        "| SMPP 공공구매종합정보망 | 중소기업자간 경쟁제품 여부, 직접생산확인 업체, 세부품명번호, 지역(부산) 필터 |",
        "| 나라장터 종합쇼핑몰 | MAS/제3자단가 등록 여부, 공급업체 소재지, 납품 가능 지역, 계약상태, 규격 |",
        "| 공사용자재 직접구매 대상 품목 고시 | 해당 자재가 직접구매 대상인지, 금액·품목 기준을 충족하는지 |",
        "",
        "### 검색 순서",
        "1. 설계내역서에서 자재명과 세부품명번호를 뽑습니다.",
        "2. SMPP(https://www.smpp.go.kr)에서 세부품명번호 10자리로 검색하고 지역을 부산광역시로 필터링합니다.",
        "3. 직접생산확인증명서 유효기간과 생산 가능 세부품명이 실제 자재와 일치하는지 확인합니다.",
        "4. 나라장터 종합쇼핑몰(https://shop.g2b.go.kr)에서 같은 품목을 검색해 부산 소재 공급업체, 납품조건, MAS 등록 여부를 확인합니다.",
        "5. 후보는 `가능 업체`가 아니라 `검토 후보`로 표시하고, 최종 계약 전 직접생산ㆍ계약상태ㆍ규격 일치를 다시 확인합니다.",
        "",
        "### 주의",
        "- 부산 생산 제품을 찾는 것은 시장조사와 지역상품 구매촉진 목적에는 적절하지만, 특정 부산 업체 제품을 설계에 박아 넣으면 부당한 특정규격이 될 수 있습니다.",
        "- 공사용자재 직접구매 대상이면 공사 내역에서 관급자재로 분리할지, 직접구매 금액 기준을 충족하는지부터 확인해야 합니다.",
        "",
        "근거: SMPP 공공구매종합정보망, 나라장터 종합쇼핑몰, 중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 기준",
    ])


def _is_sme_product_priority_vs_busan_local_question(q: str) -> bool:
    return (
        any(term in q for term in ("중소기업", "중소기업 제품", "중소기업제품"))
        and any(term in q for term in ("대기업", "대기업 제품"))
        and any(term in q for term in ("부산", "지역"))
        and any(term in q for term in ("우선 구매", "우선구매", "의무", "물품"))
    )


def _sme_product_priority_vs_busan_local_answer(q: str) -> str:
    amount = _extract_amount_won(q)
    amount_text = _format_won(amount) if amount else "해당 금액"
    local_goods_service = get_numeric_display("P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD")
    local_limit = local_goods_service or "행정안전부장관 고시금액 미만"
    return "\n".join([
        f"결론부터 말하면, **{amount_text} 물품 구매에서 `대기업 제품 대신 부산 중소기업 제품을 반드시 사야 한다`고 단정하면 안 됩니다.**",
        "다만 공공기관에는 중소기업제품 구매 확대 의무가 있고, 품목이 중소기업자간 경쟁제품이면 대기업 제품을 배제하는 중소기업자 제한 구조가 먼저 작동할 수 있습니다.",
        "",
        "| 구분 | 판단 |",
        "|---|---|",
        "| 중소기업제품 우선구매 | 판로지원법 체계에 따라 공공기관의 중소기업제품 구매 목표·의무를 확인합니다. |",
        "| 중소기업자간 경쟁제품 | 해당 세부품명이 경쟁제품이면 중소기업자 대상 제한경쟁과 직접생산확인증명서가 핵심입니다. |",
        "| 부산 중소기업 우대 | 지방계약법상 지역제한 가능 금액이면 부산 소재 중소기업으로 참가자격 제한을 검토할 수 있습니다. |",
        "| 대기업 제품 배제 | `부산` 때문이 아니라 중소기업자간 경쟁제품, 중소기업제품 구매제도, 세부품명 요건 때문에 제한되는지 확인해야 합니다. |",
        "",
        "### 2억원 물품 구매에서의 순서",
        "1. 세부품명번호로 중소기업자간 경쟁제품인지 확인합니다.",
        "2. 경쟁제품이면 직접생산확인증명서를 보유한 중소기업자 대상 공고 또는 조달구매 경로를 봅니다.",
        f"3. 부산 지역제한은 물품ㆍ일반용역 지역제한 기준인 **{local_limit}** 안에 들어오는지와 부산 내 적격 업체 수가 충분한지 확인합니다.",
        "4. 종합쇼핑몰/MAS 등록 품목이면 MAS 납품요구 또는 2단계 경쟁 경로도 함께 검토합니다.",
        "",
        "정리하면, **중소기업제품 우선구매는 의무 성격이 있지만, `부산 중소기업 제품을 반드시 구매`하는 의무와는 다릅니다.** 부산업체 지원은 중기경쟁제품ㆍ직접생산확인ㆍ지역제한 가능 여부ㆍMAS 경로를 조합해서 설계해야 합니다.",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률」, 「지방계약법 시행령」 제20조, 중소기업자간 경쟁제품 직접생산 확인기준",
    ])


def _is_performance_certified_product_documents_question(q: str) -> bool:
    return (
        any(term in q for term in ("성능인증", "epc", "EPC", "기술개발제품", "인증제품"))
        and any(term in q for term in ("수의계약", "계약"))
        and any(term in q for term in ("서류", "증빙", "필요", "구비"))
    )


def _performance_certified_product_documents_answer() -> str:
    return "\n".join([
        "중소기업 성능인증(EPC) 제품을 보유한 부산 업체와 수의계약을 검토할 때는 **성능인증 특례 증빙서류와 일반 수의계약 서류를 분리해서 받는 것**이 좋습니다.",
        "",
        "| 구분 | 필요 서류 | 확인 포인트 |",
        "|---|---|---|",
        "| 인증 특례 증빙 | 성능인증서, 인증 유효기간 확인자료 | 구매하려는 제품명·규격이 인증서와 일치해야 합니다. |",
        "| 제품 적격성 | 카탈로그, 규격서, 시험성적서, 납품실적 또는 성능 비교자료 | 성능인증 제품이 실제 과업에 필요한 이유를 남깁니다. |",
        "| 직접생산 | 직접생산확인증명서(중소기업자간 경쟁제품 등 해당 시) | 세부품명번호와 유효기간을 확인합니다. |",
        "| 계약 사유 | 수의계약 사유서, 시장조사서, 대체품 검토자료 | `부산업체라서`가 아니라 성능인증·기술개발제품 근거로 씁니다. |",
        "| 가격 적정성 | 견적서, 원가자료, 조달가격 또는 타 기관 계약사례 | 고액이면 가격 소명자료를 더 촘촘히 남깁니다. |",
        "| 공통 서류 | 사업자등록증, 법인등기부등본, 인감, 납세증명서, 4대보험 완납증명, 청렴서약서 등 | 기관 내부 계약서류 목록과 맞춥니다. |",
        "",
        "### 먼저 확인할 것",
        "- 해당 제품이 **나라장터 종합쇼핑몰/MAS 또는 제3자단가계약**에 등록되어 있으면 조달구매 경로가 더 안전하고 빠를 수 있습니다.",
        "- 쇼핑몰에 없거나 특수 조건이 필요한 경우에 자체 수의계약 사유서와 가격 적정성 자료를 갖춰 진행합니다.",
        "- 부산 소재 여부는 지역상품 구매 실적과 후보 선정에는 도움이 되지만, 수의계약의 법적 근거는 성능인증ㆍ기술개발제품 요건으로 세워야 합니다.",
        "",
        "근거: 「지방계약법 시행령」 제25조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」, 성능인증 및 기술개발제품 구매 관련 기준",
    ])


def _is_department_performance_score_question(q: str) -> bool:
    return (
        any(term in q for term in ("부서별", "부서", "성과평가", "BSC", "가점", "실적"))
        and any(term in q for term in ("기술개발제품", "인증제품", "우선구매"))
        and any(term in q for term in ("있나요", "제도", "높이", "반영"))
    )


def _department_performance_score_answer() -> str:
    return "\n".join([
        "이 질문은 계약방법보다 **기관 내부 성과평가(BSC)ㆍ부서평가 지표**에 관한 사안입니다.",
        "따라서 법령상 전국 공통으로 `부서별 가점 몇 점`이 정해져 있다고 보기는 어렵고, 부산시 또는 해당 기관의 당해 연도 성과평가 계획을 확인해야 합니다.",
        "",
        "| 확인 항목 | 확인 부서 | 실무 포인트 |",
        "|---|---|---|",
        "| BSC/부서평가 지표 | 기획·평가·혁신 담당 부서 | 기술개발제품, 혁신제품, 여성·장애인기업제품, 지역상품 구매실적이 지표에 들어 있는지 확인 |",
        "| 구매실적 산정 기준 | 계약·회계 부서 | 조달구매, 자체계약, 관급자재, 수의계약 실적이 어떻게 집계되는지 확인 |",
        "| 증빙자료 | 계약부서·사업부서 | 계약서, 납품요구서, 조달구매내역, 인증서, 업체 소재지 자료를 남김 |",
        "| 연도별 변경 | 평가담당 부서 | 가점 항목과 배점은 매년 달라질 수 있으므로 최신 평가계획을 기준으로 함 |",
        "",
        "### 실무 대응",
        "- 계약서류에는 법령상 구매 근거를, 성과관리 자료에는 `부산 소재 기술개발제품 구매실적`과 인증서·조달구매내역을 붙여 관리합니다.",
        "- 부서별 가점을 신설하려면 회계부서가 아니라 평가담당 부서와 협의해 `지역 기술개발제품 구매율`, `혁신제품 구매실적`, `중소기업제품 구매율` 같은 지표로 설계해야 합니다.",
        "",
        "정리하면, **부서별 가점은 계약법이 아니라 기관 내부 평가계획 문제**입니다. 당해 연도 BSC/성과평가 지침과 구매실적 집계 기준을 먼저 확인하세요.",
    ])


def _is_sme_competition_no_local_direct_producer_question(q: str) -> bool:
    return (
        any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
        and any(term in q for term in ("부산", "지역", "관내"))
        and any(term in q for term in ("직접생산", "직생"))
        and any(term in q for term in ("없", "없는", "부재", "없으면"))
        and any(term in q for term in ("발주", "어떻게", "진행"))
    )


def _sme_competition_no_local_direct_producer_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **중소기업자간 경쟁제품인데 부산에 직접생산확인 업체가 없으면 부산 지역제한을 고집하면 안 됩니다.**",
        "경쟁이 성립하도록 인접 지역 또는 전국 단위로 확대하고, 직접생산확인증명서를 보유한 적격 업체가 2인 이상 확보되는지 확인해야 합니다.",
        "",
        "| 단계 | 처리 방법 |",
        "|---|---|",
        "| 1. 품목 확인 | 세부품명번호 기준으로 중소기업자간 경쟁제품 및 직접생산확인 대상인지 확인 |",
        "| 2. 부산 업체 확인 | SMPP에서 부산 직접생산확인 업체 수와 유효기간 확인 |",
        "| 3. 업체 부재 | 부산 제한을 풀고 부울경 등 인접 지역 또는 전국으로 확대 검토 |",
        "| 4. 경쟁성 확보 | 직접생산확인증명서를 가진 업체가 2인 이상인지 확인 |",
        "| 5. 사유 기록 | `부산 내 적격 직접생산 업체 부재` 시장조사 결과를 내부 검토서에 남김 |",
        "",
        "### 실무 포인트",
        "- 부산 업체가 없는데도 지역제한을 걸면 유찰 반복 또는 부당제한 문제가 생길 수 있습니다.",
        "- 지역 확대 후에도 직접생산확인 업체가 부족하면 공고 조건, 세부품명, 규격이 과도하게 좁은지 다시 검토합니다.",
        "- 종합쇼핑몰/MAS에 해당 품목이 등록되어 있으면 조달구매 경로도 같이 봅니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」, 중소기업자간 경쟁제품 직접생산 확인기준",
    ])


def _is_expired_small_business_certificate_question(q: str) -> bool:
    return (
        any(term in q for term in ("소기업", "소상공인"))
        and any(term in q for term in ("확인서", "증명서"))
        and any(term in q for term in ("만료", "유효기간", "기간만료"))
        and any(term in q for term in ("계약", "실적", "인정"))
    )


def _expired_small_business_certificate_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **소기업ㆍ소상공인 확인서가 만료된 상태로 계약을 진행하면 소기업ㆍ소상공인 구매실적으로 인정받기 어렵습니다.**",
        "계약체결일 기준으로 유효한 확인서를 보유했는지 확인하고, 만료 상태라면 계약 전 갱신 발급을 안내해야 합니다.",
        "",
        "| 확인 항목 | 실무 판단 |",
        "|---|---|",
        "| 확인서 유효기간 | 계약체결일 기준 유효해야 함 |",
        "| 만료 확인서 | 구매실적 인정 및 참가자격 확인에 사용하기 어려움 |",
        "| 갱신 조치 | 업체에 SMPP 또는 중소기업현황정보시스템에서 갱신 발급 요청 |",
        "| 계약서류 | 갱신 확인서, 사업자등록증, 직접생산확인증명서(해당 시)를 함께 보관 |",
        "",
        "### 계약담당자 조치",
        "- 계약 전 확인서 발급일과 유효기간을 캡처 또는 출력해 보관합니다.",
        "- 만료 상태이면 낙찰자 결정 또는 계약 체결 전에 갱신본 제출을 요구합니다.",
        "- 갱신이 불가능하면 소기업ㆍ소상공인 제한 또는 해당 구매실적 반영을 전제로 진행하기 어렵습니다.",
        "",
        "근거: 중소기업 확인서 및 소기업ㆍ소상공인 확인 관련 공공구매 실적관리 기준, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 체계",
    ])


def _is_policy_performance_double_count_question(q: str) -> bool:
    return (
        any(term in q for term in ("여성기업", "장애인기업", "사회적기업", "정책기업"))
        and any(term in q for term in ("부산", "지역업체", "지역 업체"))
        and any(term in q for term in ("실적", "집계"))
        and any(term in q for term in ("중복", "동시에", "둘다", "두 실적"))
    )


def _policy_performance_double_count_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 소재 여성기업 제품을 구매한 1건은 여성기업제품 구매실적과 부산 지역업체 구매실적으로 각각 집계할 수 있습니다.**",
        "두 실적은 평가 목적과 관리 체계가 다릅니다. 여성기업 실적은 법정 의무구매·공공구매 실적이고, 부산 지역업체 실적은 지자체 정책·내부 평가 지표 성격입니다.",
        "",
        "| 실적 구분 | 집계 기준 | 확인 자료 |",
        "|---|---|---|",
        "| 여성기업제품 구매실적 | 「여성기업지원에 관한 법률」상 여성기업 여부 | 여성기업 확인서, 계약서, 납품내역 |",
        "| 부산 지역업체 구매실적 | 업체 본점 또는 주된 영업소가 부산인지 | 사업자등록증, 법인등기부등본, 조달업체 정보 |",
        "| 중복 집계 | 가능 | 같은 계약이라도 지표 목적이 다르면 각각 반영 가능 |",
        "",
        "### 주의",
        "- 같은 실적을 같은 지표 안에서 이중 계산하면 안 되지만, `여성기업 실적`과 `부산 지역업체 실적`처럼 서로 다른 지표에는 각각 반영할 수 있습니다.",
        "- 실적 제출 시 여성기업 확인서 유효기간과 부산 소재 기준일을 함께 남기세요.",
        "- 기관 내부 성과평가에서 중복 집계를 제한하는 별도 지침이 있으면 그 지침을 우선 확인합니다.",
        "",
        "근거: 「여성기업지원에 관한 법률」, 공공구매 실적관리 기준, 부산 지역상품 구매촉진 관련 내부 지침",
    ])


def _is_public_material_local_review_committee_question(q: str) -> bool:
    return (
        any(term in q for term in ("공사용 자재", "공사 자재", "관급자재", "직접 구매", "직접구매"))
        and any(term in q for term in ("부산", "지역업체", "지역 업체"))
        and any(term in q for term in ("우선 선정", "우선선정", "내부 심의", "심의", "선정"))
    )


def _public_material_local_review_committee_answer() -> str:
    return "\n".join([
        "공사용 자재 직접구매에서 부산 업체 제품을 우선 검토하려면 **특정 업체를 먼저 정하는 방식이 아니라, 자재 선정 기준과 시장조사 절차를 문서화하는 내부 심의**가 필요합니다.",
        "",
        "| 단계 | 내부 심의 내용 |",
        "|---|---|",
        "| 1. 대상 품목 확인 | 공사용자재 직접구매 대상 품목인지, 중소기업자간 경쟁제품인지, 직접생산확인 대상인지 확인 |",
        "| 2. 후보 조사 | SMPP, 나라장터 종합쇼핑몰, 조달등록 자료에서 부산 업체 제품과 전국 후보를 함께 비교 |",
        "| 3. 기준 설정 | 성능, 규격, 납기, A/S, 가격, 인증, 직접생산 여부를 기준으로 설정 |",
        "| 4. 지역 요소 반영 | 부산 소재 여부는 시장조사와 정책 목적 자료로 두고, 평가항목은 납기·현장대응·유지보수처럼 계약 이행 관련 요소로 설계 |",
        "| 5. 심의 기록 | 특정 규격 또는 특정 제품을 선택해야 하는 기술적 이유와 대체 가능성 검토 결과를 남김 |",
        "",
        "### 활용 가능한 계약 경로",
        "- 종합쇼핑몰/MAS 품목이면 MAS 납품요구 또는 2단계 경쟁을 먼저 검토합니다. 지역업체 자체 가점보다는 납기, 현장지원, 사후관리 평가요소로 반영하는 편이 안전합니다.",
        "- 지역제한 가능 금액이면 부산 지역제한 입찰을 검토하되, 적격 업체 수와 부당제한 여부를 확인합니다.",
        "- 우수조달ㆍ혁신제품ㆍ성능인증 등 인증제품이면 해당 특례 경로와 부산 업체 여부를 함께 봅니다.",
        "- 설계서에 특정 제품명을 박아 넣어야 한다면 자재선정위원회 또는 내부 심의에서 `왜 동등 이상 제품으로 대체하기 어려운지`를 남겨야 합니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조ㆍ제25조, 「지방자치단체 입찰 및 계약집행기준」 부당한 특정규격 금지 취지, 공사용자재 직접구매 대상 품목 기준",
    ])


def _is_sme_competition_policy_company_direct_contract_question(q: str) -> bool:
    return (
        any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
        and any(term in q for term in ("여성기업", "장애인기업", "사회적기업", "정책기업", "1인수의", "1인 수의"))
        and any(term in q for term in ("처리", "방법", "가능", "수의계약"))
    )


def _sme_competition_policy_company_direct_contract_answer() -> str:
    one_quote_policy = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **중소기업자간 경쟁제품이라도 부산 업체가 여성기업 등 1인 견적 수의계약 대상이고 금액 요건을 충족하면 수의계약 예외를 검토할 수 있습니다.**",
        "다만 중소기업자간 경쟁제품이라는 점 때문에 세부품명, 직접생산확인, MAS 등록 여부를 먼저 확인해야 합니다.",
        "",
        "| 확인 순서 | 판단 내용 |",
        "|---|---|",
        "| 1. 세부품명 | 중소기업자간 경쟁제품인지, 직접생산확인 대상인지 확인 |",
        "| 2. 정책기업 지위 | 여성기업ㆍ장애인기업ㆍ사회적기업 등 확인서가 유효한지 확인 |",
        f"| 3. 금액 기준 | 1인 견적은 **추정가격 {one_quote_policy} 이하**인지 우선 확인 |",
        "| 4. 경쟁제품 예외 | 판로지원법 시행령상 중소기업자간 경쟁입찰 예외 사유에 해당하는지 확인 |",
        "| 5. 조달 경로 | 종합쇼핑몰/MAS 또는 제3자단가계약 등록 여부를 먼저 확인 |",
        "",
        "### 실무 처리",
        "- MAS에 등록되어 있으면 자체 수의계약보다 조달구매 경로가 더 안전할 수 있습니다.",
        "- 자체 수의계약을 하려면 여성기업 등 확인서, 직접생산확인증명서(해당 시), 수의계약 사유서, 세부품명 일치 자료, 가격 적정성 자료를 갖춥니다.",
        "- 금액이 1인 견적 한도를 넘거나 정책기업 요건이 불명확하면 부산 지역제한 2인 이상 견적 또는 중소기업자간 경쟁입찰로 전환합니다.",
        "",
        "근거: 「지방계약법 시행령」 제25조ㆍ제30조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령」 제7조, 중소기업자간 경쟁제품 직접생산 확인기준",
    ])


def _is_startup_product_priority_purchase_question(q: str) -> bool:
    return (
        any(term in q for term in ("창업기업", "창업 기업", "스타트업", "벤처나라"))
        and any(term in q for term in ("부산", "지역"))
        and any(term in q for term in ("우선 구매", "우선구매", "법적 근거", "금액 한도", "한도"))
    )


def _startup_product_priority_purchase_answer() -> str:
    general_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    young_startup_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **부산 창업기업 제품은 우선구매 실적 대상으로 관리할 수 있지만, `창업기업`이라는 이유만으로 고액 1인 수의계약이 자동 허용되는 것은 아닙니다.**",
        "일반 창업기업 우선구매, 청년창업기업 수의계약 특례, 벤처나라ㆍ기술개발제품 경로를 분리해서 봐야 합니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 창업기업제품 우선구매 | 「중소기업창업 지원법」 제5조의2에 따른 공공기관 우선구매 실적 관리 대상 |",
        "| 구매목표 | 창업기업제품 구매목표 비율은 관련 시행령ㆍ당해 연도 공공구매 지침에서 확인 |",
        f"| 일반 창업기업 1인 수의 | 특별한 다른 사유가 없으면 일반 1인 견적 기준인 **추정가격 {general_one_quote} 이하**부터 봅니다. |",
        f"| 청년창업기업 특례 | 청년창업기업 요건을 충족하면 **추정가격 {young_startup_one_quote} 이하** 1인 견적 특례를 별도 검토할 수 있습니다. |",
        "| 벤처나라ㆍ기술개발제품 | 벤처나라 등록, 성능인증, 우수조달, 혁신제품 등 별도 지정이 있으면 해당 경로를 우선 검토 |",
        "",
        "### 부산 업체 지원 방식",
        "- 부산 소재 창업기업 확인서, 사업자등록증, 제품 인증, 조달등록 상태를 확인합니다.",
        "- 수의계약 사유가 부족하면 부산 지역제한 2인 이상 견적 또는 제한경쟁, 벤처나라/종합쇼핑몰 구매, 기술개발제품 우선구매 경로로 전환합니다.",
        "- `창업기업`과 `청년창업기업`은 같은 말이 아니므로 확인서와 대표자 요건을 구분해야 합니다.",
        "",
        "근거: 「중소기업창업 지원법」 제5조의2, 「지방계약법 시행령」 제25조ㆍ제30조, 창업기업제품 공공기관 우선구매제도, 벤처나라 운영 기준",
    ])


def _is_coop_recommendation_direct_contract_question(q: str) -> bool:
    return (
        any(term in q for term in ("조합추천", "조합 추천", "협동조합추천", "협동조합 추천"))
        and any(term in q for term in ("수의계약", "구매", "절차", "방법"))
    )


def _coop_recommendation_direct_contract_answer() -> str:
    coop_limit = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **조합 추천 수의계약은 부산 지역 협동조합 제품을 바로 지정하는 제도가 아니라, 중소기업자간 경쟁제품을 조합 추천 업체 간 가격경쟁으로 구매하는 절차입니다.**",
        f"일반적으로 추정가격 **{coop_limit} 이하** 소액 경쟁제품에서 검토하며, 세부품명과 직접생산확인 요건을 먼저 맞춰야 합니다.",
        "",
        "| 단계 | 처리 내용 |",
        "|---|---|",
        "| 1. 품목 확인 | 구매 품목이 중소기업자간 경쟁제품인지, 직접생산확인 대상인지 확인 |",
        "| 2. 추천 요청 | 해당 중소기업협동조합에 구매조건, 납기, 지역 희망 조건을 포함해 추천 요청 |",
        "| 3. 업체 추천 | 조합이 자격요건을 검토해 복수 업체를 추천 |",
        "| 4. 가격경쟁 | 추천 업체 간 견적 또는 가격경쟁을 거쳐 계약상대자를 결정 |",
        "| 5. 계약·검수 | 직접생산확인증명서, 견적서, 납품·검수 자료를 계약서류로 보관 |",
        "",
        "### 부산 업체 활용 포인트",
        "- 추천 요청서에 `부산 소재 조합원사 우선 추천 가능 여부`를 문의할 수는 있지만, 경쟁 가능한 적격 업체 수와 부당제한 위험을 함께 확인해야 합니다.",
        "- 부산에 적격 직접생산 업체가 부족하면 부산으로만 묶기보다 조합 추천 범위를 확대하고, 납기·A/S·현장대응 조건으로 실무 필요를 반영합니다.",
        "- 협동조합이라는 명칭만으로 수의계약이 되는 것은 아니므로, 조합 추천 제도 대상인지와 사회적협동조합·사회적기업 특례를 구분해야 합니다.",
        "",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령」 제8조, 중소기업자간 경쟁제품 직접생산 확인기준, 공공구매종합정보망(SMPP) 조합추천 수의계약 절차",
    ])


def _is_cancelled_direct_production_contract_question(q: str) -> bool:
    return (
        "직접생산확인" in q
        and any(term in q for term in ("취소", "취소처분", "취소 처분", "말소"))
        and any(term in q for term in ("이미계약", "이미 계약", "계약한", "대금", "지급", "해지", "해제"))
    )


def _cancelled_direct_production_contract_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **직접생산확인이 취소된 업체와의 계약은 전부 또는 일부 해제·해지를 먼저 검토해야 합니다.**",
        "다만 이미 적법하게 납품·검수까지 끝난 부분의 대금은 계약조건과 검수 결과를 확인해 정산할 수 있는지 별도로 판단합니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 미이행·잔여 물량 | 직접생산확인 취소 사실을 확인한 뒤 계약 해제·해지 및 재발주를 검토 |",
        "| 기납품·검수 완료분 | 실제 납품, 검수 합격, 하자 여부, 허위서류 여부를 대조해 지급 또는 환수 여부 판단 |",
        "| 허위·부정 확인 | 직접생산 허위, 대리납품, 서류 위조가 있으면 부정당업자 제재·환수·손해배상 검토 |",
        "| 기록 보관 | 취소 통보일, 납품일, 검수일, 대금 청구일을 시간순으로 정리 |",
        "",
        "### 처리 순서",
        "1. SMPP 또는 발급기관 자료로 직접생산확인 취소일과 취소 사유를 확인합니다.",
        "2. 계약 물량을 `검수 완료분`, `납품했으나 미검수분`, `미납품분`으로 나눕니다.",
        "3. 미이행분은 해제·해지와 대체 조달을 검토하고, 기납품분은 계약담당·감사·법무 검토 후 지급 또는 보류를 결정합니다.",
        "4. 허위 직접생산 또는 부정 납품 정황이 있으면 대금 지급보다 환수·제재 검토가 우선입니다.",
        "",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 제11조, 「지방계약법」 부정당업자 제재 및 계약 해제·해지 관련 규정, 직접생산확인 기준",
    ])


def _is_early_payment_local_small_business_question(q: str) -> bool:
    return (
        any(term in q for term in ("대금", "대가", "물품구매대금", "물품 구매 대금"))
        and any(term in q for term in ("3일", "3일이내", "조기지급", "조기 지급"))
        and any(term in q for term in ("소상공인", "부산소재", "부산 소재", "지역업체"))
        and any(term in q for term in ("근거", "가능", "지급"))
    )


def _early_payment_local_small_business_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **검수와 대금청구 서류가 갖춰졌다면 부산 소재 소상공인에게 3일 이내 조기 지급하는 것은 가능합니다.**",
        "다만 `3일 이내`가 항상 의무인 것은 아니고, 원칙은 청구일부터 5일 이내 지급이며 재난·경제위기 등 행안부장관이 기간을 정해 고시한 경우에는 3일 기준이 적용됩니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 일반 원칙 | 계약상대자의 대금 청구일부터 5일 이내 지급 |",
        "| 한시 특례 | 재난·경기침체 등 행안부 고시 기간에는 3일 이내 지급 기준 적용 |",
        "| 자발적 조기 지급 | 5일은 최대 지급기한이므로 검수·청구가 완료되면 3일 이내 지급 가능 |",
        "| 선결 조건 | 검사·검수 완료, 세금계산서·청구서·계약서류 적정성 확인 |",
        "",
        "### 실무 포인트",
        "- `부산 소상공인 지원`은 조기 지급의 정책 목적이 될 수 있지만, 지급 자체의 법적 전제는 검수 완료와 적정한 대금청구입니다.",
        "- 계약금액, 납품내역, 하자·지체 여부가 정리되지 않았는데 지역업체라는 이유만으로 먼저 지급하면 정산 리스크가 생깁니다.",
        "- 내부 지출부서에는 `지방계약법상 5일 이내 지급기한 안에서 지역 소상공인 유동성 지원을 위해 3일 이내 처리`라고 정리하면 됩니다.",
        "",
        "근거: 「지방계약법」 제18조, 「지방계약법 시행령」 제67조, 지방계약 대가 지급기한 특례 고시",
    ])


def _is_shopping_mall_busan_vendor_filter_question(q: str) -> bool:
    return (
        any(term in q for term in ("종합쇼핑몰", "나라장터쇼핑몰", "나라장터 종합쇼핑몰", "쇼핑몰"))
        and any(term in q for term in ("부산", "지역업체", "업체지역", "소재"))
        and any(term in q for term in ("필터", "검색", "보는법", "보는 법", "찾는법", "찾는 법"))
    )


def _shopping_mall_busan_vendor_filter_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **나라장터 종합쇼핑몰에서 품명을 먼저 검색한 뒤 상세검색의 업체지역 조건을 `부산`으로 좁혀 보면 됩니다.**",
        "다만 업체지역 필터는 후보 탐색 도구이고, 계약 가능 여부는 MAS 계약상대자, 납품지역, 세부품명, 2단계 경쟁 대상 여부를 다시 확인해야 합니다.",
        "",
        "### 검색 순서",
        "1. 나라장터 종합쇼핑몰(shop.g2b.go.kr)에 접속합니다.",
        "2. 검색창에 세부품명 또는 품명(예: 데스크톱컴퓨터, 노트북컴퓨터, 냉난방기)을 입력합니다.",
        "3. 결과 화면에서 `상세검색` 또는 `결과 내 검색`을 엽니다.",
        "4. `업체지역`, `본사 소재지`, `공급업체 지역` 등 지역 필터가 있으면 `부산광역시`를 선택합니다.",
        "5. 후보 제품별로 MAS 계약 여부, 납품가능지역, 납기, A/S, 제조사·공급사 구분을 확인합니다.",
        "",
        "### 주의할 점",
        "- `부산 업체 제품만 보기`는 후보를 찾는 절차이지, 고액 물품에서 부산 업체를 임의 지정할 수 있다는 뜻은 아닙니다.",
        "- MAS 2단계 경쟁 대상 금액이면 부산 후보를 포함해 제안요청 절차를 거쳐야 하고, 직접구매 기준 미만이면 부산 업체 상품을 우선 비교할 수 있습니다.",
        "- 중소기업자간 경쟁제품이면 직접생산확인과 세부품명 일치 여부를 함께 확인합니다.",
        "",
        "근거: 나라장터 종합쇼핑몰 검색 기능, 물품 다수공급자계약 업무처리규정, 물품 다수공급자계약 2단계경쟁 업무처리기준",
    ])


def _is_desktop_mas_second_stage_threshold_question(q: str) -> bool:
    return (
        any(term in q for term in ("컴퓨터", "데스크톱", "데스크탑", "pc"))
        and any(term in q for term in ("mas", "종합쇼핑몰", "2단계", "2단계경쟁"))
        and any(term in q for term in ("거치지않고", "바로", "직접", "금액", "얼마", "기준"))
        and any(term in q for term in ("부산", "지역업체", "업체"))
    )


def _desktop_mas_second_stage_threshold_answer() -> str:
    general_threshold = get_numeric_display("P_MAS_SECOND_STAGE_GENERAL_THRESHOLD") or "5천만원"
    sme_competition_threshold = get_numeric_display("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD") or "1억원"
    return "\n".join([
        "결론부터 말하면, **데스크톱 컴퓨터가 중소기업자간 경쟁제품으로 MAS에 등록되어 있다면 2단계 경쟁 기준은 통상 1회 납품요구대상 구매예산 `1억원 이상`부터 봅니다.**",
        f"따라서 **{sme_competition_threshold} 미만**이면 2단계 경쟁 없이 종합쇼핑몰 납품요구·직접구매 가능성을 먼저 검토할 수 있습니다.",
        "",
        "| 구분 | MAS 2단계 경쟁 기준 | 실무 의미 |",
        "|---|---|---|",
        f"| 일반 제품 | {general_threshold} 이상 | 일반 MAS 물품은 5천만원 이상이면 2단계 경쟁 검토 |",
        f"| 중소기업자간 경쟁제품 | {sme_competition_threshold} 이상 | 데스크톱컴퓨터가 해당되면 1억원 미만은 바로구매 가능성 검토 |",
        "| 부산 업체 상품 | 금액 기준을 먼저 본 뒤 후보 비교 | 부산 업체 필터는 후보 탐색 수단이지 고액 지정구매 근거가 아님 |",
        "",
        "### 실무 순서",
        "1. 세부품명이 `데스크톱컴퓨터` 등으로 중소기업자간 경쟁제품인지 확인합니다.",
        "2. 나라장터 종합쇼핑몰에서 부산 소재 계약상대자와 납품가능지역을 검색합니다.",
        "3. 1회 납품요구대상 금액이 중소기업자간 경쟁제품 기준 미만이면 부산 후보 상품을 비교해 납품요구를 검토합니다.",
        "4. 기준 이상이면 MAS 2단계 경쟁을 진행하고, 납기·A/S·현장지원 등 과업 관련 요소로 평가합니다.",
        "",
        "근거: 조달청 2단계경쟁 제도 안내, 「물품 다수공급자계약 2단계경쟁 업무처리기준」",
    ])


def _is_mas_candidate_must_include_local_vendor_question(q: str) -> bool:
    return (
        any(term in q for term in ("mas", "종합쇼핑몰", "2단계", "2단계경쟁"))
        and any(term in q for term in ("5개", "5인", "후보", "제안요청", "제안 요청"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("반드시", "의무", "포함해야", "넣어야"))
    )


def _mas_candidate_must_include_local_vendor_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **조달청 MAS 2단계 경쟁 규정상 5개 이상 제안요청 대상자에 부산 업체를 반드시 포함해야 하는 일반 의무는 아닙니다.**",
        "다만 부산시 또는 기관 내부 지역업체 구매 촉진 지침이 있으면, 적격한 부산 MAS 계약상대자를 후보군에 포함하도록 시장조사 단계에서 검토하는 것이 실무상 안전합니다.",
        "",
        "| 구분 | 판단 |",
        "|---|---|",
        "| 조달청 MAS 규정 | 5개사 이상 제안요청 또는 종합쇼핑몰 자동선정 방식이 기본. 지역업체 필수 포함 조항으로 보기는 어려움 |",
        "| 기관 내부 지침 | 부산 지역업체 우선 검토 지침이 있으면 후보 탐색·시장조사 자료에 부산 업체 검토 이력을 남김 |",
        "| 실제 포함 가능성 | 동일 세부품명, 계약상태, 납품가능지역, 납기·A/S 요건을 충족하는 부산 업체가 있으면 제안요청 대상에 포함 검토 |",
        "| 주의 | 부산 업체를 넣기 위해 세부품명·규격·평가기준을 특정 업체에 맞추면 부당제한 위험 |",
        "",
        "### 실무 처리",
        "- 먼저 종합쇼핑몰에서 같은 세부품명으로 부산 소재 MAS 계약상대자가 있는지 검색합니다.",
        "- 5개 후보를 직접 선정하는 방식이면 부산 업체가 적격한 경우 포함 검토하되, 없으면 `부산 적격 MAS 업체 없음`을 시장조사 자료로 남깁니다.",
        "- 자동선정 방식을 쓰는 경우에는 시스템 선정 결과를 따르고, 부산 업체 포함 여부를 별도 강제하지 않는 편이 안전합니다.",
        "",
        "근거: 조달청 2단계경쟁 제도 안내, 「물품 다수공급자계약 2단계경쟁 업무처리기준」, 기관별 지역업체 구매촉진 지침",
    ])


def _is_mas_regional_point_amount_question(q: str) -> bool:
    if any(term in q for term in ("상향", "자체기준", "자체 기준", "5점이상", "5점 이상")):
        return False
    return (
        any(term in q for term in ("mas", "종합쇼핑몰", "2단계", "2단계경쟁"))
        and any(term in q for term in ("지역업체", "지역 업체", "부산업체", "부산 업체"))
        and any(term in q for term in ("배점", "몇점", "몇 점", "점수", "가점", "평가기준", "평가 기준"))
    )


def _mas_regional_point_amount_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **MAS 2단계 경쟁에서 지역업체 우대 배점은 임의로 정하는 것이 아니라 조달청 2단계경쟁 업무처리기준의 평가방식과 선택평가항목 배점한도 안에서만 줄 수 있습니다.**",
        "최신 별표 기준은 적용 시점에 확인해야 하지만, 지역업체 항목은 종합평가방식의 선택평가항목 배점한도(예: 7.5점 이하로 안내되는 기준) 안에서 검토하는 구조입니다.",
        "",
        "| 평가방식 | 지역업체 배점 처리 |",
        "|---|---|",
        "| 표준평가방식 | 조달청이 제공하는 방식 그대로 사용. 별도 항목 추가나 배점 조정 불가 |",
        "| 종합평가방식 | 기본평가와 선택평가를 구성하면서 `지역업체` 선택평가항목을 배점한도 안에서 반영 가능 |",
        "| 기관 임의 가점 | 공고문에 없는 별도 부산업체 가점, 배점한도 초과, 특정업체 유리 배점은 부당제한 위험 |",
        "",
        "### 실무 권장",
        "- 지역업체 배점을 쓰려면 `종합평가방식`을 선택했는지 먼저 확인합니다.",
        "- 제안요청서에는 `지역업체 여부` 항목, 배점, 확인 기준(본사 소재지 등), 기준일을 명확히 씁니다.",
        "- 표준평가방식을 쓰면서 별도로 부산업체 가점을 붙이는 방식은 피해야 합니다.",
        "- 지역업체 배점만으로 부족하면 납기, 사후관리, 현장 A/S처럼 품목 수행과 직접 관련된 평가요소도 함께 설계합니다.",
        "",
        "근거: 조달청 2단계경쟁 제도 안내, 「물품 다수공급자계약 2단계경쟁 업무처리기준」의 종합평가방식·표준평가방식 및 선택평가항목",
    ])


def _is_local_vendor_higher_price_audit_risk_question(q: str) -> bool:
    return (
        any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("조달단가", "조달 단가", "쇼핑몰단가", "비싼", "비싸", "높은"))
        and any(term in q for term in ("배임", "감사", "구매해도", "사도", "보호", "리스크"))
    )


def _local_vendor_higher_price_audit_risk_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 업체 보호만을 이유로 조달 단가보다 비싼 제품을 선택하면 감사 지적과 예산낭비 논란이 생길 수 있습니다.**",
        "배임 해당 여부는 수사·법률 판단 영역이지만, 계약 실무에서는 경제성 원칙과 가격 적정성 증빙을 먼저 갖춰야 합니다.",
        "",
        "| 검토 항목 | 안전한 판단 기준 |",
        "|---|---|",
        "| 가격 비교 | 나라장터 종합쇼핑몰 단가, MAS 제안가격, 타 기관 계약사례, 시장견적을 비교 |",
        "| 합리적 사유 | 운송비 절감, 긴급 A/S, 납기 단축, 현장 설치·유지보수 포함 등 가격 차이를 설명할 사유 필요 |",
        "| 지역업체 보호 | 보조적 고려는 가능하지만 가격 차이를 정당화하는 단독 사유로 쓰기는 어려움 |",
        "| 문서화 | 가격검토서, 시장조사표, 비교견적, 품질·유지보수 차이 자료를 결재문서에 첨부 |",
        "",
        "### 실무 결론",
        "- 같은 규격·같은 조건인데 부산 업체 제품이 더 비싸다면 그대로 구매하지 말고 가격협상 또는 경쟁절차를 먼저 검토합니다.",
        "- 단가가 높아도 총비용 기준으로 더 유리한 경우, 예를 들어 배송·설치·A/S·장애 대응 비용까지 합산하면 유리하다는 자료가 있어야 합니다.",
        "- 지역업체 구매 실적을 높이려면 비싼 제품을 지정하기보다 부산 업체가 참여 가능한 지역제한, MAS 2단계 평가항목, 납기·A/S 평가요소를 설계하는 방식이 안전합니다.",
        "",
        "근거: 「지방계약법」의 공정성·경제성 원칙, 지방자치단체 입찰 및 계약집행기준, 물품 다수공급자계약 업무처리규정",
    ])


def _is_third_party_local_specialty_innovation_search_question(q: str) -> bool:
    return (
        any(term in q for term in ("제3자단가", "3자단가", "종합쇼핑몰", "나라장터"))
        and any(term in q for term in ("특산품", "혁신제품", "지역특산", "키워드", "검색어"))
        and any(term in q for term in ("부산", "지역"))
        and any(term in q for term in ("찾", "검색", "키워드"))
    )


def _third_party_local_specialty_innovation_search_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **나라장터 종합쇼핑몰은 `품명 검색 + 상세검색의 지역 필터`로 부산 제3자단가·MAS 후보를 찾고, 혁신제품은 혁신장터에서 별도로 검색하는 것이 좋습니다.**",
        "특산품은 법정 조달분류명이 아닐 수 있으므로 실제 세부품명과 지역 키워드를 함께 써야 합니다.",
        "",
        "| 찾는 대상 | 검색 위치 | 추천 키워드 |",
        "|---|---|---|",
        "| 제3자단가·MAS 물품 | 나라장터 종합쇼핑몰 | `부산`, `부산광역시`, 실제 품명, 세부품명번호, 제조사명 |",
        "| 지역 특산품 | 종합쇼핑몰/나라장터 | `기장`, `해운대`, `동래`, `수산물`, `어묵`, `해조류`, `관광기념품` 등 실제 품목어 |",
        "| 혁신제품 | 혁신장터 | `부산`, `혁신제품`, 기술명, 제품명, 인증명 |",
        "| 기술개발제품 | 종합쇼핑몰/혁신장터 | `우수조달`, `성능인증`, `NET`, `NEP`, `GS`, `벤처나라` |",
        "",
        "### 검색 순서",
        "1. 종합쇼핑몰에서 품명 또는 세부품명으로 검색합니다.",
        "2. 상세검색에서 업체지역 또는 본사 소재지를 `부산광역시`로 좁힙니다.",
        "3. 제3자단가계약, MAS, 납품가능지역, 계약기간, 계약상태를 확인합니다.",
        "4. 혁신제품은 혁신장터에서 같은 키워드와 부산 소재 기업명을 별도 검색합니다.",
        "5. 후보를 찾은 뒤에는 특정 업체 내정처럼 보이지 않도록 시장조사표와 비교 후보를 함께 남깁니다.",
        "",
        "근거: 나라장터 종합쇼핑몰 상세검색, 혁신장터 검색, 제3자단가계약·다수공급자계약 구매 절차",
    ])


def _is_mas_non_lowest_local_vendor_selection_question(q: str) -> bool:
    return (
        any(term in q for term in ("mas", "종합쇼핑몰", "2단계", "2단계경쟁"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("최저가", "최저가격", "최저", "낙찰", "선정"))
        and any(term in q for term in ("아닐", "아니", "방법", "가능"))
    )


def _mas_non_lowest_local_vendor_selection_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **MAS 2단계 경쟁에서 부산 업체가 최저가가 아니어도 종합평가 총점이 가장 높으면 납품대상자로 선정될 수 있습니다.**",
        "다만 부산 업체를 선정하기 위해 사후에 평가항목을 바꾸거나 가격보다 지역성만 크게 반영하는 방식은 부당한 평가가 될 수 있습니다.",
        "",
        "| 방식 | 최저가가 아니어도 선정 가능성 | 주의점 |",
        "|---|---|---|",
        "| 표준평가방식 | 정해진 방식에 따라 가격·품질 등 점수로 결정 | 별도 지역업체 항목 추가나 배점 조정 불가 |",
        "| 종합평가방식 | 가격 외 품질, 납기, 사후관리, 선택평가항목을 반영해 총점으로 선정 가능 | 제안요청 전에 항목·배점을 정해야 함 |",
        "| 지역업체 항목 | 선택평가항목 배점한도 안에서 검토 가능 | 본사 소재지 기준, 확인서류, 기준일을 명확히 해야 함 |",
        "",
        "### 실무 설계",
        "- 제안요청 단계에서 종합평가방식을 선택하고 지역업체, 납기, A/S, 현장지원, 품질관리 등 정당한 항목을 미리 설정합니다.",
        "- 평가 결과 부산 업체가 최저가는 아니더라도 총점 1위라면 선정 근거가 생깁니다.",
        "- 이미 가격제안이 끝난 뒤 부산 업체를 살리기 위해 평가항목을 추가하거나 배점을 바꾸면 안 됩니다.",
        "- 가격 차이가 큰 경우에는 지역업체 항목만으로 방어하지 말고 총비용, 유지보수, 장애 대응, 납품 안정성 자료를 함께 남깁니다.",
        "",
        "근거: 조달청 2단계경쟁 제도 안내, 「물품 다수공급자계약 2단계경쟁 업무처리기준」의 종합평가방식·표준평가방식",
    ])


def _is_excellent_procurement_shopping_mall_order_question(q: str) -> bool:
    return (
        any(term in q for term in ("우수조달", "우수 조달", "우수제품", "우수 제품"))
        and any(term in q for term in ("부산업체", "부산 업체", "부산"))
        and any(term in q for term in ("수의계약", "사고싶", "구매", "납품요구", "승인", "나라장터"))
    )


def _excellent_procurement_shopping_mall_order_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **우수조달물품이 나라장터 종합쇼핑몰에 등록되어 있으면 별도 입찰 승인보다 종합쇼핑몰 `납품요구` 절차로 구매하는 것이 보통 가장 안전합니다.**",
        "우수조달물품은 지방계약법상 수의계약 사유가 될 수 있고, 종합쇼핑몰 등록 물품이면 조달청 계약 단가를 근거로 납품요구를 진행합니다.",
        "",
        "| 확인 항목 | 실무 처리 |",
        "|---|---|",
        "| 우수조달 지정 | 우수조달물품 지정번호, 유효기간, 제품명·규격 일치 확인 |",
        "| 종합쇼핑몰 등록 | 나라장터 종합쇼핑몰에서 계약상태, 단가, 납품가능지역, 계약기간 확인 |",
        "| 구매 방식 | 쇼핑몰 등록 물품이면 자체 수의계약보다 납품요구가 우선 검토 경로 |",
        "| MAS 2단계 경쟁 | 우수조달물품 등 별도 제도 물품은 일반 MAS 2단계 경쟁 대상인지 예외인지 쇼핑몰 계약조건으로 확인 |",
        "",
        "### 나라장터 처리 순서",
        "1. 종합쇼핑몰에서 제품명 또는 우수조달 지정번호로 검색합니다.",
        "2. 부산 업체 제품인지, 계약상대자와 제조사가 일치하는지 확인합니다.",
        "3. 납품요구 가능 금액, 납품기한, 인도조건, 하자보증 조건을 확인합니다.",
        "4. 내부 결재에는 `우수조달물품 지정 + 종합쇼핑몰 계약단가 + 납품요구` 근거를 함께 적습니다.",
        "5. 쇼핑몰에 없거나 특수조건이 필요한 경우에만 자체 수의계약 사유서와 가격 적정성 자료를 별도로 준비합니다.",
        "",
        "근거: 「지방계약법 시행령」 제25조제1항제6호 라목, 우수조달물품 지정관리 규정, 나라장터 종합쇼핑몰 납품요구 절차",
    ])


def _is_innovative_prototype_pilot_purchase_question(q: str) -> bool:
    return (
        any(term in q for term in ("혁신시제품", "혁신 시제품", "혁신제품"))
        and any(term in q for term in ("시범구매", "시범 구매", "시범사용", "시범 사용"))
        and any(term in q for term in ("참여", "신청", "방법", "예산", "지원", "범위"))
    )


def _innovative_prototype_pilot_purchase_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 소재 기업 제품도 혁신시제품으로 지정되면 혁신장터(ppi.g2b.go.kr)를 통해 시범구매 사업에 연결할 수 있습니다.**",
        "참여 절차는 `기업의 혁신제품 지정 신청`과 `수요기관의 시범사용 신청`을 분리해서 봐야 합니다.",
        "",
        "| 주체 | 해야 할 일 |",
        "|---|---|",
        "| 기업 | 혁신장터에서 혁신제품·혁신시제품 지정 공고 확인 → 제품 신청 → 혁신성·공공성·조달적합성 평가 → 지정 후 혁신제품전용몰 등록 |",
        "| 수요기관 | 혁신장터에서 필요한 제품 검색 → 시범사용 수요 신청 또는 자체예산 구매 검토 → 수요매칭 결과에 따라 시범사용 |",
        "| 조달청 | 선정된 혁신제품을 조달청 예산으로 구매해 수요기관에 제공하고 사용결과를 평가·피드백 |",
        "",
        "### 예산 지원 범위",
        "- 조달청 시범구매사업에 선정되면 조달청 예산으로 제품을 구매해 수요기관이 시범사용할 수 있습니다.",
        "- 지원 금액과 수량은 해당 연도 공고, 수요매칭 결과, 제품 단가와 예산 규모에 따라 달라지므로 `정액 보장`으로 안내하면 안 됩니다.",
        "- 시범구매 대상이 아니거나 매칭되지 않은 경우에도 혁신제품전용몰 등록 제품은 수요기관 자체예산으로 구매를 검토할 수 있습니다.",
        "",
        "### 부산업체 실무 포인트",
        "- 부산 기업에는 혁신제품 지정 신청 자료, 부산시 실증사업 이력, 공공서비스 개선 효과, 납품·A/S 가능성을 함께 준비하게 합니다.",
        "- 수요기관은 `부산업체라서`가 아니라 `공공서비스 개선을 위한 혁신제품 시범사용 필요성`으로 신청 사유를 써야 합니다.",
        "- 이미 혁신장터 등록 제품인지, 지정 유효기간이 남아 있는지, 수의계약·시범구매·자체예산 구매 중 어느 경로인지 구분합니다.",
        "",
        "근거: 조달청 혁신제품 지정 안내, 혁신장터(ppi.g2b.go.kr), 혁신제품 구매 운영 규정, 혁신시제품 시범구매사업 안내",
    ])


def _is_supplier_shopping_mall_entry_support_question(q: str) -> bool:
    return (
        any(term in q for term in ("나라장터", "종합쇼핑몰", "쇼핑몰", "mas", "다수공급자"))
        and any(term in q for term in ("입점", "등록", "새로", "업체가", "기업이"))
        and any(term in q for term in ("부산", "지역업체", "부산업체"))
        and any(term in q for term in ("지원", "컨설팅", "받을수", "받을 수", "도움"))
    )


def _supplier_shopping_mall_entry_support_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 업체가 나라장터 종합쇼핑몰에 새로 입점하려면 계약법보다 `조달시장 진출 지원사업`과 `조달청 등록·컨설팅 경로`를 먼저 안내해야 합니다.**",
        "발주기관의 구매 방식 답변이 아니라 공급기업의 판로 진입 지원 답변으로 처리하는 것이 맞습니다.",
        "",
        "| 지원 경로 | 받을 수 있는 도움 | 확인처 |",
        "|---|---|---|",
        "| 부산지방조달청 공공조달 길잡이 | 조달업체 등록, MAS·벤처나라·혁신제품·우수제품 진입 상담 | 부산지방조달청/조달청 공공조달 길잡이 |",
        "| 부산경제진흥원·구군 지원사업 | MAS, 벤처나라, 이음장터, 전자입찰 1:1 컨설팅 지원 | 부산경제진흥원, 부산시·구군 기업지원 공고 |",
        "| MAS 컨설팅 | 규격서, 시험성적서, 가격자료, 납품실적, 계약요건 준비 | 다수공급자계약 컨설팅 사업 |",
        "| 벤처나라 후보 추천 | 창업·벤처기업 제품의 벤처나라 등록 후보 추천 및 컨설팅 | 지자체 추천기관, 조달청 벤처나라 |",
        "| 혁신제품·우수제품 | 기술개발제품이면 혁신제품·우수조달 지정 가능성 검토 | 혁신장터, 조달청 우수제품 담당 |",
        "",
        "### 기업 준비 체크리스트",
        "- 나라장터 조달업체 등록과 입찰참가자격 등록을 먼저 확인합니다.",
        "- 품목이 물품인지 용역인지, 세부품명번호와 직접생산확인 필요 여부를 정리합니다.",
        "- MAS 입점이면 규격서, 시험성적서, 가격자료, 납품·거래실적, 인증자료를 준비합니다.",
        "- 창업·벤처기업이면 벤처나라, 기술개발제품이면 혁신제품·우수조달 경로를 함께 봅니다.",
        "- 부산경제진흥원과 관할 구·군의 공공조달시장 진출지원 사업 공고는 매년 달라지므로 신청기간을 확인해야 합니다.",
        "",
        "근거: 부산지방조달청 공공조달 길잡이, 조달청 다수공급자계약(MAS) 제도, 벤처나라 운영, 부산경제진흥원·구군 공공조달시장 진출지원 사업 공고",
    ])


def _is_mas_local_participation_score_increase_question(q: str) -> bool:
    return (
        any(term in q for term in ("mas", "2단계", "2단계경쟁", "다수공급자"))
        and any(term in q for term in ("지역업체참여도", "지역 업체 참여도", "지역업체", "지역 업체"))
        and any(term in q for term in ("5점", "상향", "자체기준", "자체 기준", "초과", "이상"))
    )


def _mas_local_participation_score_increase_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **기관 자체 기준만으로 MAS 2단계 경쟁의 지역업체 배점을 마음대로 5점 이상으로 올릴 수는 없습니다.**",
        "적용 가능한 상한은 조달청 「다수공급자계약 2단계경쟁 업무처리기준」 별표의 `지역업체` 선택평가항목 배점한도와 해당 기관이 공고에서 채택한 평가표가 결정합니다.",
        "",
        "| 경우 | 판단 |",
        "|---|---|",
        "| 기관 자체 평가표가 5점 이하로 정한 경우 | 자체 기준을 적용했다면 5점 초과 부여는 불가 |",
        "| 최신 조달청 별표가 더 높은 배점한도(예: 7.5점 이하)를 허용하는 경우 | 그 범위 안에서만 제안요청 전에 평가표로 확정 가능 |",
        "| 표준평가방식 | 별도 지역업체 배점 신설·상향 조정 불가 |",
        "| 종합평가방식 | 선택평가항목 배점한도 안에서 지역업체 여부를 반영 가능 |",
        "",
        "### 실무 처리",
        "- 먼저 해당 제안요청이 표준평가방식인지 종합평가방식인지 확인합니다.",
        "- 종합평가방식이면 최신 조달청 별표의 `지역업체` 배점한도와 기관 자체 평가표의 배점 중 더 엄격한 기준을 적용합니다.",
        "- 제안요청 이후 부산 업체를 유리하게 하려고 배점을 상향하면 안 됩니다.",
        "- 배점을 올리는 대신 납기, 사후관리, A/S, 현장대응 등 품목 수행과 직접 관련된 항목으로 정당성을 보강하는 편이 안전합니다.",
        "",
        "근거: 「물품 다수공급자계약 2단계경쟁 업무처리기준」 별표의 종합평가방식·선택평가항목, 조달청 2단계경쟁 제도 안내",
    ])


def _is_desired_quantity_bid_split_delivery_question(q: str) -> bool:
    return (
        any(term in q for term in ("희망수량", "희망 수량"))
        and any(term in q for term in ("분할납품", "분할 납품", "분할", "납품요구", "납품 요구"))
        and any(term in q for term in ("가능", "대상", "제품", "물품"))
    )


def _desired_quantity_bid_split_delivery_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **희망수량 경쟁입찰 대상 물품의 분할 납품은 공고문과 계약조건에 예정되어 있으면 가능합니다.**",
        "다만 부산 업체 제품이라는 이유로 낙찰 후 임의로 물량을 쪼개거나 납품조건을 바꾸는 것은 안 됩니다.",
        "",
        "| 확인 항목 | 실무 판단 |",
        "|---|---|",
        "| 입찰 방식 | 희망수량 경쟁입찰인지, 단가계약·MAS인지 먼저 구분 |",
        "| 공고문 | 총 구매예정수량, 납품장소, 납품기한, 부분납품 허용 여부 확인 |",
        "| 계약조건 | 물품구매계약 일반조건·특수조건의 분할납품, 검사·검수, 대금 지급 조건 확인 |",
        "| 낙찰 후 변경 | 계약상대자 유리·불리 변경이 되지 않도록 변경계약 사유와 물량 배분 근거 필요 |",
        "",
        "### 실무 처리",
        "- 처음부터 여러 납품장소나 순차 납품이 예상되면 공고문에 분할 납품 조건을 명시합니다.",
        "- 낙찰 후 사정 변경으로 분할 납품이 필요하면 계약조건상 허용 여부, 납품기한 연장, 지체상금, 검사·검수 단위를 함께 검토합니다.",
        "- 지역업체 보호 목적은 보조적 정책 고려일 뿐, 희망수량 경쟁입찰의 물량 배분·분할 납품 근거가 되지는 않습니다.",
        "",
        "근거: 「지방계약법 시행령」 제17조, 물품구매계약 일반조건, 입찰공고문 및 계약특수조건",
    ])


def _is_unregistered_shopping_mall_local_product_direct_contract_question(q: str) -> bool:
    return (
        any(term in q for term in ("종합쇼핑몰", "나라장터쇼핑몰", "나라장터 쇼핑몰", "쇼핑몰", "mas"))
        and any(term in q for term in ("등록되지않", "등록 되지 않", "미등록", "없", "없는"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("수의계약", "자체수의", "자체 수의", "사도", "구매"))
    )


def _unregistered_shopping_mall_local_product_direct_contract_answer() -> str:
    general_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    policy_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **나라장터 종합쇼핑몰에 등록되지 않은 부산 업체 제품도 요건을 충족하면 자체 수의계약을 검토할 수 있습니다.**",
        "하지만 `부산 업체 제품`이라는 이유만으로 수의계약이 되는 것은 아니며, 금액 기준과 법정 수의계약 사유, MAS 대체품 존재 여부를 먼저 확인해야 합니다.",
        "",
        "| 확인 항목 | 실무 판단 |",
        "|---|---|",
        f"| 일반 1인 견적 | 추정가격 **{general_one_quote} 이하**이면 일반 소액 1인 견적 가능성 검토 |",
        f"| 정책기업 | 여성기업·장애인기업·사회적기업·청년창업기업 등은 **{policy_one_quote} 이하** 특례 검토 |",
        "| 인증·특례 제품 | 우수조달, 혁신제품, 성능인증, 특허·신기술 등 별도 수의계약 사유가 있으면 금액과 별개로 검토 |",
        "| MAS 대체품 | 종합쇼핑몰에 같은 세부품명·동등 규격의 대체품이 있는지 시장조사 필요 |",
        "| 중소기업자간 경쟁제품 | 해당되면 직접생산확인과 경쟁제품 예외 여부 확인 |",
        "",
        "### 실무 결론",
        "- 금액이 일반 1인 견적 기준을 넘고 정책기업·인증제품·특수사유도 없으면 부산 업체 제품이라도 자체 1인 수의계약은 위험합니다.",
        "- 쇼핑몰 미등록은 `자체 계약 가능`의 자동 근거가 아니라, 조달구매 경로가 없다는 시장조사 자료 중 하나입니다.",
        "- 같은 규격의 MAS 상품이 있으면 MAS 납품요구나 2단계 경쟁을 먼저 검토하고, 자체계약을 선택할 때는 왜 쇼핑몰 물품으로 대체하기 어려운지 남겨야 합니다.",
        "",
        "근거: 「지방계약법 시행령」 제25조ㆍ제30조, 물품 다수공급자계약 업무처리규정, 중소기업자간 경쟁제품 직접생산 확인기준",
    ])


def _is_shopping_mall_lower_spec_higher_price_justification_question(q: str) -> bool:
    return (
        any(term in q for term in ("쇼핑몰", "종합쇼핑몰", "나라장터"))
        and any(term in q for term in ("직접구매", "직접 구매", "바로구매", "납품요구"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("사양", "스펙", "규격"))
        and any(term in q for term in ("낮", "높", "비싸", "가격"))
    )


def _shopping_mall_lower_spec_higher_price_justification_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **쇼핑몰 직접 구매에서 부산 업체 제품이 사양은 낮고 가격은 높다면 구매 정당성 확보가 매우 어렵습니다.**",
        "지역업체 보호만으로는 충분하지 않고, 최소 요구 사양 충족 여부와 총비용 관점의 합리적 사유를 문서화해야 합니다.",
        "",
        "| 판단 항목 | 실무 기준 |",
        "|---|---|",
        "| 최소 사양 | 과업·규격서의 필수 성능을 충족하지 못하면 가격과 무관하게 후보 제외 |",
        "| 가격 적정성 | 동등 규격 상품, 종합쇼핑몰 단가, 시장가격, 유지보수 포함 총비용 비교 |",
        "| 지역업체 고려 | 납기, A/S, 장애 대응, 현장설치 등 수행과 직접 관련된 장점만 보조 사유로 활용 |",
        "| 법정 우선구매 | 여성기업·장애인기업·사회적기업 등 실적 목적이 있어도 필수 사양 미달을 정당화하지는 못함 |",
        "",
        "### 정당성 확보가 가능한 경우",
        "- 표시 사양은 낮아 보여도 실제 필수 기능은 충족하고, 유지보수·납기·현장 대응을 포함한 총비용이 더 유리한 경우.",
        "- 기관의 최소 규격을 충족하며, 법정 우선구매 대상 제품이고 가격 차이가 합리적인 범위로 설명되는 경우.",
        "- 단순 성능 비교가 아니라 호환성, 설치공간, 기존 시스템 연동, 장애 대응 시간 등 과업 수행에 필요한 조건이 더 적합한 경우.",
        "",
        "### 피해야 할 처리",
        "- `부산 업체라서`라는 문구만으로 비싸고 사양 낮은 제품을 선택하는 것.",
        "- MAS 2단계 경쟁 대상 금액인데 직접구매로 쪼개거나, 비교표에서 더 나은 제품을 의도적으로 제외하는 것.",
        "- 필수 규격을 충족하지 못하는 제품을 우선구매 실적 목적만으로 선택하는 것.",
        "",
        "근거: 「지방계약법」의 공정성·경제성 원칙, 물품 다수공급자계약 업무처리규정, 기관 물품 규격서 및 검사·검수 기준",
    ])


def _is_mas_two_local_vendors_only_question(q: str) -> bool:
    return (
        any(term in q for term in ("mas", "2단계", "2단계경쟁", "종합쇼핑몰"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("2곳", "2개", "두곳", "두 곳", "2개사", "2인"))
        and any(term in q for term in ("지명", "경쟁", "공정거래", "위반"))
    )


def _mas_two_local_vendors_only_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **MAS 2단계 경쟁 대상인데 부산 업체 2곳만 지명해 경쟁시키는 방식은 원칙적으로 맞지 않습니다.**",
        "공정거래법 위반 여부를 따지기 전에, 조달청 다수공급자계약 2단계경쟁 기준상 제안요청 대상자 수 요건을 먼저 충족해야 합니다.",
        "",
        "| 항목 | 실무 판단 |",
        "|---|---|",
        "| 제안요청 대상 | 원칙적으로 5개사 이상의 계약상대자를 대상으로 제안요청 |",
        "| 부산 2곳만 지명 | 2단계 경쟁 요건 미충족 및 부당한 제한 논란 가능 |",
        "| 지역업체 우대 | 종합평가방식의 지역업체 선택평가항목, 납기·A/S·현장지원 등 정당한 항목으로 반영 |",
        "| 예외 검토 | 5개사 미만인 특수 상황은 쇼핑몰 시스템·계약조건·조달청 기준에 따른 예외 가능 여부를 별도 확인 |",
        "",
        "### 안전한 처리",
        "- 같은 세부품명으로 MAS 계약상대자가 5개사 이상 있는지 확인합니다.",
        "- 부산 업체가 2곳뿐이면 그 2곳을 포함하되, 전국 또는 적격 계약상대자까지 포함해 5개사 이상 제안요청하는 구조를 우선 봅니다.",
        "- 부산 업체 지원은 후보군 시장조사, 지역업체 선택평가항목, 납품·A/S 평가요소로 설계하고 `부산 2곳만 경쟁` 형태는 피합니다.",
        "",
        "근거: 「물품 다수공급자계약 2단계경쟁 업무처리기준」, 나라장터 종합쇼핑몰 제안요청 절차",
    ])


def _is_streetlight_fixture_public_material_question(q: str) -> bool:
    return (
        any(term in q for term in ("가로등", "등기구", "조명기구"))
        and any(term in q for term in ("공사", "교체"))
        and any(term in q for term in ("관급자재", "분리", "물품", "직접구매"))
        and any(term in q for term in ("부산", "지역업체", "부산업체"))
    )


def _streetlight_fixture_public_material_answer() -> str:
    general_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    policy_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **가로등 교체 공사에서 등기구만 관급자재로 분리 구매하는 것은 공사용 자재 직접구매 대상 여부와 설계 분리 가능성을 확인한 뒤 검토할 수 있습니다.**",
        "다만 부산 업체 제품을 지정하기 위한 임의 분할이 아니라, 공사와 물품의 책임 범위가 실제로 분리되는 구조여야 합니다.",
        "",
        "| 경로 | 실무 판단 |",
        "|---|---|",
        "| 관급자재 직접구매 | 등기구가 공사용 자재 직접구매 대상 품목인지, 직접생산확인 대상인지 확인 |",
        "| 종합쇼핑몰/MAS | 나라장터 종합쇼핑몰 등록 등기구가 있으면 납품요구 또는 2단계 경쟁을 우선 검토 |",
        f"| 1인 견적 | 일반 업체는 **{general_one_quote} 이하**, 정책기업은 **{policy_one_quote} 이하** 등 별도 한도 확인 |",
        "| 지역업체 고려 | 부산 업체 상품은 후보로 비교하되, 세부품명·규격·인증·납품조건이 맞아야 함 |",
        "",
        "### 부산 업체 지원 방식",
        "- MAS 직접구매 기준 미만이면 부산 소재 계약상대자 상품을 우선 비교할 수 있습니다.",
        "- 2단계 경쟁 대상이면 종합평가방식의 지역업체 선택항목, 납기, A/S, 현장지원 항목으로 반영합니다.",
        "- 자체 구매로 갈 경우에는 공사 설계서에서 등기구 공급, 설치, 하자 책임, 검수 주체를 분리해 적어야 합니다.",
        "",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 공사용 자재 직접구매 제도, 물품 다수공급자계약 업무처리규정, 「지방계약법 시행령」 제25조ㆍ제30조",
    ])


def _is_info_telecom_cctv_separate_procurement_question(q: str) -> bool:
    return (
        any(term in q for term in ("정보통신공사", "정보 통신 공사"))
        and any(term in q for term in ("cctv", "카메라", "보안용카메라"))
        and any(term in q for term in ("통합발주", "통합 발주", "분리발주", "분리 발주", "물품구매"))
    )


def _info_telecom_cctv_separate_procurement_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **정보통신공사와 CCTV 물품 구매는 지역업체 지원 목적의 임의 분할이 아니라 법정 분리발주·관급자재 직접구매 필요성 관점에서 검토해야 합니다.**",
        "정보통신공사는 원칙적으로 다른 공사와 분리발주해야 하고, CCTV 같은 물품은 세부품명·직접생산·MAS 등록 여부에 따라 별도 구매가 필요할 수 있습니다.",
        "",
        "| 구분 | 판단 |",
        "|---|---|",
        "| 정보통신공사 | 「정보통신공사업법」상 공사 분리발주 원칙 및 정보통신공사업 면허 확인 |",
        "| CCTV 물품 | 보안용카메라, 영상감시장치 등 세부품명과 중소기업자간 경쟁제품·직접생산확인 여부 확인 |",
        "| 관급자재 | 공사용 자재 직접구매 대상이면 공사에서 제외해 물품으로 별도 조달 검토 |",
        "| 지역업체 지원 | 합법적으로 분리한 뒤 물품은 MAS/지역제한/2단계 평가, 공사는 부산 지역제한 또는 지역의무 공동도급 검토 |",
        "",
        "### 주의할 점",
        "- `부산 업체 지원`만을 목적으로 금액을 쪼개는 분할발주는 감사 리스크가 큽니다.",
        "- 반대로 정보통신공사업법상 분리발주나 공사용 자재 직접구매 대상이면 분리 자체가 적정한 절차가 될 수 있습니다.",
        "- 물품 구매에 설치·배선·시운전이 포함되면 정보통신공사업 면허 또는 공사 부분 분리 필요성을 다시 봐야 합니다.",
        "- CCTV는 종합쇼핑몰/MAS, 직접생산확인, 보안·호환성 요건을 함께 확인해야 합니다.",
        "",
        "근거: 「정보통신공사업법」 제25조, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 공사용 자재 직접구매 제도, 물품 다수공급자계약 업무처리규정",
    ])


def _is_construction_waste_distance_restriction_question(q: str) -> bool:
    return (
        any(term in q for term in ("건설폐기물", "폐기물"))
        and any(term in q for term in ("중간처리", "처리용역", "처리 용역", "용역"))
        and any(term in q for term in ("거리", "반경", "km", "부산"))
        and any(term in q for term in ("제한", "지역제한", "업체로만"))
    )


def _construction_waste_distance_restriction_answer() -> str:
    service_regional_threshold = get_numeric_display("P_LOCAL_LIMITED_BID_SERVICE_THRESHOLD") or "3.3억원"
    return "\n".join([
        "결론부터 말하면, **건설폐기물 처리 용역에서 `현장 반경 몇 km 이내 중간처리업체`처럼 거리 기준으로 참가자격을 제한하는 것은 원칙적으로 부당제한 위험이 큽니다.**",
        "지역제한을 쓰려면 거리 반경이 아니라 지방계약법령의 행정구역 단위와 추정가격 기준을 봐야 합니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 거리 기준 | 반경·운반거리만으로 입찰참가자격 제한은 부당제한 위험 |",
        f"| 용역 지역제한 | 추정가격이 지역제한 가능 기준(일반용역은 통상 **{service_regional_threshold} 미만** 여부 확인) 안인지 검토 |",
        "| 행정구역 | 금액 기준이 맞으면 `부산광역시` 단위 지역제한 검토 |",
        "| 폐기물 처리 특성 | 허가업종, 처리능력, 운반거리, 처리시설 위치는 수행능력·가격·운반계획으로 평가 |",
        "",
        "### 실무 대안",
        "- 참가자격은 폐기물처리업 허가, 처리능력, 법정 인허가, 지역제한 가능 여부로 설계합니다.",
        "- 운반거리나 처리시설 접근성은 비용 산정, 운반계획, 처리기간, 환경·민원 대응 계획 같은 과업 관련 요소로 반영합니다.",
        "- 부산 내 적격 업체가 충분하지 않으면 부울경 또는 전국으로 신규공고 확대를 검토합니다.",
        "",
        "근거: 「지방계약법 시행규칙」 제24조, 「지방계약법 시행령」 제20조, 지방자치단체 입찰 및 계약집행기준의 부당한 제한 금지 취지",
    ])


def _is_distance_based_regional_restriction_question(q: str) -> bool:
    return (
        any(term in q for term in ("반경", "km", "킬로", "거리"))
        and any(term in q for term in ("참가자격", "참가 자격", "지역제한", "제한", "입찰"))
        and any(term in q for term in ("부산", "지역업체", "업체보호", "보호"))
    )


def _distance_based_regional_restriction_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **공사 현장에서 반경 10km 이내 업체처럼 거리 기준으로 입찰참가자격을 제한하는 것은 원칙적으로 부당제한 위험이 큽니다.**",
        "지방계약의 지역제한은 거리 반경이 아니라 법령이 정한 행정구역 단위로 설정해야 합니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 반경 10km 제한 | 법정 지역제한 단위가 아니므로 사용하지 않는 것이 안전 |",
        "| 행정구역 제한 | 금액·공종 기준을 충족하면 `부산광역시` 단위 지역제한 검토 |",
        "| 더 좁은 구·군 제한 | 일반적으로 과도한 제한 위험. 특수 사유 없으면 피함 |",
        "| 현장 대응 필요 | 참가자격 제한 대신 긴급출동, A/S, 현장관리 계획 등 과업 관련 평가요소로 반영 |",
        "",
        "### 대안",
        "- 지역제한 가능 금액이면 공고문 참가자격을 `부산광역시에 주된 영업소를 둔 업체`로 설정합니다.",
        "- 현장 접근성이 중요하면 `1시간 이내 출동`, `비상연락체계`, `현장대리인 배치계획`처럼 계약이행과 직접 관련된 조건으로 설계합니다.",
        "- 특정 반경·동·구 단위 제한은 민원이나 감사에서 경쟁 제한으로 지적될 수 있으므로 사유서가 매우 강해야 합니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「지방계약법 시행규칙」 제24조, 지방자치단체 입찰 및 계약집행기준의 부당한 입찰참가자격 제한 금지 취지",
    ])


def _is_landscape_local_tree_spec_question(q: str) -> bool:
    return (
        any(term in q for term in ("조경", "수목", "나무", "식재"))
        and any(term in q for term in ("부산", "지역", "재배", "지역산"))
        and any(term in q for term in ("설계서", "시방서", "명시", "우선사용", "우선 사용"))
    )


def _landscape_local_tree_spec_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **조경 공사 설계서에 `부산 지역에서 재배된 수목 우선 사용`을 직접 명시하는 것은 부당한 경쟁제한으로 볼 위험이 큽니다.**",
        "지역산 수목 활용이 필요하다면 공사 설계 조건이 아니라 관급자재·지급자재 분리 구매 또는 물품구매 지역제한 가능성으로 검토하는 편이 안전합니다.",
        "",
        "| 방식 | 판단 |",
        "|---|---|",
        "| 설계서에 부산산 수목 명시 | 특정 지역 자재 지정으로 경쟁제한 위험. 원칙적으로 피함 |",
        "| 품질·생육 조건 명시 | 수종, 규격, 뿌리분, 병충해, 활착률, 하자보증 등 객관 조건은 가능 |",
        "| 관급자재 분리 | 수목을 지급자재로 별도 구매할 수 있는지 설계·시공 책임 분리 검토 |",
        "| 물품 지역제한 | 금액 기준과 경쟁 가능 업체 수가 맞으면 부산 또는 해당 행정구역 지역제한 검토 |",
        "",
        "### 실무 설계",
        "- 설계서에는 `부산산`이 아니라 생육환경 적합성, 운반거리로 인한 품질저하 방지, 납품 후 활착관리 등 과업 수행과 직접 관련된 객관 요건을 씁니다.",
        "- 수목을 별도 관급자재로 구매할 경우에는 물품 세부품명, 수량, 규격, 검수 기준, 하자·활착 책임을 분리합니다.",
        "- 지역업체 지원은 수목 구매 단계에서 지역제한 가능 여부, MAS/조달등록 여부, 2인 이상 견적 또는 제한경쟁으로 검토합니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조, 「지방계약법 시행규칙」 제24조, 지방자치단체 입찰 및 계약집행기준의 부당한 특정규격·입찰참가자격 제한 금지 취지",
    ])


def _is_split_contract_to_distribute_local_vendors_question(q: str) -> bool:
    return (
        any(term in q for term in ("쪼개기", "쫄개기", "분할발주", "분할계약", "나눠"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "지역 업체"))
        and any(term in q for term in ("배분", "여러곳", "여러 곳", "수의계약", "피하면서", "정교한"))
    )


def _split_contract_to_distribute_local_vendors_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **쪼개기 발주 의심을 피하기 위한 논리로 부산 업체 여러 곳에 수의계약을 배분하는 방식은 안내할 수 없고, 실무상 매우 위험합니다.**",
        "같은 목적·같은 시기·같은 예산의 수요를 수의계약 한도에 맞추기 위해 나누면 부당한 분할계약으로 감사 지적 대상이 됩니다.",
        "",
        "| 구분 | 판단 |",
        "|---|---|",
        "| 지역업체 배분 목적 | 수의계약 사유가 아니라 위법·부당 분할 의심 사유 |",
        "| 동일 품목·동일 사업 | 연간·사업별 총수요를 합산해 통합 발주가 원칙 |",
        "| 예외적 분리 | 예측 불가능한 추가 수요, 예산 회계연도·사업목적 차이, 물리적·기술적 분리 필요성 등 객관 사유 필요 |",
        "| 적법 대안 | 부산 지역제한 경쟁입찰, 2인 이상 견적공고, MAS 2단계 경쟁, 지역의무 공동도급·참여도 평가 |",
        "",
        "### 안전한 처리",
        "- 먼저 총 소요량과 추정가격을 합산해 통합 발주 기준으로 계약방법을 정합니다.",
        "- 부산 업체 지원이 목적이면 수의계약 배분이 아니라 지역제한, 지역업체 참여도, 납기·A/S 평가항목을 설계합니다.",
        "- 부득이하게 나누어야 한다면 분리 사유, 예산 출처, 수요 발생 시점, 품목·현장·기술적 독립성을 문서화합니다.",
        "",
        "근거: 「지방계약법 시행령」 제77조, 지방자치단체 입찰 및 계약집행기준의 분할계약 금지 원칙, 「지방계약법 시행령」 제20조ㆍ제30조",
    ])


def _is_design_service_with_printing_question(q: str) -> bool:
    return (
        any(term in q for term in ("디자인", "홍보물", "포스터", "리플릿", "브로슈어"))
        and any(term in q for term in ("인쇄", "출력", "제작"))
        and any(term in q for term in ("용역", "발주", "포함", "부산"))
    )


def _design_service_with_printing_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **홍보물 디자인 용역에 인쇄까지 포함할 수는 있지만, 인쇄물의 중소기업자간 경쟁제품·직접생산확인 요건을 먼저 확인해야 합니다.**",
        "부산 디자인 업체가 디자인은 가능해도 인쇄 직접생산 자격이 없으면 인쇄까지 통합 수행시키는 구조가 문제가 될 수 있습니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 디자인 중심 용역 | 기획·편집·디자인이 주된 과업이고 인쇄가 소액 부수업무인지 확인 |",
        "| 인쇄물 제작 | 인쇄물이 주된 목적이면 물품 제조·구매 성격과 중소기업자간 경쟁제품 여부 확인 |",
        "| 직접생산확인 | 인쇄 관련 세부품명이 직접생산확인 대상이면 업체가 해당 증명서를 보유해야 함 |",
        "| 종합쇼핑몰/MAS | 등록 인쇄물·홍보물 제작 상품이 있으면 나라장터 종합쇼핑몰 경로도 검토 |",
        "",
        "### 실무 선택지",
        "- 디자인과 인쇄가 모두 필요한 경우, 디자인 용역과 인쇄 물품을 과업·검수·대금 기준으로 명확히 **분리 발주**하는 방식을 먼저 검토합니다.",
        "- 한 업체에 통합 발주하려면 그 업체가 디자인 수행능력뿐 아니라 인쇄 직접생산확인증명서와 납품 능력을 갖췄는지 확인합니다.",
        "- 부산 업체 지원은 부산 디자인 업체 지정이 아니라 지역제한 가능성, 직접생산 보유 부산 인쇄업체 후보, MAS 등록 여부로 설계합니다.",
        "",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 중소기업자간 경쟁제품·직접생산확인 제도, 「지방계약법 시행령」 제25조ㆍ제30조, 나라장터 종합쇼핑몰 구매 절차",
    ])


def _is_electrical_work_split_performance_joint_question(q: str) -> bool:
    return (
        any(term in q for term in ("전기공사", "전기 공사", "전기공사업"))
        and any(term in q for term in ("분담이행", "분담 이행", "공동이행", "공동도급", "지역의무"))
        and any(term in q for term in ("부산", "지역업체", "소규모", "설계법", "설계"))
    )


def _electrical_work_split_performance_joint_answer() -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    return "\n".join([
        "결론부터 말하면, **전기공사에서 부산 소규모 전기공사업체를 지원하려고 같은 전기공사업 면허 업체끼리 `분담이행방식`을 설계하는 것은 보통 맞지 않습니다.**",
        "분담이행은 서로 다른 공종·업무를 나누어 각자 책임지는 방식이고, 같은 전기공사업 면허로 같은 공사를 함께 수행하는 경우에는 공동이행방식 또는 지역의무 공동도급을 먼저 봐야 합니다.",
        "",
        "| 방식 | 적용 구조 | 전기공사에서의 포인트 |",
        "|---|---|---|",
        "| 공동이행방식 | 같은 공사를 공동수급체가 지분율에 따라 함께 이행 | 부산 업체 참여 확대에 주로 활용 |",
        "| 분담이행방식 | 전기, 통신, 소방 등 서로 다른 분담 공종을 각자 이행 | 같은 전기공사업체끼리 단순 배분용으로 쓰기 어려움 |",
        "| 지역의무 공동도급 | 일정 규모 공사에서 지역업체 참여를 의무화 | 지역업체 수, 면허, 시공능력, 공사 성격 확인 필요 |",
        "",
        "### 실무 설계",
        f"- 지역의무 공동도급을 적용할 수 있는 공사라면 부산 업체 참여비율을 원칙 {min_share}, 필요 시 {max_share} 이하 범위에서 검토합니다.",
        "- 공고문에는 공동수급체 구성 방식, 지역업체 최소 참여비율, 대표사 요건, 협정서 제출기한, 미충족 시 처리 기준을 명시합니다.",
        "- 단순히 소규모 업체에게 물량을 나누어 주기 위한 분담이행 구조는 감사·민원 리스크가 있으므로 피합니다.",
        "",
        "근거: 「지방계약법」 제29조, 「지방계약법 시행령」 제88조, 지방자치단체 입찰 및 계약집행기준 공동계약 운영요령",
    ])


def _is_contractor_bankruptcy_remaining_work_direct_contract_question(q: str) -> bool:
    return (
        any(term in q for term in ("부도", "파산", "공사중단", "공사가중단", "계약해지"))
        and any(term in q for term in ("잔여공사", "잔여 공사", "남은공사", "다른"))
        and any(term in q for term in ("수의계약", "부산업체", "부산 업체"))
    )


def _contractor_bankruptcy_remaining_work_direct_contract_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **기존 부산 업체가 부도로 공사를 중단했더라도 잔여 공사를 곧바로 다른 부산 업체와 수의계약하는 것은 원칙이 아닙니다.**",
        "먼저 계약 해제·해지, 보증시공, 공동수급체 잔여 구성원의 이행 가능성을 확인하고, 새 입찰에 부칠 여유가 없는 경우에만 예외적 수의계약을 검토합니다.",
        "",
        "| 순서 | 확인 내용 |",
        "|---|---|",
        "| 1. 계약상태 | 부도 사실, 공정률, 기성검사, 계약 해제·해지 사유 확인 |",
        "| 2. 보증시공 | 계약보증기관의 보증시공 또는 보증금 청구 절차 확인 |",
        "| 3. 공동수급체 | 공동계약이면 잔여 구성원의 이행 또는 보충 가능 여부 확인 |",
        "| 4. 재입찰 원칙 | 잔여 공사 범위와 예정가격을 다시 산정해 경쟁입찰 가능성 검토 |",
        "| 5. 예외 수의계약 | 공사 지연으로 중대한 손해가 있고 새 입찰에 부칠 여유가 없는 경우에 한해 검토 |",
        "",
        "### 부산 업체와 계약하려면",
        "- 수의계약 사유가 성립하더라도 `부산 업체라서`가 아니라 즉시 이행 가능성, 면허, 시공능력, 현장 인수 가능성, 가격 적정성으로 선정 근거를 세워야 합니다.",
        "- 시간 여유가 있으면 부산 지역제한 입찰 또는 2인 이상 견적 절차가 더 안전합니다.",
        "- 기존 업체의 기성·하자·미지급금과 새 업체의 잔여 공사 범위를 명확히 분리해야 합니다.",
        "",
        "근거: 「지방계약법 시행령」 제26조제2항, 「지방계약법 시행령」 제92조, 지방자치단체 공사계약 일반조건, 공동계약 운영요령",
    ])


def _is_public_material_small_construction_exception_question(q: str) -> bool:
    return (
        any(term in q for term in ("공사용자재", "공사용 자재", "직접구매", "직접 구매", "관급자재"))
        and any(term in q for term in ("소규모공사", "소규모 공사", "제외", "예외", "기준", "얼마"))
    )


def _public_material_small_construction_exception_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **공사용 자재 직접구매 대상에서 제외되는 소규모 공사 기준은 공사 종류별로 다릅니다.**",
        "",
        "| 공사 구분 | 소규모 공사 기준 | 실무 의미 |",
        "|---|---|---|",
        "| 종합공사 | 추정가격 **40억원 미만** | 이 기준 미만이면 공사용 자재 직접구매 의무 예외 검토 |",
        "| 전문공사 등 | 추정가격 **3억원 미만** | 전문공사, 전기공사, 정보통신공사, 소방시설공사 등은 3억원 기준 확인 |",
        "",
        "### 주의할 점",
        "- 이 기준은 `공사용 자재 직접구매 의무 예외` 판단 기준이지, 공사를 나누어 발주해도 된다는 뜻이 아닙니다.",
        "- 공사 추정가격, 직접구매 대상 자재 해당 여부, 자재 금액, 분리 가능성, 공정 지연 위험을 함께 봐야 합니다.",
        "- 기준 이상 공사라도 공정관리상 곤란, 하자 책임 불분명 등 예외 사유가 있으면 별도 검토가 필요합니다.",
        "",
        "근거: 「중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령」 제11조제2항, 공사용 자재 직접구매 대상 품목 지정 고시",
    ])


def _is_regional_bid_no_bid_reannouncement_expand_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역제한", "부산지역제한", "부산 지역 제한", "부산제한"))
        and any(term in q for term in ("무투찰", "유찰", "입찰자없", "투찰없"))
        and any(term in q for term in ("2차공고", "2차 공고", "재공고", "전국", "확대"))
    )


def _regional_bid_no_bid_reannouncement_expand_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 지역제한 입찰이 무투찰로 유찰되었다고 해서 `재공고`에서 바로 전국으로 확대하는 방식은 주의해야 합니다.**",
        "재공고입찰은 원칙적으로 최초 입찰 조건을 변경하지 않는 절차이고, 지역제한을 전국으로 넓히는 것은 참가자격 조건 변경에 해당하므로 신규공고로 정리하는 편이 안전합니다.",
        "",
        "| 선택지 | 처리 방식 |",
        "|---|---|",
        "| 재공고입찰 | 최초 공고의 지역제한·규격·가격 등 주요 조건을 유지 |",
        "| 전국 확대 | 지역제한을 해제하거나 부울경·전국으로 넓히려면 조건 변경 신규공고 검토 |",
        "| 수의계약 전환 | 재공고 이후에도 입찰자가 없고 법정 요건을 충족하는 경우에만 별도 검토 |",
        "| 문서화 | 부산 업체 부재, 가격·규격 적정성, 시장조사, 확대 사유를 결재문서에 첨부 |",
        "",
        "### 실무 순서",
        "1. 최초 공고의 규격, 기초금액, 납기, 면허·실적 제한이 과도했는지 먼저 점검합니다.",
        "2. 단순 홍보 부족이면 같은 조건으로 재공고합니다.",
        "3. 부산 내 적격 업체가 없거나 경쟁성이 없다는 시장조사가 확인되면 지역제한을 완화한 신규공고를 냅니다.",
        "4. 신규공고 시에는 `부산 지역제한 유찰 및 시장조사 결과`를 조건 변경 사유로 남깁니다.",
        "",
        "근거: 「지방계약법 시행령」 제19조제2항, 지방자치단체 입찰 및 계약집행기준의 재공고입찰·입찰참가자격 제한 기준",
    ])


def _is_annual_unit_price_contract_local_share_question(q: str) -> bool:
    return (
        any(term in q for term in ("연간단가", "연간 단가", "단가계약", "단가 계약"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "부산"))
        and any(term in q for term in ("점유율", "높이", "맺는법", "맺는 법", "계약"))
    )


def _annual_unit_price_contract_local_share_answer() -> str:
    general_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    policy_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **특정 품목의 부산 업체 점유율을 높이기 위해 특정 부산 업체와 임의로 연간 단가계약을 맺는 방식은 위험합니다.**",
        "연간 반복 구매 품목은 총수요를 합산해 계약방법을 정하고, 그 안에서 지역제한·MAS·수의계약 특례 같은 적법 경로를 활용해야 합니다.",
        "",
        "| 경로 | 적용 방식 |",
        "|---|---|",
        "| 지역제한경쟁입찰 | 연간 총수요 금액이 지역제한 가능 범위이면 부산광역시 지역제한으로 단가계약 또는 총액계약 검토 |",
        "| MAS/종합쇼핑몰 | 해당 품목이 쇼핑몰에 있으면 납품요구 또는 2단계 경쟁. 지역업체 선택평가항목·납기·A/S로 반영 |",
        f"| 일반 소액 1인 견적 | 연간 총수요가 **{general_one_quote} 이하** 등 요건을 충족할 때만 검토 |",
        f"| 정책기업 특례 | 부산 여성기업·장애인기업·사회적기업 등은 **{policy_one_quote} 이하** 1인 견적 특례 검토 |",
        "",
        "### 실무 설계",
        "- 품목별 연간 예상 수량과 금액을 먼저 산정해 쪼개기 발주 의심을 피합니다.",
        "- 특정 업체명 대신 세부품명, 규격, 납기, A/S, 직접생산확인, 조달등록 여부를 객관 요건으로 둡니다.",
        "- 부산 업체 풀을 넓히려면 지역제한 가능 여부, 조합 추천, MAS 지역업체 평가항목, 소기업·소상공인 제한을 조합합니다.",
        "- 이미 특정 부산 업체를 정해 놓고 연간 단가계약을 설계하면 특혜·부당제한 리스크가 큽니다.",
        "",
        "근거: 「지방계약법 시행령」 제20조ㆍ제25조ㆍ제30조, 지방자치단체 입찰 및 계약집행기준, 물품 다수공급자계약 2단계경쟁 업무처리기준",
    ])


def _is_event_service_local_artist_scope_statement_question(q: str) -> bool:
    return (
        any(term in q for term in ("행사", "공연", "축제"))
        and any(term in q for term in ("부산", "지역예술인", "지역 예술인", "공연기획사", "공연 기획사"))
        and any(term in q for term in ("과업지시서", "문구", "우선고용", "우선 고용", "고용"))
    )


def _event_service_local_artist_scope_statement_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **행사 운영 용역 과업지시서에 부산 지역 예술인·공연기획사 고용을 강제하는 문구는 부당특약 또는 경쟁제한 위험이 있습니다.**",
        "대신 지역문화 이해도, 지역 예술인 협업계획, 현장 운영 대응성처럼 과업 수행과 관련된 요소를 `권장` 또는 `평가항목`으로 설계하는 편이 안전합니다.",
        "",
        "### 권장형 과업지시서 문구 예시",
        "`수행사는 행사 목적과 지역문화 확산 취지를 고려하여 부산 지역 예술인, 공연단체, 현장 운영 인력과의 협업 방안을 제안할 수 있으며, 발주기관은 제안서 평가 시 지역문화 이해도, 현장 대응성, 협업계획의 구체성을 평가할 수 있다.`",
        "",
        "### 피해야 할 문구",
        "`부산 지역 예술인만 고용하여야 한다.`",
        "`공연기획사는 부산 업체여야 한다.`",
        "`부산 업체를 하도급하지 않으면 감점한다.`",
        "",
        "| 대안 | 적용 방식 |",
        "|---|---|",
        "| 지역제한입찰 | 용역 금액과 법령 기준이 맞으면 부산 지역제한 가능성 검토 |",
        "| 협상계약 평가 | 지역문화 이해도, 지역 예술인 협업계획, 현장 운영 능력을 정성평가로 반영 |",
        "| 과업 조건 | 긴급 현장대응, 리허설 참여, 지역 네트워크 활용 등 수행 관련 조건으로 작성 |",
        "",
        "근거: 「지방계약법」 제6조, 「지방계약법 시행령」 제20조, 지방자치단체 입찰 및 계약집행기준의 부당한 특약·입찰참가자격 제한 금지 취지",
    ])


def _is_software_maintenance_resident_staff_question(q: str) -> bool:
    return (
        any(term in q for term in ("소프트웨어", "sw", "시스템", "유지보수"))
        and any(term in q for term in ("상주", "전담인력", "전담 인력", "인력상주", "상주조건"))
        and any(term in q for term in ("부산", "업체", "조건", "넣어도", "가능"))
    )


def _software_maintenance_resident_staff_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **소프트웨어 유지보수 용역에서 전담 인력 상주를 일반 조건으로 요구하는 것은 원칙적으로 신중해야 하며, 보안·장애 대응 등 예외 사유가 있을 때만 최소 범위로 설계해야 합니다.**",
        "부산 소재 업체라는 이유만으로 상주를 요구하면 원격지 개발·유지보수 원칙과 과도한 인력 투입 요구 문제가 생길 수 있습니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 원칙 | 원격지 개발·유지보수와 산출물 중심 관리가 기본 |",
        "| 상주 가능 사유 | 폐쇄망, 중요정보 처리, 즉시 장애복구, 물리적 장비 접근 등 객관적 필요가 있는 경우 |",
        "| 문구 설계 | `상주 1명 필수`보다 장애 대응시간, 보안 준수, 정기점검, 긴급출동 SLA로 표현 |",
        "| 지역업체 고려 | 부산 현장 대응 가능성은 평가요소가 될 수 있지만 상주 강제의 단독 근거는 아님 |",
        "",
        "### 권장 문구",
        "`수행사는 원격 유지보수를 원칙으로 하되, 보안상 필요하거나 중대 장애 발생 시 발주기관이 요청하는 경우 정해진 시간 내 현장 대응이 가능한 지원체계를 제시하여야 한다.`",
        "",
        "### 상주가 필요한 경우 남길 자료",
        "- 폐쇄망·보안구역 운영 여부, 개인정보·중요정보 처리 범위.",
        "- 장애 발생 시 업무 중단 손실과 목표 복구시간.",
        "- 원격 유지보수로 대체하기 어려운 장비 접근·현장 점검 필요성.",
        "- 상주 기간, 인원, 장소, 업무 범위를 최소화한 산출근거.",
        "",
        "근거: 「소프트웨어 진흥법」, 「소프트웨어사업 계약 및 관리감독에 관한 지침」의 원격지 개발·과업관리 취지, 「지방계약법」의 부당한 특약 금지 원칙",
    ])


def _is_local_product_purchase_goal_calculation_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역제품", "지역 제품", "지역상품", "지역 상품"))
        and any(term in q for term in ("구매목표", "구매 목표", "목표제", "비율", "계산"))
        and any(term in q for term in ("부서", "사업", "적용", "부산"))
    )


def _local_product_purchase_goal_calculation_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **지역 제품 구매 목표제는 계약방법을 바꾸는 규정이 아니라 부서별 구매실적을 관리하는 내부 성과관리 기준으로 봐야 합니다.**",
        "계산은 보통 `대상 구매예산 또는 구매실적 × 당해 연도 목표비율` 구조로 잡고, 제외대상과 실적인정 기준은 부산시 지침을 확인합니다.",
        "",
        "| 단계 | 계산 방법 |",
        "|---|---|",
        "| 1. 대상 예산 산정 | 부서 사업 중 물품·용역·공사 구매성 예산을 추려 대상 예산을 확정 |",
        "| 2. 제외대상 차감 | 인건비, 보조금, 법정경비, 타 지역 공급 불가 품목 등 내부 지침상 제외대상 차감 |",
        "| 3. 목표액 산정 | 대상 예산 × 당해 연도 지역상품 구매 목표비율 |",
        "| 4. 실적 집계 | 계약상대자 본점 소재지, 납품업체, 제품 생산지 등 지침상 인정 기준으로 집계 |",
        "| 5. 부족분 관리 | 남은 구매계획에서 지역제한, MAS 부산업체 후보, 정책기업, 인증제품 경로를 검토 |",
        "",
        "### 주의할 점",
        "- 목표제는 `부산 업체를 무조건 지정하라`는 의미가 아닙니다.",
        "- 실제 계약은 지방계약법의 수의계약, 지역제한, MAS, 적격심사·평가항목 범위 안에서 설계해야 합니다.",
        "- 목표비율과 제외대상은 해마다 바뀔 수 있으므로 당해 연도 부산시 지역상품 우선구매 지침 또는 성과관리 기준을 확인합니다.",
        "",
        "근거: 「부산광역시 지역상품 우선구매에 관한 조례」, 부산시 지역업체·지역상품 구매촉진 지침, 「지방계약법」 제6조",
    ])


def _is_public_contract_monitoring_local_purchase_ratio_question(q: str) -> bool:
    return (
        any(term in q for term in ("공공계약모니터링", "공공계약 모니터링", "모니터링시스템", "모니터링 시스템"))
        and any(term in q for term in ("지역업체", "지역 업체", "구매비중", "구매 비중", "구매율", "실적"))
        and any(term in q for term in ("확인", "조회", "보는법", "보는 법", "우리부서", "우리 부서"))
    )


def _public_contract_monitoring_local_purchase_ratio_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산시 공공계약 모니터링 시스템에서는 통계·실적 조회 메뉴에서 부서, 기간, 계약유형을 지정해 지역업체 구매 비중을 확인하는 흐름으로 보면 됩니다.**",
        "정확한 메뉴명은 기관 내부 시스템 버전에 따라 다를 수 있으므로, 조회 권한과 지표 정의는 회계부서 또는 계약부서에 확인해야 합니다.",
        "",
        "### 조회 순서",
        "1. 공공계약 모니터링 시스템에 접속해 계약/구매 실적 조회 권한으로 로그인합니다.",
        "2. `통계`, `실적조회`, `부서별 구매현황`, `지역업체 구매율`과 유사한 메뉴를 엽니다.",
        "3. 조회기간을 회계연도, 분기, 월 단위로 설정합니다.",
        "4. 부서를 선택하고 계약유형을 물품·용역·공사 또는 전체로 설정합니다.",
        "5. 지역 기준을 `부산광역시`, `지역업체`, `본점 소재지` 등 시스템 정의에 맞춰 선택합니다.",
        "6. 총 계약금액, 지역업체 계약금액, 지역업체 구매비율, 제외대상 금액을 확인합니다.",
        "",
        "### 확인할 지표",
        "- 분모: 총 구매액인지, 제외대상을 뺀 대상 구매액인지.",
        "- 분자: 계약상대자 본점 소재지 기준인지, 납품업체·생산지 기준인지.",
        "- 기준일: 계약일, 납품일, 대금지급일 중 무엇을 실적일로 보는지.",
        "- 누락 건: 수기계약, 조달청 납품요구, 변경계약이 반영됐는지.",
        "",
        "근거: 부산시 지역상품 우선구매 실적관리 체계, 부서별 계약실적 통계, 기관 회계·계약부서 내부 운영 기준",
    ])


def _is_local_purchase_performance_branch_or_dealer_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역업체", "지역 업체", "지역실적", "지역 실적", "구매실적", "구매 실적"))
        and any(term in q for term in ("지사", "지점", "대리점", "납품", "타시도", "타 시도", "본점"))
        and any(term in q for term in ("인정", "포함", "삭제", "보고", "실적"))
    )


def _local_purchase_performance_branch_or_dealer_answer(q: str) -> str:
    is_dealer = any(term in q for term in ("대리점", "납품", "타시도", "타 시도"))
    if is_dealer:
        first = "결론부터 말하면, **타 시도 업체와 계약했다면 실제 물건을 부산 대리점에서 납품받았더라도 원칙적으로 부산 지역업체 실적으로 인정하기 어렵습니다.**"
    else:
        first = "결론부터 말하면, **부산에 지사·지점만 있고 본점이 타 시도인 업체는 원칙적으로 부산 지역업체 구매실적에서 제외하는 것이 안전합니다.**"
    return "\n".join([
        first,
        "지역업체 실적은 보통 계약상대자의 사업자등록증 또는 법인등기부상 본점 소재지를 기준으로 집계합니다.",
        "",
        "| 상황 | 실적 판단 |",
        "|---|---|",
        "| 본점이 부산 | 부산 지역업체 실적 인정 가능 |",
        "| 부산 지사·지점만 있음 | 원칙적으로 부산 지역업체 실적 인정 어려움 |",
        "| 타 시도 본점 업체와 계약, 부산 대리점 납품 | 계약상대자 기준이면 원칙적으로 인정 어려움 |",
        "| 예외 가능성 | 해당 연도 성과평가 매뉴얼이 납품업체·생산지 기준을 별도로 인정하는 경우만 확인 |",
        "",
        "### 실무 처리",
        "- 실적 보고 전에 계약상대자의 사업자등록증, 법인등기부등본, 본점 소재지를 확인합니다.",
        "- 지사·대리점 납품 건은 별도 비고로 관리하되, 지역업체 실적 분자에 포함할지는 평가 매뉴얼과 회계·계약부서 확인을 거칩니다.",
        "- 잘못 포함된 건은 정정 대상 목록으로 분리하고, 향후 공고·계약 단계에서 부산 본점 업체 여부를 후보표에 표시합니다.",
        "",
        "근거: 부산시 지역업체 구매실적 관리 기준, 부서별 성과평가 매뉴얼, 계약상대자 본점 소재지 기준의 지역업체 판단 관행",
    ])


def _is_local_vendor_direct_contract_reason_template_question(q: str) -> bool:
    return (
        any(term in q for term in ("수의계약사유서", "수의계약 사유서", "사유서", "품의서", "기안"))
        and any(term in q for term in ("지역업체", "지역 업체", "부산업체", "부산 업체", "구매확대", "구매 확대"))
        and any(term in q for term in ("모범사례", "모범 사례", "예시", "문구", "작성"))
    )


def _local_vendor_direct_contract_reason_template_answer() -> str:
    general_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "2천만원"
    policy_one_quote = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "5천만원"
    return "\n".join([
        "결론부터 말하면, **`부산 지역업체 구매 확대`만으로는 수의계약 사유서의 법정 사유가 될 수 없습니다.**",
        "사유서에는 먼저 지방계약법상 수의계약 근거를 적고, 부산 지역업체 활용은 보조 사유로 붙여야 합니다.",
        "",
        "| 구분 | 작성 기준 |",
        "|---|---|",
        f"| 일반 소액 1인 견적 | 추정가격 **{general_one_quote} 이하** 등 법정 요건을 먼저 기재 |",
        f"| 정책기업 특례 | 여성기업·장애인기업·사회적기업·청년창업기업 등은 **{policy_one_quote} 이하** 특례 근거와 확인서 기재 |",
        "| 인증·특수사유 | 우수조달, 혁신제품, 특허·신기술, 긴급 등 해당 조항과 증빙 기재 |",
        "| 지역업체 문구 | 법정 사유 뒤에 지역경제 활성화와 현장 대응성 보조 사유로 기재 |",
        "",
        "### 품의서 문구 예시",
        "`본 건은 추정가격 ○○원으로 「지방계약법 시행령」 제25조제1항제○호 및 제30조에 따른 수의계약 요건을 충족합니다. 계약상대자는 ○○ 확인서/인증서/면허 등 계약 목적 수행에 필요한 자격을 보유하고 있으며, 가격조사 결과 예정가격 범위 내로 가격 적정성이 확인되었습니다. 아울러 해당 업체는 부산광역시에 본점을 둔 지역업체로서 납기, 하자보수, 긴급 현장 대응 측면에서 계약 이행 안정성이 있어 지역경제 활성화 취지에도 부합합니다.`",
        "",
        "### 첨부자료",
        "- 수의계약 근거 조항, 추정가격 산출자료, 비교견적 또는 가격조사표.",
        "- 정책기업·인증제품·면허·직접생산확인 등 해당 증빙.",
        "- 부산 본점 소재지 확인자료와 납기·A/S·현장대응 가능성 자료.",
        "",
        "근거: 「지방계약법 시행령」 제25조ㆍ제30조, 지방자치단체 입찰 및 계약집행기준 수의계약 운영요령, 부산시 지역상품 우선구매 취지",
    ])


def _is_active_administration_audit_defense_question(q: str) -> bool:
    return (
        any(term in q for term in ("적극행정", "면책", "사전컨설팅", "감사리스크", "감사 리스크"))
        and any(term in q for term in ("부산업체", "부산 업체", "지역업체", "제품", "구매"))
    )


def _active_administration_audit_defense_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **적극행정 면책은 부산 업체 제품 구매를 사후에 정당화하는 자동 방패가 아닙니다.**",
        "계약 전에 공익성, 법령 범위 내 판단, 사적 이해관계 부재, 가격 적정성, 대안 검토를 문서화하고 필요하면 사전컨설팅 감사나 적극행정위원회 심의를 거치는 것이 핵심입니다.",
        "",
        "| 대응 요소 | 준비 자료 |",
        "|---|---|",
        "| 공공의 이익 | 지역경제 활성화, 신속한 장애 대응, 공공서비스 품질 개선 등 구체적 효과 |",
        "| 법령 준수 | 수의계약·지역제한·MAS·평가항목이 지방계약법 범위 안인지 검토 |",
        "| 사적 이해관계 부재 | 담당자·업체 이해관계 확인, 수의계약 체결 제한 여부 확인서 |",
        "| 가격 적정성 | 비교견적, 조달단가, 시장조사, 총비용 분석 |",
        "| 사전 절차 | 사전컨설팅 감사, 적극행정위원회, 계약심사·일상감사 의견 |",
        "",
        "### 실무 처리",
        "- 애매한 사안이면 계약 체결 전 사전컨설팅 감사를 신청해 판단 근거를 확보합니다.",
        "- 적극행정위원회 심의가 가능한 기관이면 지역업체 구매 필요성과 법령상 허용 범위를 안건으로 올립니다.",
        "- 특정 업체를 위한 조건처럼 보이지 않도록 대안 비교표와 후보군 검토표를 남깁니다.",
        "- 면책은 위법을 허용하는 제도가 아니므로, 금액 쪼개기·특정업체 지정·가격 부풀리기는 방어되지 않습니다.",
        "",
        "근거: 적극행정 운영규정, 지방자치단체 사전컨설팅감사 제도, 「지방계약법」 제6조 및 수의계약·지역제한 관련 규정",
    ])


def _is_local_purchase_award_evidence_question(q: str) -> bool:
    return (
        any(term in q for term in ("포상", "우수공무원", "우수 공무원", "표창"))
        and any(term in q for term in ("지역업체", "지역 업체", "부산", "구매실적", "구매 실적"))
        and any(term in q for term in ("증빙", "자료", "신청", "기준"))
    )


def _local_purchase_award_evidence_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **부산 지역업체 구매 실적 우수 공무원 포상 기준은 법령 고정값이 아니라 당해 연도 포상계획 공문과 내부 평가기준을 확인해야 합니다.**",
        "증빙은 개별 계약서류보다 시스템 실적과 정정자료를 우선으로 준비하는 편이 효율적입니다.",
        "",
        "| 확인 항목 | 준비 자료 |",
        "|---|---|",
        "| 포상 기준 | 당해 연도 포상계획, 부서별 평가표, 가점·감점 기준 |",
        "| 구매 실적 | e호조, 공공계약 모니터링 시스템, 나라장터 납품요구 내역 |",
        "| 지역업체 증빙 | 계약상대자 사업자등록증, 본점 소재지, 지역업체 인정 기준 |",
        "| 우수 사례 | 지역제한, MAS 부산업체 활용, 정책기업·인증제품 발굴, 예산 절감 자료 |",
        "| 검증 자료 | 실적 제외대상, 오집계 정정표, 회계·계약부서 확인 의견 |",
        "",
        "### 신청 순서",
        "1. 회계부서 또는 지역경제 담당 부서에서 당해 연도 포상계획 공문을 확인합니다.",
        "2. 시스템에서 부서·개인별 지역업체 구매 실적을 추출합니다.",
        "3. 본점 소재지 기준으로 지역업체 실적을 검증하고 오집계를 정정합니다.",
        "4. 정량실적과 함께 지역업체 발굴 노력, 합법적 계약설계, 예산 절감 사례를 요약합니다.",
        "",
        "근거: 당해 연도 부산시·기관 포상계획, 지역업체 구매실적 관리 기준, e호조·공공계약 모니터링 시스템 실적자료",
    ])


def _is_chatbot_recommended_paper_company_responsibility_question(q: str) -> bool:
    return (
        any(term in q for term in ("챗봇", "추천"))
        and any(term in q for term in ("페이퍼컴퍼니", "페이퍼 컴퍼니", "부적격", "허위업체"))
        and any(term in q for term in ("책임", "담당자", "범위", "징계", "변상"))
    )


def _chatbot_recommended_paper_company_responsibility_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **챗봇이 부산 업체를 추천했다는 사정은 담당자의 적격성 확인 의무를 면제하지 않습니다.**",
        "실제 업체가 페이퍼 컴퍼니이거나 부적격 업체인데 확인 없이 계약했다면, 담당자에게 징계·주의·변상 책임이 문제 될 수 있습니다.",
        "",
        "| 확인 의무 | 체크 자료 |",
        "|---|---|",
        "| 업체 실재성 | 사업자등록, 법인등기, 본점 소재지, 사무실·연락처, 실제 영업 여부 |",
        "| 계약 적격성 | 면허·허가, 직접생산확인, 중소기업·정책기업 확인서, 조달등록 상태 |",
        "| 수행 능력 | 납품실적, 기술인력, 장비, 재무상태, 하자·A/S 체계 |",
        "| 제재·제한 | 부정당업자 제재, 수의계약 체결 제한 여부 확인서, 이해관계 여부 |",
        "| 가격 적정성 | 비교견적, 시장가격, 조달단가, 원가자료 |",
        "",
        "### 실무 대응",
        "- 챗봇 추천 결과는 시장조사 보조자료로만 쓰고, 계약 전에는 공적 증빙으로 재확인합니다.",
        "- 계약서류에 `챗봇 추천`을 근거로 쓰지 말고, 법정 자격·가격·수행능력 확인 결과를 근거로 씁니다.",
        "- 페이퍼 컴퍼니 의심이 있으면 계약 전 후보에서 제외하거나 회계·감사·법무 부서 검토를 받습니다.",
        "",
        "근거: 「지방공무원법」 제48조 성실의 의무, 「회계관계직원 등의 책임에 관한 법률」 제4조, 선량한 관리자의 주의의무, 지방계약 수의계약 체결 제한 확인 절차",
    ])


def _is_busan_local_purchase_guideline_pdf_question(q: str) -> bool:
    return (
        any(term in q for term in ("pdf", "파일", "자료", "가이드라인", "최신판"))
        and any(term in q for term in ("부산시", "부산광역시", "부산"))
        and any(term in q for term in ("지역업체", "지역 업체", "지역상품", "구매가이드", "구매 가이드"))
        and any(term in q for term in ("볼수", "볼 수", "보여", "다운", "찾"))
    )


def _busan_local_purchase_guideline_pdf_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **제가 이 답변 안에서 부산시 최신 PDF 파일을 직접 첨부해 보여주지는 못합니다.**",
        "다만 최신판은 부산광역시 공식 홈페이지나 내부 행정망의 공문·자료실에서 확인하는 것이 가장 안전합니다.",
        "",
        "### 공식 확인 경로",
        "1. 부산광역시청 공식 홈페이지(https://www.busan.go.kr)에 접속합니다.",
        "2. 통합검색에서 `지역업체 구매`, `지역상품 우선구매`, `지역 업체 구매 가이드라인`, `지역상품 구매촉진`을 검색합니다.",
        "3. `고시공고`, `공지사항`, `자료실`, `회계재산담당관`, `경제정책` 관련 게시판을 확인합니다.",
        "4. 검색 결과의 첨부파일명, 작성부서, 작성일을 확인해 최신본인지 봅니다.",
        "5. 내부 적용 지침은 온나라/새올 등 내부 공문함에서 같은 키워드로 추가 확인합니다.",
        "",
        "### 확인할 내용",
        "- 발간연도와 적용기간.",
        "- 지역업체 인정 기준: 본점 소재지, 지사 포함 여부, 생산지 기준 여부.",
        "- 실적 집계 기준: 계약일, 납품일, 대금지급일, 제외대상.",
        "- 계약방법별 권장사항: 수의계약, 지역제한, MAS, 정책기업, 인증제품.",
        "",
        "공식 출처가 확인되지 않은 PDF를 기준으로 계약 판단을 확정하지 말고, 회계·계약부서가 배포한 최신 공문 또는 부산시 홈페이지 게시본을 기준으로 삼으세요.",
    ])


def _is_procurement_api_credit_check_question(q: str) -> bool:
    return (
        any(term in q for term in ("공공조달api", "공공조달 api", "조달api", "조달 api", "api"))
        and any(term in q for term in ("신용도", "신용", "신용평가", "신용등급"))
        and any(term in q for term in ("부산업체", "부산 업체", "실시간", "체크", "조회"))
    )


def _procurement_api_credit_check_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **공공조달 API만으로 부산 업체의 신용도나 신용등급을 실시간 조회하는 것은 원칙적으로 어렵습니다.**",
        "업체 신용정보는 신용정보 보호와 이용 목적 제한이 적용되는 정보라 공개 API로 자유 조회하는 데이터로 보기 어렵습니다.",
        "",
        "| 확인 대상 | 가능한 경로 |",
        "|---|---|",
        "| 조달 등록·계약 정보 | 공공조달/나라장터 공개 API, 종합쇼핑몰, 입찰참가자격 정보 |",
        "| 신용평가등급 | 입찰·계약 과정에서 업체가 제출한 신용평가등급 확인서 또는 나라장터 내부 심사자료 |",
        "| 부정당 제재 | 나라장터·조달청 공개 제재 정보 또는 내부 조회 |",
        "| 재무·휴폐업 | 국세청·공공데이터 공개 범위, 사업자 상태 조회 등 제한적 확인 |",
        "",
        "### 실무 처리",
        "- API는 후보 업체의 조달등록, 계약이력, 품목, 지역, 제재정보 등 공개 가능한 범위의 스크리닝에 사용합니다.",
        "- 신용도는 계약공고에서 요구한 신용평가등급 확인서, 적격심사 자료, 경영상태 평가자료로 확인합니다.",
        "- 챗봇 화면에는 `신용도 실시간 조회`라고 표시하지 말고 `신용평가 자료 제출 필요` 또는 `계약담당자 내부 확인 필요`로 표시하는 편이 안전합니다.",
        "",
        "근거: 「신용정보의 이용 및 보호에 관한 법률」, 나라장터 입찰참가자격·적격심사 자료 제출 체계, 공공데이터 제공 범위",
    ])


def _is_low_local_purchase_ratio_penalty_question(q: str) -> bool:
    return (
        any(term in q for term in ("구매비중", "구매 비중", "구매율", "지역업체", "지역 업체"))
        and any(term in q for term in ("낮은", "낮", "부서"))
        and any(term in q for term in ("불이익", "불기익", "패널티", "제재", "규정"))
    )


def _low_local_purchase_ratio_penalty_answer() -> str:
    return "\n".join([
        "결론부터 말하면, **지역 업체 구매 비중이 낮다는 이유만으로 지방계약법령상 직접 과태료나 계약상 제재가 부과되는 구조는 아닙니다.**",
        "다만 부산시나 기관 내부 성과평가, 부서평가, 행정사무감사, 감사 지적에서 불이익 또는 개선 요구가 생길 수 있습니다.",
        "",
        "| 구분 | 가능성 |",
        "|---|---|",
        "| 지방계약법상 직접 패널티 | 일반적으로 없음. 계약은 공정성·경쟁성·경제성이 우선 |",
        "| 내부 성과평가 | BSC, 부서평가, 구매목표 달성률 지표와 연계 가능 |",
        "| 감사·의회 지적 | 지역업체 구매 확대 지침 미이행, 실적 부진 사유 미관리로 지적 가능 |",
        "| 포상·인센티브 | 우수 부서·공무원 포상, 가점, 예산·평가상 인센티브 가능 |",
        "",
        "### 실무 대응",
        "- 낮은 실적 자체보다 `왜 낮았는지`와 `개선 계획이 있는지`를 문서화합니다.",
        "- 해당 품목에 부산 업체가 없었는지, MAS 등록업체가 없었는지, 법령상 지역제한이 불가능했는지 시장조사 자료를 남깁니다.",
        "- 다음 발주에서는 지역제한 가능성, 정책기업·인증제품, MAS 부산 후보, 평가항목 반영 가능성을 사전 검토합니다.",
        "",
        "근거: 부산시 지역상품 우선구매 조례·지침, 기관 BSC·부서평가 운영기준, 행정사무감사 및 내부감사 운영 기준",
    ])


def _is_regional_mandatory_joint_contract(q: str) -> bool:
    if (
        any(term in q for term in ("지역제한", "적격심사"))
        and any(term in q for term in ("연결", "높이", "어떻게"))
    ):
        return False
    return (
        ("지역의무" in q or "의무공동" in q or ("공동도급" in q and "지역" in q))
        and any(term in q for term in ("기준", "비율", "몇", "가능", "공사", "발주", "공동도급"))
    )


def _is_regional_mandatory_joint_contract_invalid_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역의무", "의무공동", "지역업체의무", "지역업체참여"))
        and any(term in q for term in ("공동도급", "컨소시엄", "공동수급"))
        and any(term in q for term in ("무효", "탈락", "미충족", "안맺", "안맺으면", "구성하지않"))
    )


def _regional_mandatory_joint_contract_invalid_answer() -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    return "\n".join([
        "### 지역의무 공동도급 미충족 시 입찰 효력",
        "- 결론부터 보면, **공고문에 지역의무 공동도급이 입찰참가 조건으로 명시되어 있는데 이를 충족하지 않으면 입찰 무효 또는 부적격 처리 대상입니다.**",
        "- 타 지역 업체가 부산 업체와 공동수급체를 구성하지 않거나, 공고된 지역업체 최소 시공참여비율을 맞추지 못하면 공동수급체 구성 요건을 충족하지 못한 것입니다.",
        "",
        "| 확인 항목 | 실무 판단 |",
        "|---|---|",
        f"| 지역업체 참여비율 | 원칙 {min_share}, 필요 시 {max_share} 이하 범위에서 공고 가능 |",
        "| 공동수급협정서 | 입찰참가신청 또는 공고에서 정한 제출기한까지 제출 여부 확인 |",
        "| 입찰무효 판단 | 공고문, 공동계약 운영요령, 입찰유의서의 무효·부적격 조항과 연결 |",
        "",
        "### 공고문 작성 포인트",
        "- `지역업체 최소 시공참여비율`, `공동수급체 구성 방식`, `공동수급협정서 제출기한`, `미제출 또는 비율 미달 시 입찰무효/부적격`을 명확히 적어야 합니다.",
        "- 단순 하도급 약속이나 자재 납품 약속은 지역의무 공동도급의 지역업체 참여비율을 충족한 것으로 보지 않는 편이 안전합니다.",
        "",
        "근거: 「지방계약법 시행령」 제88조, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령",
    ])


def _is_regional_mandatory_point_exclusion_question(q: str) -> bool:
    return (
        any(term in q for term in ("지역의무", "의무공동", "지역업체의무"))
        and any(term in q for term in ("적격심사", "가점", "참여도", "점수", "산정"))
        and any(term in q for term in ("지분율", "참여비율", "부산업체", "지역업체"))
    )


def _regional_mandatory_point_exclusion_answer() -> str:
    return "\n".join([
        "### 지역의무 공동도급과 적격심사 지역업체 가산평가",
        "- 결론부터 보면, **지역의무 공동도급 입찰공사는 적격심사의 지역업체 가산평가 적용대상에서 제외되는 구조를 먼저 확인해야 합니다.**",
        "- 즉, 지역의무 공동도급의 부산업체 지분율은 보통 `가점 산정용 점수`가 아니라 `입찰참가 또는 공동수급체 구성 요건`으로 봐야 합니다.",
        "",
        "| 구분 | 실무 판단 |",
        "|---|---|",
        "| 지역의무 공동도급 | 공고문에 정한 지역업체 최소 시공참여비율 충족 여부를 확인 |",
        "| 적격심사 지역업체 가산평가 | 지역의무 공동도급 입찰공사는 제외 대상인지 먼저 확인 |",
        "| 지분율 미달 | 가점을 덜 받는 문제가 아니라 공동수급체 요건 미충족·부적격 문제가 될 수 있음 |",
        "",
        "### 주의",
        "- 지역업체 참여도 가산평가는 공사 종류, 낙찰자 결정기준, 지역제한 여부, 지역의무 공동도급 여부에 따라 적용 제외가 달라집니다.",
        "- 공고문에는 `지역의무 공동도급 비율`과 `적격심사 지역업체 가산평가 적용 여부`를 따로 명시해야 혼선이 줄어듭니다.",
        "",
        "근거: 「지방자치단체 입찰시 낙찰자 결정기준」의 지역업체 가산평가 적용제외, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령",
    ])


def _is_regional_mandatory_joint_contract_share_question(q: str) -> bool:
    return (
        any(term in q for term in ("의무참여비율", "참여비율", "49%", "사십구"))
        and any(term in q for term in ("부산업체", "지역업체", "지역"))
        and any(term in q for term in ("공사", "종합공사", "전문공사"))
        and any(term in q for term in ("근거", "설정", "가능", "수있"))
    )


def _regional_mandatory_joint_contract_share_answer(q: str) -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    min_company_count = _num("P_LOCAL_JOINT_CONTRACT_MIN_QUALIFIED_COMPANY_COUNT")
    local_general = _money_limit("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    amount = _extract_amount_won(q)
    amount_label = _format_won(amount) if amount is not None else "질문 금액"
    regional_limit_note = []
    if "종합공사" in q and amount is not None:
        regional_limit_note = [
            "",
            "### 지역제한과 혼동하면 안 되는 부분",
            f"- {amount_label} 종합공사는 지방계약 종합공사 지역제한 기준 **{local_general}**을 넘을 수 있으므로, `부산 업체만 입찰`로 제한하는 지역제한과는 분리해서 봐야 합니다.",
            "- 지역의무 공동도급은 부산 업체를 공동수급체 구성원으로 참여시키는 장치이고, 지역제한은 입찰참가자 전체를 부산 업체로 제한하는 장치입니다.",
        ]
    return "\n".join([
        f"### {amount_label} 공사의 부산 업체 의무 참여비율 49% 근거",
        f"- 결론부터 보면, **지역의무 공동도급에서 지역업체 최소 시공참여비율은 원칙 {min_share}이고, 지역경제 활성화 필요성이 있으면 {max_share} 이하 범위에서 정할 수 있습니다.**",
        "- 따라서 49%라는 숫자는 `부산 업체만 입찰`시키는 근거가 아니라, 공동수급체 안에서 부산 지역업체가 실제 시공에 참여해야 하는 비율을 정하는 근거로 보아야 합니다.",
        "",
        "| 항목 | 기준 |",
        "|---|---|",
        f"| 법령 근거 | 「지방계약법 시행령」 제88조, 특히 지역업체 참여비율을 정할 수 있다는 제6항 구조 |",
        f"| 예규 근거 | 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령의 {min_share} 원칙 및 {max_share} 상한 |",
        f"| 제한 사유 | 참여비율을 충족할 지역업체 또는 면허 보유 지역업체가 {min_company_count} 미만이면 조정·배제 검토 |",
        "| 문서화 | 공고문에 공동계약 방식, 지역업체 참여비율, 협정서 제출기한, 미충족 시 처리 기준 명시 |",
        *regional_limit_note,
        "",
        "### 실무 결론",
        "- 49% 설정은 가능성을 검토할 수 있지만, 자동으로 넣는 숫자는 아닙니다. 부산 지역업체 수, 면허·시공능력, 공정별 수행 가능성, 품질 저하 우려를 시장조사로 확인한 뒤 정해야 합니다.",
        "- 공고문에는 `부산업체 의무 참여`라는 표현만 쓰지 말고 `지역의무 공동도급`, `최소 시공참여비율`, `공동수급협정서` 요건을 함께 적는 편이 안전합니다.",
    ])


def _is_mas_regional_review(q: str) -> bool:
    has_mas = any(term in q for term in ("mas", "종합쇼핑몰", "다수공급자", "제3자단가", "3자단가"))
    has_region = any(term in q for term in ("지역업체", "부산업체", "부산", "지역", "우대", "가점"))
    has_review = any(term in q for term in ("2단계", "경쟁", "우대", "가점", "고려", "활용", "가능", "살수", "구매"))
    return has_mas and has_region and has_review


def _is_excellent_procurement_or_third_party(q: str) -> bool:
    if "소프트웨어" in q:
        return False
    return (
        any(term in q for term in ("우수조달", "제3자단가", "3자단가", "제3자를위한단가"))
        and any(term in q for term in ("부산", "지역상품", "지역업체", "활용", "도움", "구매"))
    )


def _is_innovation_product_purchase_review(q: str) -> bool:
    return (
        any(term in q for term in ("혁신제품", "혁신시제품", "혁신장터", "기술개발제품", "우수조달", "성능인증", "gs인증", "nep", "net"))
        and any(term in q for term in ("수의계약", "우선구매", "검토", "구매"))
        and not any(term in q for term in ("후보", "추천", "찾아", "검색"))
    )


def _innovation_product_purchase_review_answer() -> str:
    return "\n".join([
        "혁신제품·혁신시제품·기술개발제품은 **수의계약 근거**와 **우선구매 근거**를 분리해서 봐야 합니다.",
        "결론부터 보면, **「조달사업법」 제27조제1항에 따라 지정된 혁신제품을 구매하려는 경우에는 일반 소액수의 한도와 별개로 1인 견적 수의계약을 검토할 수 있습니다.**",
        "지방계약 기준에서는 현행 「지방계약법 시행령」 제25조제1항제8호다목이 혁신제품 구매 수의계약 사유이고, 제30조제1항제1호가 제25조제1항 각 호 중 제5호를 제외한 계약에 대해 1인 견적을 허용하는 연결 조항입니다.",
        "따라서 `금액만으로 배제하지 않는다`가 원칙이지만, 지정·인증 상태가 맞는지 확인하지 않고 성급하게 계약 결론을 내리면 감사 리스크가 큽니다.",
        "",
        "### 1. 수의계약과 우선구매의 차이",
        "| 구분 | 수의계약 | 우선구매 |",
        "|---|---|---|",
        "| 법적 성격 | 경쟁입찰 예외로 특정 제품·업체와 계약할 수 있는 **계약방법** | 공공기관이 일정 제품군 구매를 우선 검토·관리하는 **구매목표·정책수단** |",
        "| 판단 질문 | `이 제품을 경쟁 없이 계약방법으로 선택할 수 있는가` | `이 제품 구매가 기관의 우선구매 실적·정책목표에 들어가는가` |",
        "| 주요 근거 | 지방자치단체는 「지방계약법 시행령」 제25조제1항제8호다목 및 제30조제1항제1호, 국가기관은 「국가계약법 시행령」의 혁신제품 수의계약 근거, 공기업·준정부기관은 「공기업·준정부기관 계약사무규칙」과 준용 규정 | 「조달사업법」의 혁신제품 제도, 「중소기업제품 구매촉진 및 판로지원에 관한 법률」 및 기술개발제품 우선구매 관련 고시·운영규정 |",
        "| 금액 판단 | 해당 수의계약 사유가 성립하면 일반 소액수의 한도만으로 배제하지 않음. 다만 기관 내부심사·감사 소명은 별도 필요 | 금액보다 지정·인증 지위, 구매실적 인정 범위, 해당 연도 목표비율·관리기준을 확인 |",
        "",
        "### 2. 제품 유형별 확인 로직",
        "| 제품 유형 | 수의계약 검토 포인트 | 우선구매 검토 포인트 |",
        "|---|---|---|",
        "| 혁신제품 | 「조달사업법」 제27조제1항 지정 여부, 지정 유효기간, 혁신장터·조달계약 등록, 제품명·모델명·규격 일치 확인 | 혁신제품 구매실적, 시범구매·혁신조달 정책과 연결되는지 확인 |",
        "| 혁신시제품 | 현재 제도상 혁신제품으로 전환·지정되었는지, 시범구매계약 특수조건이 붙는지 확인 | 시범구매 단계인지, 실증·성과관리 조건이 있는지 확인 |",
        "| 기술개발제품 | 성능인증, 우수조달, NEP, NET, GS 등 해당 인증이 수의계약 사유와 연결되는지 확인 | 기술개발제품 우선구매 대상인지, 인증 유효기간과 제품 범위가 맞는지 확인 |",
        "",
        "### 3. 금액 질문에 대한 실무 답",
        "- 결론은 `법령상 일반 소액수의 한도와 별개로 1인 견적 수의계약 검토가 가능하다`입니다. 혁신제품 특례는 2천만원·5천만원 같은 일반 1인 견적 금액 기준과 다른 축의 수의계약 사유입니다.",
        "- 다만 `혁신제품이라는 명칭`, `GS·NEP·NET 같은 인증명`, `부산업체 제품`이라는 이유만으로 충분하지 않습니다. **지정·인증 유효성, 제품명·모델명·규격 일치, 조달등록 상태, 직접생산확인 필요 여부, 기관 적용 법령**을 같이 봐야 합니다.",
        "- 고액 계약이면 법령상 금액 한도와 별도로 자체 계약심사, 계약심의위원회, 예산·투자심사, 가격 적정성 검토 같은 내부 통제 장치가 작동할 수 있습니다.",
        "- 수의계약 사유서에는 `왜 이 지정 제품이어야 하는지`, `혁신제품 지정 범위와 구매 규격이 일치하는지`, `경쟁입찰보다 이 경로가 적정한 이유`, `가격 적정성 검토`를 남기는 것이 안전합니다.",
        "",
        "### 4. 기술적 체크포인트",
        "- 계약체결일 기준으로 혁신제품 지정 유효기간이 살아 있는지 확인합니다.",
        "- 혁신장터·나라장터·G2B에 표시된 제품명, 물품식별번호, 모델명, 규격이 실제 구매 규격서와 일치하는지 대조합니다.",
        "- 혁신장터와 나라장터 데이터가 다르게 보이면 조달청 지정공고, 혁신장터 상세화면, 나라장터 계약·쇼핑몰 등록정보를 모두 캡처해 근거 파일로 남깁니다.",
        "- 중소기업자간 경쟁제품 또는 직접생산확인 대상이면 직접생산확인증명서와 실제 제조·공급 주체를 별도로 확인합니다.",
        "",
        "### 5. 부산업체 지원과 연결할 때",
        "- 부산업체 제품이라면 지역상품 구매지원 취지와 연결할 수 있지만, 계약 명분은 `부산 소재`가 아니라 **혁신제품·기술개발제품 지정 또는 인증에 따른 법정 특례**로 세워야 합니다.",
        "- 후속으로 품목이 정해지면 부산 업체 DB에서 혁신제품, 기술개발제품, 우수조달, 종합쇼핑몰 등록, 직접생산확인 여부를 함께 조회해 후보표로 붙이는 방식이 실무적으로 가장 좋습니다.",
        "",
        "정리하면, **혁신제품은 금액만으로 배제하지 않고 1인 견적 수의계약을 검토할 수 있지만, 법적 근거는 현행 지방계약법 시행령 제25조제1항제8호다목과 제30조제1항제1호입니다.** 수의계약은 계약방법이고 우선구매는 정책목표이므로, 두 근거를 섞지 말고 제품의 지정·인증 상태를 먼저 확인한 뒤 각각 문서화하세요.",
    ])


def _is_audit_risk_review(q: str) -> bool:
    return (
        any(term in q for term in ("감사", "지적", "문제되지", "특혜", "부당"))
        and any(term in q for term in ("부산업체", "지역업체", "지역상품", "지역제한", "수의계약", "활용"))
    )


def _is_split_purchase_audit_review(q: str) -> bool:
    return (
        any(term in q for term in ("쪼개기", "쫄개기", "분할발주", "나눠", "여러번"))
        and any(term in q for term in ("수의계약", "감사", "대응", "자료"))
    )


def _split_purchase_audit_review_answer(q: str) -> str:
    item = "컴퓨터" if "컴퓨터" in q else "같은 물품"
    return "\n".join([
        f"{item}를 같은 부서에서 여러 번 나눠 구매하면 **쪼개기 수의계약** 또는 분할발주 의심을 받을 수 있습니다.",
        "",
        "- **먼저 볼 점**",
        "  - 같은 목적, 같은 예산, 같은 시기, 같은 수요부서의 구매를 인위적으로 나누었는지 확인합니다.",
        "  - 추정가격 산정 시 동일·유사 물품 수요를 합산했는지, 부서별·기간별 분리 사유가 객관적인지 확인합니다.",
        "",
        "- **감사 대응 자료**",
        "  - 수요조사 자료, 예산 편성·배정 내역, 구매 필요 시점, 고장·증설 등 긴급·추가 수요 발생 근거를 남깁니다.",
        "  - 시장조사, 견적 비교, 세부품명·규격 결정 사유, 반복 구매 사유서를 보관합니다.",
        "  - 통합발주 가능성을 검토했고 왜 나누었는지 결재문서에 남기는 편이 안전합니다.",
        "",
        "정리하면, 나누어 샀다는 사실만으로 항상 위법이라고 단정할 수는 없지만, 금액 기준이나 경쟁절차를 피하려는 구조로 보이면 감사 리스크가 큽니다.",
    ])


def _regional_restriction_answer(q: str) -> str:
    wants_national = "국가" in q
    wants_public_corp = "공기업" in q or "준정부" in q or "공공기관" in q
    wants_local = "지방" in q or "지방자치단체" in q or "지자체" in q
    asks_multiple = sum([wants_national, wants_public_corp, wants_local]) >= 2
    if not any([wants_national, wants_public_corp, wants_local]) or asks_multiple:
        wants_national = wants_public_corp = wants_local = True

    national_amount = _money_limit("P_NATIONAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    public_corp_amount = _money_limit("P_PUBLIC_CORP_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    local_amount = _money_limit("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")

    lines = ["종합공사 지역제한 기준은 **기관유형별 기준값을 나누어** 봐야 합니다.", ""]
    if wants_national:
        lines += _regional_amount_line(
            "국가기관",
            "P_NATIONAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「국가계약법 시행규칙」 제24조제2항제1호가목 + 국가계약법 제4조제1항 고시금액",
        )
    if wants_public_corp:
        lines += _regional_amount_line(
            "공기업ㆍ준정부기관",
            "P_PUBLIC_CORP_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「공기업ㆍ준정부기관 계약사무규칙」 제6조제4항제1호가목",
        )
    if wants_local:
        lines += _regional_amount_line(
            "지방자치단체",
            "P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「지방계약법 시행규칙」 제24조제1호가목",
        )

    if wants_national and wants_public_corp and wants_local:
        summary = f"국가기관만 `고시금액`을 따라 현재 **{national_amount}**이고, 공기업ㆍ준정부기관은 **{public_corp_amount}**, 지방자치단체는 **{local_amount}**입니다."
    elif wants_national:
        summary = f"국가기관의 종합공사는 국가계약법상 `고시금액`을 따라 현재 **{national_amount}** 기준으로 봅니다."
    elif wants_public_corp:
        summary = f"공기업ㆍ준정부기관의 종합공사 지역제한 기준은 **{public_corp_amount}**입니다."
    else:
        summary = f"지방자치단체의 종합공사 지역제한 기준은 **{local_amount}**입니다."

    lines += [
        "",
        summary,
        "",
        "실무 적용 시에는 추정가격 기준인지, 전문공사인지, 그 밖의 공사 관련 법령에 따른 공사인지 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 최신 법령과 고시금액 기준을 바탕으로 한 참고 안내입니다.",
    ]
    return "\n".join(lines)


def _extract_amount_won(q: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)억", q)
    if match:
        return int(float(match.group(1)) * 100_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)천만", q)
    if match:
        return int(float(match.group(1)) * 10_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)백만", q)
    if match:
        return int(float(match.group(1)) * 1_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)만원", q)
    if match:
        return int(float(match.group(1)) * 10_000)

    return None


def _contract_kind(q: str) -> str | None:
    if any(term in q for term in ("종합공사", "전문공사", "건설공사", "공사")):
        return "construction"
    if any(term in q for term in ("용역", "학술", "기술용역")):
        return "service"
    if any(term in q for term in ("물품", "구매", "제조", "납품", "제품")):
        return "goods"
    return None


def _sole_contract_answer(q: str) -> str:
    general_construction = _money_limit("P_DIRECT_GENERAL_CONSTRUCTION_THRESHOLD")
    specialty_construction = _money_limit("P_DIRECT_SPECIALTY_CONSTRUCTION_THRESHOLD")
    other_construction = _money_limit("P_DIRECT_OTHER_CONSTRUCTION_THRESHOLD")
    general_goods_service = _money_limit("P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD")
    policy_company = _money_limit("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD")
    one_quote_general = _money_limit("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    one_quote_policy = _money_limit("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")

    return "\n".join([
        "수의계약은 **계약 종류와 견적 방식**을 나누어 봐야 합니다.",
        "",
        "- **공사 수의계약 금액 기준**",
        f"  - 종합공사: **추정가격 {general_construction}**",
        f"  - 전문공사: **추정가격 {specialty_construction}**",
        f"  - 그 밖의 공사 관련 법령에 따른 공사: **추정가격 {other_construction}**",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호가목, 「국가계약법 시행령」 제26조제1항제5호가목",
        "",
        "- **물품ㆍ용역 일반 기준**",
        f"  - 일반 물품ㆍ용역: **추정가격 {general_goods_service}**",
        f"  - 소기업ㆍ소상공인, 여성기업, 장애인기업, 사회적기업 등 정책기업 요건에 해당하는 일부 물품ㆍ용역: **추정가격 {policy_company}** 범위의 수의계약 근거가 있습니다.",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호, 「국가계약법 시행령」 제26조제1항제5호",
        "",
        "- **1인 견적 가능 기준은 별도입니다**",
        f"  - 기본: **{one_quote_general}**",
        f"  - 청년창업기업ㆍ여성기업ㆍ장애인기업 등 일부 정책기업: **{one_quote_policy}**까지 1인 견적 가능 범위가 열립니다.",
        "  근거: 「지방계약법 시행령」 제30조, 「국가계약법 시행령」 제30조",
        "",
        "따라서 `수의계약 가능`과 `1인 견적으로 바로 가능`은 같은 말이 아닙니다. 실제 발주에서는 품목, 기관유형, 추정가격, 정책기업 자격, 직접생산 여부, 분할발주 금지 여부를 같이 확인해야 합니다.",
        "",
        "지역상품 구매 지원 관점에서는 먼저 부산 업체가 정책기업ㆍ직접생산ㆍ조달등록 요건을 갖췄는지 확인한 뒤, 수의계약이 불안하면 2인 이상 견적 또는 지역제한경쟁입찰로 연결하는 방식이 안전합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _vat_threshold_basis_answer() -> str:
    return "\n".join([
        "수의계약 한도 계산에서는 **부가가치세를 제외합니다.**",
        "",
        "### 1. 기준은 `추정가격`입니다",
        "- 수의계약 가능 여부, 1인 견적 가능 여부, 지역제한 가능 여부처럼 계약방법을 정할 때는 법령상 **추정가격**을 기준으로 봅니다.",
        "- 추정가격은 발주 단계에서 산정하는 **부가가치세 제외 금액**입니다.",
        "- 따라서 `2천만원 이하`, `5천만원 이하` 같은 수의계약 한도도 원칙적으로 VAT 제외 금액으로 판단합니다.",
        "",
        "### 2. 헷갈리기 쉬운 금액 용어",
        "- **추정가격**: VAT 제외. 계약방법 결정 기준입니다.",
        "- **기초금액ㆍ예정가격**: 입찰ㆍ견적 제출과 낙찰자 결정에서 쓰는 금액으로, 실무상 VAT 포함 금액으로 공고되는 경우가 많습니다.",
        "- **계약금액**: 업체에 지급되는 계약서상 총액으로, 일반적으로 VAT 포함 금액입니다.",
        "",
        "### 3. 예시",
        "- 물품 추정가격이 1,900만원이고 부가세가 190만원이면 계약 총액은 2,090만원이 될 수 있습니다.",
        "- 이때 1인 견적 가능 여부는 계약 총액 2,090만원이 아니라 **추정가격 1,900만원**으로 판단합니다.",
        "- 그래서 일반 물품ㆍ용역의 2천만원 이하 1인 견적 기준에는 들어갈 수 있습니다.",
        "",
        "### 4. 실무 체크",
        "- 여성기업ㆍ장애인기업ㆍ사회적기업 등 정책기업의 5천만원 1인 견적 특례도 **추정가격 기준**으로 봅니다.",
        "- 면세 사업자와 계약하는 경우에는 예정가격 작성 시 부가세 상당액 처리 방식이 달라질 수 있으므로 기관 회계 기준과 계약담당자 검토를 함께 남기세요.",
        "- VAT 제외 금액을 한도에 맞추기 위해 동일 수요를 쪼개면 분할계약 지적 위험이 있습니다. 지방계약은 「지방계약법 시행령」 제77조도 함께 확인해야 합니다.",
        "",
        "정리하면, 예산 집행과 계약서 금액은 VAT 포함 총액으로 관리하더라도, **수의계약 한도 판단은 VAT 제외 추정가격**으로 먼저 계산하는 것이 맞습니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _local_company_point_answer(q: str) -> str:
    wants_national = "국가" in q or "중앙" in q or "정부기관" in q
    wants_public_corp = "공기업" in q or "준정부" in q or "공공기관" in q
    wants_local = "지방" in q or "지방자치단체" in q or "지자체" in q
    asks_multiple = sum([wants_national, wants_public_corp, wants_local]) >= 2
    if not any([wants_national, wants_public_corp, wants_local]) or asks_multiple:
        wants_national = wants_public_corp = wants_local = True

    full_rate = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_RATE")
    full_score = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_SCORE")
    partial_rate = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_PARTIAL_RATE")
    partial_score = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_PARTIAL_SCORE")
    national_min_share = _num("P_NATIONAL_JOINT_CONTRACT_MIN_SHARE")

    lines = [
        "맞습니다. **지역업체 참여도ㆍ가점은 조문만 보면 안 되고, 낙찰자 결정기준의 별표ㆍ세부심사기준ㆍ공고문 평가표까지 내려가야 합니다.**",
        "본문 조문은 `가점을 둘 수 있는 근거`를 보여주는 뼈대이고, 실제 배점ㆍ참여비율ㆍ계산방식은 예규의 장ㆍ별표ㆍ붙임 또는 해당 입찰공고의 평가표에 들어 있는 경우가 많습니다.",
        "",
        "### 1. 지역업체 우대 배점 확인 5단계 알고리즘",
        "| 단계 | 확인할 것 | 실제로 열어볼 문서 | 실무 포인트 |",
        "|---|---|---|---|",
        "| 1단계 | 발주처 정체성 | 기관 설립근거, 계약규정, 공고문 첫 부분 | 국가기관ㆍ국가공기업인지, 지방자치단체ㆍ지방공기업인지 먼저 나눕니다. 여기서 적용 법체계가 갈립니다. |",
        "| 2단계 | 계약대상과 낙찰방식 | 입찰공고, 제안요청서, 적격심사 기준 적용 문구 | 공사ㆍ용역ㆍ물품인지, 적격심사ㆍ종합평가ㆍ협상계약ㆍMAS 2단계경쟁인지 확정합니다. |",
        "| 3단계 | 핵심 행정규칙 검색 | 법령정보센터(law.go.kr)의 행정규칙 | 지방계약은 「지방자치단체 입찰시 낙찰자 결정기준」, 국가계약은 「(계약예규) 적격심사기준」ㆍ「(계약예규) 공동계약운용요령」부터 봅니다. |",
        "| 4단계 | 별표ㆍ세부심사표 추적 | 해당 예규의 장, 별표, 붙임, 세부심사방법 | 실제 `몇 점`인지는 여기 있습니다. 조문 검색에서 멈추지 말고 사업 유형ㆍ금액구간에 맞는 별표까지 내려갑니다. |",
        "| 5단계 | 공고문 최종 확인 | 나라장터 공고문, 과업지시서, 제안요청서, 평가표 | 상위 법령ㆍ예규 범위 안에서 해당 공고가 어떤 기준을 적용한다고 명시했는지가 최종 실무 기준입니다. 자체 적격심사 세부기준이 있으면 반드시 함께 봅니다. |",
        "",
        "### 2. 사업 유형별 별표 추적 포인트",
        "| 사업 구분 | 확인할 구체 경로 | 봐야 할 항목 |",
        "|---|---|---|",
        "| 시설공사 | 시설공사 적격심사ㆍ종합평가 관련 장과 별표 | 지역업체 참여비율, 지역의무공동도급 여부, 공동수급체 지분율, 공사 금액구간별 배점 |",
        "| 기술ㆍ학술용역 | 용역 적격심사 세부기준 별표 | 지역업체 합산 참여비율, 참여도 점수, 공동수급체 구성 방식 |",
        "| 일반용역ㆍ협상계약 | 낙찰자 결정기준, 협상계약 평가기준, 제안요청서 평가표 | 지역 이해도, 현장 대응성, 지역업체 참여계획, 지역 자원 활용계획이 정당한 평가항목인지 |",
        "| 물품구매 | 물품 적격심사 세부기준, MAS 2단계경쟁 기준, 공고 특수조건 | 물품은 지역가점보다 제조ㆍ직접생산, 정책기업, 납품지역, A/S, 쇼핑몰 등록 여부가 더 중요할 수 있습니다. |",
        "",
    ]

    if wants_local:
        lines += [
            "### 3. 지방계약 대상이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「지방자치단체 입찰시 낙찰자 결정기준」.",
            "- **다음 확인**: 공사ㆍ용역ㆍ물품 중 해당 장을 열고, 그 장의 별표ㆍ세부심사기준에서 `지역업체 참여도`, `지역업체 합산 참여비율`, `지역의무공동도급`, `지역업체 참여계획` 항목을 찾습니다.",
            f"- **대표 예시**: 기술ㆍ학술용역 적격심사에서는 지역업체 합산 참여비율 **{full_rate} 이상: {full_score}**, **{partial_rate} 이상 {full_rate} 미만: {partial_score}** 같은 참여도 점수 구조가 쓰일 수 있습니다.",
            "- **주의**: 이 숫자는 질문 유형을 설명하기 위한 대표 기준입니다. 실제 적용은 해당 공고가 적용한다고 명시한 최신 예규 번호, 사업 유형, 금액구간, 별표를 기준으로 확정해야 합니다.",
            "",
        ]

    if wants_national:
        lines += [
            "### 4. 국가계약 대상이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「국가계약법 시행령」에서 공동계약ㆍ제한경쟁의 근거를 확인한 뒤, 실제 배점은 「(계약예규) 적격심사기준」, 「(계약예규) 공동계약운용요령」, 분야별 세부기준에서 찾습니다.",
            "- **핵심 구분**: 국가계약은 `모든 계약에 지역업체 가점 몇 점`이라는 단일 표가 있는 구조가 아닙니다. 가점인지, 지역업체 의무참여인지, 공동수급 허용인지부터 나눠야 합니다.",
            f"- **대표 예시**: 「국가계약법 시행령」 제72조와 「공동계약운용요령」 제9조는 일정 공동계약에서 지역업체 최소 지분율을 **{national_min_share} 이상**으로 두는 구조를 둡니다.",
            "- **주의**: 국가기관이 지방계약의 별표 점수를 그대로 가져와 쓰면 부당한 평가기준이 될 수 있습니다.",
            "",
        ]

    if wants_public_corp:
        lines += [
            "### 5. 공기업ㆍ준정부기관이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「공기업ㆍ준정부기관 계약사무규칙」과 해당 기관의 계약규정ㆍ입찰공고.",
            "- **다음 확인**: 규칙에 없는 사항은 국가계약법령을 준용하는 구조인지, 기관별 계약기준ㆍ자체 적격심사 세부기준이나 제안서 평가기준을 따로 두는지 봅니다.",
            "- **주의**: 계약사무규칙 자체에 지역업체 가점 단일 점수표가 바로 들어 있는 구조가 아닙니다. 지역제한은 같은 규칙 제6조의 입찰참가자격 제한 장치이고, 가점ㆍ참여도와는 구분해야 합니다.",
            "",
        ]

    lines += [
        "### 6. 공고문에서 마지막으로 확인할 문구",
        "- `본 입찰은 ○○ 예규 제○호 「○○ 낙찰자 결정기준」을 적용한다`",
        "- `지역업체 참여도는 별표 ○의 산식에 따라 평가한다`",
        "- `공동수급체 구성 시 지역업체 참여비율을 평가한다`",
        "- `기관 자체 적격심사 세부기준 또는 제안서 평가기준을 적용한다`",
        "",
        "정리하면, **조문에서 근거를 확인하고, 예규ㆍ낙찰자 결정기준의 별표에서 점수를 찾은 뒤, 나라장터 공고문과 평가표에서 최종 적용 기준을 확정**해야 합니다. `부산업체라서 무조건 가점`이 아니라, 해당 계약의 기관유형ㆍ사업유형ㆍ낙찰방식ㆍ별표 항목 안에서 허용되는지를 확인하는 순서입니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ]
    return "\n".join(lines)


def _mas_regional_review_answer(q: str) -> str:
    item = _item_hint(q)
    item_prefix = f"**{item}** 구매처럼 품목이 정해진 경우에는, " if item else ""
    item_example = item or "LED, CCTV, 사무가구"
    return "\n".join([
        f"{item_prefix}종합쇼핑몰/MAS 2단계 경쟁에서는 **부산업체라는 이유만으로 지역제한을 걸거나 별도 가점을 주는 방식은 신중해야 합니다.**",
        "다만 부산 지역상품 구매 지원 관점에서 활용할 수 있는 실무 경로는 있습니다.",
        "",
        "- **1. 부산 MAS 등록업체를 후보군으로 먼저 찾기**",
        "  - 구매 품목을 확정한 뒤 종합쇼핑몰에서 부산 소재 공급업체, 납품 가능 지역, 계약상태, 규격 일치 여부를 확인합니다.",
        "  - 이는 특정 업체 특혜가 아니라 제안요청 전 후보 탐색과 시장조사 단계로 정리하는 것이 안전합니다.",
        "",
        "- **2. 2단계 경쟁에서는 평가항목 안에서만 지역 장점을 반영**",
        "  - 지역업체 자체를 독립 가점으로 두기보다 납기, 사후관리, 현장지원, 유지보수 대응 같은 정당한 평가요소와 연결해야 합니다.",
        "  - 부산 업체가 빠른 A/S나 납품 대응을 제안서에 제시하면, 그 내용이 공고된 평가항목과 맞는 범위에서 검토될 수 있습니다.",
        "",
        "- **3. 지역제한경쟁입찰과 MAS 2단계 경쟁은 구분**",
        "  - 지방계약법령상 지역제한은 일반 경쟁입찰의 참가자격 제한 장치입니다.",
        "  - MAS 2단계 경쟁에서는 조달청 다수공급자계약 체계와 종합쇼핑몰 운영규정, 물품 다수공급자계약 업무처리규정을 우선 확인해야 합니다.",
        "",
        "- **4. 품목이 정해졌다면 업체 후보까지 붙여야 실무 답변이 됩니다**",
        f"  - 예: {item_example}처럼 세부품명이 있으면 부산 MAS 등록업체, 조달등록 여부, 인증제품 여부를 함께 조회해 구매 경로를 정리합니다.",
        "  - 품목이 없는 제도 질문이면 여기서는 원칙과 확인 순서까지만 안내하는 것이 적절합니다.",
        "",
        "정리하면, **MAS에서 부산업체를 직접 우대한다고 단정하기보다는, 부산 MAS 등록업체를 후보로 발굴하고 납기ㆍA/Sㆍ현장지원 등 정당한 평가요소로 연결하는 방식**이 안전합니다.",
        "근거: 「조달사업에 관한 법률」, 「국가종합전자조달시스템 종합쇼핑몰 운영규정」, 「물품 다수공급자계약 업무처리규정」",
        "⚖️ 본 답변은 내부 DB에 적재된 조달 관련 행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _excellent_procurement_or_third_party_answer() -> str:
    return "\n".join([
        "우수조달물품이나 **제3자단가계약** 제품은 부산 지역상품 구매지원에 도움이 될 수 있습니다. 다만 `부산업체라서 바로 수의계약 가능`으로 보지 말고, 제품 지정ㆍ계약상태ㆍ납품요구 가능 여부를 순서대로 확인해야 합니다.",
        "",
        "- **우수조달물품**",
        "  - 조달청 우수조달물품 지정 제품인지, 지정 상태가 유효한지 확인합니다.",
        "  - 구매하려는 규격과 우수조달 지정 제품명이 같은지 확인해야 합니다.",
        "  - 부산업체 제품이면 지역상품 구매 취지와 연결할 수 있지만, 우수조달 지정 자체와 부산 소재 여부는 별도 요건입니다.",
        "",
        "- **제3자단가계약/종합쇼핑몰 경로**",
        "  - 나라장터 종합쇼핑몰 등록 여부, 계약기간, 납품 가능 지역, 납품요구 한도와 2단계 경쟁 대상 여부를 확인합니다.",
        "  - 부산 공급업체가 있으면 시장조사와 후보 검토 자료로 활용하되, 특정 업체를 미리 정한 것처럼 공고ㆍ평가를 설계하면 안 됩니다.",
        "",
        "- **실무 처리 방향**",
        "  - 품목명이 정해지면 부산업체 후보, 쇼핑몰/MAS 등록, 우수조달ㆍ혁신제품ㆍ성능인증 여부를 함께 조회합니다.",
        "  - 답변에는 `계약 가능` 단정 대신 `등록상태, 지정ㆍ인증 상태, 규격 일치, 기관유형별 절차 확인 후 검토 가능`으로 표시하는 것이 안전합니다.",
        "",
        "⚖️ 본 답변은 내부 DB와 구매지원 카탈로그 기준의 실무 안내입니다.",
    ])


def _audit_risk_review_answer() -> str:
    return "\n".join([
        "부산업체를 활용할 때 감사에서 문제되지 않게 하려면 핵심은 **지역상품 구매지원 목적**과 **계약법상 경쟁성ㆍ공정성**을 함께 남기는 것입니다.",
        "",
        "- **1. 특정 업체를 먼저 정하지 않기**",
        "  - 시장조사는 가능하지만, 공고조건ㆍ규격ㆍ평가항목이 특정 부산업체만 맞출 수 있게 작성되면 특혜 시비가 생길 수 있습니다.",
        "  - 과업지시서에는 `부산업체 수행` 같은 직접 조건보다 과업 수행에 필요한 현장 대응, 납기, 유지관리, 의사소통, 품질관리 기준을 객관적으로 적어야 합니다.",
        "  - 업체 후보표는 `검토 후보`로 관리하고, 계약 가능 여부는 별도 확인으로 남깁니다.",
        "",
        "- **2. 지역제한ㆍ지역의무공동도급ㆍ지역업체 가점은 제도별 요건 확인**",
        "  - 지역제한은 계약목적물과 금액 기준, 본점 소재지, 경쟁 가능한 업체 수를 확인해야 합니다.",
        "  - 지역의무공동도급은 주로 공사에서 검토하며, 지역업체 수와 공동수급체 구성 가능성을 확인해야 합니다.",
        "  - 가점ㆍ참여도는 기관유형과 낙찰자 결정기준, 입찰공고 평가항목에 근거가 있어야 합니다.",
        "",
        "- **3. 수의계약은 금액ㆍ사유ㆍ견적방식을 문서화**",
        "  - 소액수의, 정책기업, 기술개발제품, 우수조달물품 등은 각각 근거와 한도가 다릅니다.",
        "  - `부산업체라서 수의계약`이 아니라, 해당 법령상 사유와 금액 기준을 먼저 확인해야 합니다.",
        "",
        "- **4. 남겨야 할 확인 자료**",
        "  - 적용 법령 조문, 기준금액 산정 근거, 세부품명/규격 결정 이유, 후보업체 비교표, 인증ㆍ쇼핑몰 등록 상태, 견적 또는 평가 기록을 남깁니다.",
        "  - 내부 검토서에는 `지역상품 구매지원 목적`, `경쟁성 확보 방식`, `특정업체 배제ㆍ특혜 방지 조치`를 함께 적는 것이 좋습니다.",
        "",
        "정리하면, 부산업체 활용 자체가 문제라기보다 **근거 없는 제한, 특정업체 맞춤 규격, 수의계약 사유 누락, 후보 검증 미기록**이 감사 리스크입니다.",
    ])


def _regional_mandatory_joint_contract_answer(q: str = "") -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    min_company_count = _num("P_LOCAL_JOINT_CONTRACT_MIN_QUALIFIED_COMPANY_COUNT")
    public_corp_note = []
    if "공기업" in q or "준정부" in q or "공공기관" in q:
        public_corp_note = [
            "",
            "- **공기업ㆍ준정부기관에서의 추가 확인**",
            "  - 공기업ㆍ준정부기관은 「공기업ㆍ준정부기관 계약사무규칙」과 기관 자체 계약기준, 입찰공고 조건을 함께 확인해야 합니다.",
            "  - 지역업체 공동도급을 검토할 때도 국가계약법령 준용 여부, 기관 내부 기준, 공사 성격, 공동수급체 구성 가능성을 먼저 확인해야 합니다.",
            "  - 지방자치단체 기준의 지역의무공동도급 비율을 공기업 계약에 그대로 적용한다고 단정하면 안 됩니다.",
            "  근거: 「공기업ㆍ준정부기관 계약사무규칙」 및 공동계약 관련 내부 DB 기준",
        ]

    return "\n".join([
        "지역의무공동도급은 지역업체 참여를 강제해 지역 시공 참여를 확보하는 장치입니다. 전기공사 같은 공사에서 검토할 수 있고, 핵심은 **공사에 한해** 적용한다는 점입니다.",
        "지역제한은 참가자격을 지역으로 제한하는 장치이고, 지역의무공동도급은 공동수급체 안에 지역업체 참여비율을 두는 장치라서 서로 구분해 검토해야 합니다.",
        "",
        "- **적용 대상**",
        "  - 지방계약에서 공동계약을 체결하는 경우, 지역경제 활성화를 위해 지역업체 참여비율을 정할 수 있습니다.",
        "  - 「지방자치단체 입찰 및 계약집행기준」은 **공사의 경우에만 지역의무 공동도급으로 발주할 수 있다**고 정합니다.",
        "  근거: 「지방계약법 시행령」 제88조, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령",
        "",
        "- **지역업체 최소 시공참여비율**",
        f"  - 원칙: 해당 시ㆍ도 소재 지역업체의 최소 시공참여비율 **{min_share}**를 입찰공고에 명시",
        f"  - 지역경제 활성화 필요성이 있으면 **{max_share} 이하의 범위**에서 정할 수 있습니다.",
        "",
        "- **발주하면 안 되거나 조정이 필요한 경우**",
        f"  - 최소 참여비율 이상을 충족할 시공능력평가액을 갖춘 지역업체가 {min_company_count} 미만인 경우",
        f"  - {min_share} 이상 지역업체로 제한할 때 필요한 면허ㆍ등록 자격을 갖춘 지역업체가 {min_company_count} 미만인 경우",
        "  - 품질 저하 우려나 공동수급체 구성이 곤란한 경우",
        "  - 지역업체 수를 과도하게 제한하거나 특정 지역업체 하도급ㆍ자재납품을 의무화하는 방식은 부당 제한이 될 수 있습니다.",
        *public_corp_note,
        "",
        "지역상품 구매 지원 관점에서는 대형 공사에서 부산 지역업체 참여를 제도적으로 확보하는 데 유용하지만, 입찰공고 단계에서 비율ㆍ면허ㆍ시공능력ㆍ업체 수를 먼저 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])
