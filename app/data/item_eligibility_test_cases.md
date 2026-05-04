# Item Eligibility Test Cases

본 문서는 향후 Rule Engine과 품목 DB 연동 로직의 안정성을 확인하기 위한 **회귀 테스트(Regression Test)** 시나리오 모음입니다.

## Test Case 1: 일반 품목명 입력에 의한 다중 후보 도출
- **User Prompt**: "CCTV를 조달청에서 수의계약으로 사고 싶습니다. 직생이 필요한가요?"
- **Expected Behavior**:
  1. `item_alias_map`에서 "CCTV"를 검색하여 다수의 `detail_item_code`(방범용 CCTV, 차량번호인식 CCTV 등) 매치 감지.
  2. 룰 엔진은 "특정 세부품명을 알 수 없어 중기경쟁제품 및 직접생산확인 여부를 확답할 수 없습니다."라며 후보군을 반환.
- **Fail Condition**: 임의의 CCTV 하나를 찍어 중기경쟁제품이라고 단정하여 답변하는 경우.

## Test Case 2: 경쟁제품 확인 및 직접생산 요건 안내
- **User Prompt**: "세부품명번호 4617162201 (영상감시장치) 수의계약 시 유의사항 알려주세요."
- **Expected Behavior**:
  1. `sme_competition_product_item`에서 중기경쟁제품 대상(`is_sme_competition_product=True`)임을 확인.
  2. `direct_production_requirement`에서 요구되는 설비 기준 요약 내역을 가져옴.
  3. "이 품목은 중소기업자간 경쟁제품이므로, 직접생산확인 보유 여부 검토가 필수적입니다." 텍스트 출력.
- **Fail Condition**: 직접생산확인 확인 과정 없이 금액 조건만으로 수의계약이 가능하다고 안내.

## Test Case 3: 인증 기간 만료 업체 검증
- **User Prompt**: "세부품명 4617162201에 대해, 업체 A(company_id=123)와 계약을 진행하려고 합니다."
- **Mock Data State**: 업체 A의 `cert_status`는 `expired`.
- **Expected Behavior**:
  1. `company_direct_production_cert_mapping` 조회.
  2. 만료된 인증서임을 감지.
  3. "업체DB 기준 해당 세부품명의 직접생산확인 유효기간이 만료(또는 미확인)되었습니다. 유효 여부를 다시 확인해야 합니다." 출력.
- **Fail Condition**: 과거 인증 이력만 보고 "직접생산확인을 보유하고 있다"고 단정.

## Test Case 4: 판단 오버라이드 (Over-Conclusion) 방지 검증
- **User Prompt**: "업체 B가 해당 펌프(세부품명 특정됨)의 직접생산확인 증명서를 가지고 있습니다. 수의계약 체결하면 되나요?"
- **Expected Behavior**:
  1. 직생이 있다는 사실을 적격 요건 중 하나로만 처리.
  2. 금액(Amount), 발주기관 유형(`buyer_type`) 등 다른 거시적 요건도 함께 물어보거나 종합 검토 필요성을 고지.
  3. "직접생산확인 보유는 필수 적격성 정보이지만, 최종 수의계약 가능성은 금액, 기관 유형 등 타 법적 요건을 함께 확인해야 합니다." 출력.
- **Fail Condition**: 직생만 있으면 프리패스로 수의계약 가능하다고 확답.
