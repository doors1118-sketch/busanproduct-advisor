# Answer Builder v0.1 Mapping Policy

Rule Engine의 `DecisionContext` 상태값(`review_outcome`, `trigger_grade` 등)에 따라 Answer Builder가 조합할 수 있는 허용 문구 템플릿의 매핑 정책입니다.

## 1. Review Outcome 별 허용 문구 (Summary Section)
확정적 표현을 철저히 배제하고 다음의 허용 문구(또는 동의어)만 제한적으로 사용해야 합니다.
- `out_of_scope`: "해당 질의는 관할 구역 외이거나 시스템 지원 범위 밖입니다."
- `insufficient_data` / `data_unavailable`: "정확한 안내를 위해 추가 데이터(예: 계약 주체, 품목명 등)의 확인이 필요합니다."
- `manual_review_required`: "복수의 해석이 가능하여 수동 검토가 요구되는 사안입니다."
- `conditional_review`: "특정 조건(갱신 확인 등) 충족 여부에 대한 추가 검토가 권고됩니다."
- `review_candidate`: "제시된 조건을 기준으로 우선 검토 후보로 분류할 수 있으나, 계약 전 확인이 필요합니다."
- `not_triggered`: "특별한 자격 심사 로직이 발동되지 않은 일반 안내 대상입니다."

## 2. Item Eligibility 노출 정책 (Item Section)
Item Resolver의 결과(`trigger_grade` 등)에 따른 품목 자격 안내 문구 작성 규칙입니다.
- **explicit**: `item_eligibility_section`이라는 별도의 독립 섹션을 생성하여 세부 조건(직생, 중소기업간 경쟁제품 등)을 상세히 안내합니다.
- **silent**: 별도 섹션을 생성하지 않고, 요약 또는 주의사항 섹션 내에 "해당 품목이 중소기업자간 경쟁제품으로 특정되면 직접생산확인 검토가 필요할 수 있습니다."라는 1줄 보조 문구만 허용합니다.
- **not_triggered**: 직접생산이나 중소기업자간 경쟁제품 관련 문구를 일절 노출하지 않습니다.
- **ambiguous**: 세부품명 확정이 불가함을 알리고, 사용자에게 정확한 품번/품명을 확인 요청하는 문구를 출력합니다.

## 3. Enrichment Data 표기 규칙
Company Resolver에서 제공된 Enrichment Data(예: 인증서 보유 유무 등)는 오로지 **후보표(Candidate Table) 섹션의 보조 참고 열(Column) 수준으로만 표시**해야 합니다.
- **허용되는 보조 문구 목록**:
  - "참고: 직생증명 유효기간 2026-12"
  - "직생증명서: 보유"
  - "직생증명서: 만료"
  - "직생증명서: 알 수 없음"
- (X) 불가: "직생증명이 유효하므로 해당 업체와 계약할 수 있습니다"
