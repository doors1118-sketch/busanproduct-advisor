# Rule Engine Priority Order v0.1

본 문서는 챗봇 Rule Engine의 **기본 판단 우선순위**를 정의합니다.
Item Eligibility는 조건부 레이어이며, 기본 흐름에서 선행 게이트로 작동하지 않습니다.

## 1. 기본 판단 순서

```
┌─────────────────────────────────────────────────────────────┐
│  사용자 질문 입력                                             │
│      │                                                      │
│      ▼                                                      │
│  ❶ buyer_type (기관유형 식별)                                │
│      │  지방자치단체 / 국가기관 / 공기업 / 출자출연기관          │
│      ▼                                                      │
│  ❷ contract_object (계약목적물 분류)                          │
│      │  공사 / 물품 / 용역                                    │
│      ▼                                                      │
│  ❸ amount (추정가격·예정가격 확인)                             │
│      │  수의계약 한도, 지역제한 기준, 소액수의 기준              │
│      ▼                                                      │
│  ❹ procurement_route (조달경로 판별)                          │
│      │  자체계약 / 조달청의뢰 / MAS / 쇼핑몰                   │
│      ▼                                                      │
│  ❺ contract_method (계약방식 판별)                            │
│      │  일반경쟁 / 제한경쟁 / 지명경쟁 / 수의계약               │
│      ▼                                                      │
│  ❻ local_preference (지역제한·지역업체 우대)                   │
│      │  시행령 제13조, 공동수급체 참여비율, 지역상품 조례         │
│      ▼                                                      │
│  ❼ policy_company / certification (정책기업·인증 특례)         │
│      │  사회적기업, 여성기업, 장애인기업, 혁신제품 등             │
│      ▼                                                      │
│  ❽ item_eligibility (조건부 — 트리거 조건 충족 시에만)          │
│      │  중소기업자간 경쟁제품 / 직접생산확인                     │
│      │  ※ item_eligibility_required = true일 때만 호출          │
│      ▼                                                      │
│  최종 답변 조립 (Answer Builder)                              │
└─────────────────────────────────────────────────────────────┘
```

## 2. 단계별 역할

| 순서 | 레이어 | 역할 | 항상 실행 |
|:---:|--------|------|:---------:|
| ❶ | buyer_type | 적용 법령체계 결정 (국가계약법/지방계약법/공기업법) | ✅ |
| ❷ | contract_object | 계약목적물별 법조항 분기 | ✅ |
| ❸ | amount | 금액 기준 수의계약·소액수의·지역제한 한도 판별 | ✅ |
| ❹ | procurement_route | 조달청 경로 Overlay 적용 여부 판단 | ✅ |
| ❺ | contract_method | 경쟁/수의/지명 등 계약방식 판별 | ✅ |
| ❻ | local_preference | 지역제한 가능 여부, 지역업체 후보 검색 | ✅ |
| ❼ | policy_company | 정책기업 특례 (사회적기업, 여성기업 등) | ✅ |
| ❽ | item_eligibility | 중기경쟁제품·직접생산확인 검토 | ❌ 조건부 |

## 3. 핵심 원칙

1. **❶~❼은 항상 실행**합니다. 질문 유형에 따라 일부 레이어가 해당 없을 수 있으나, 해당 여부 판단 자체는 항상 수행합니다.
2. **❽ item_eligibility는 트리거 조건이 충족된 경우에만 호출**합니다. 트리거 조건은 `item_eligibility_trigger_policy_v0_1_3.md`에 정의됩니다.
3. 각 레이어의 결과는 후속 레이어에 Context로 전달됩니다. 선행 레이어에서 이미 확정된 판단을 후행 레이어가 뒤집지 않습니다.
4. 지역업체 후보 검색(❻)은 item_eligibility(❽) 결과와 독립적으로 실행됩니다. 직생 미확인이 지역업체 검색을 차단하지 않습니다.

## 4. 기존 문서와의 관계

| 기존 문서 | 변경 사항 |
|-----------|-----------|
| `item_eligibility_rule_integration_plan.md` | Step 1에서 Item Eligibility를 선행으로 배치 → **폐기(superseded)**. 본 문서로 대체. |
| `item_eligibility_rule_integration_plan_v0_1_2.md` | 처리 순서 1~9를 Item Eligibility 선행으로 정의 → **폐기(superseded)**. 본 문서로 대체. |
| `procurement_route_layer_policy.md` | 변경 없음. ❹ procurement_route 단계에서 참조. |
| `local_public_institution_routing_policy.md` | 변경 없음. ❶ buyer_type 단계에서 참조. |
| `procedure_only_separation_policy.md` | 변경 없음. Rule Engine에서 절차 전용 규정 배제 원칙 유지. |
