# Item Eligibility Rule Integration Plan v0.1.2

## 1. 처리 순서 (Sequence)
1. 사용자 질문에서 `item_name` 추출
2. `item_alias_map`으로 `detail_item_code` 후보 조회
3. 후보가 복수이면 법적 판단은 보류하되, 후보를 제시하고 지역업체 검색은 병행
4. `detail_item_code` 확정
5. `sme_competition_product_item` 조회 (유효기간 확인)
6. `direct_production_requirement` 조회
7. `company_id`가 있으면 `company_direct_production_cert_mapping` 조회
8. `buyer_type`, `amount`, `procurement_route`, `contract_method`와 결합
9. Answer Builder에 `eligibility_context` 전달

## 2. eligibility_context 구조
```json
{
  "detail_item_resolved": true,
  "detail_item_code": "4617162201",
  "detail_item_name": "영상감시장치",
  "is_sme_competition_product": true,
  "direct_production_required": true,
  "company_direct_production_status": "expired",
  "eligibility_status": "needs_certificate_update_check",
  "candidate_action": "request_updated_certificate",
  "procurement_support_message": "지역업체 후보로는 유지할 수 있으나, 계약 전 직접생산확인 갱신 증빙 확인이 필요합니다.",
  "legal_conclusion_allowed": false
}
```

## 3. 결합 원칙
- Item Eligibility는 독립 판단으로 끝나지 않습니다.
- 기존 Legal Rule, 업체DB, 조달경로, 금액 기준과 결합해야 합니다.
- `legal_conclusion_allowed`가 `false`이면 계약 가능 여부를 단정하지 않습니다.
