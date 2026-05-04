# Rule Engine v0.1 Mapping Table

이 테이블은 `GatewayResponse`의 주요 상태값 조합을 `DecisionContext`의 핵심 필드로 변환하는 결정(Decision) 매트릭스입니다.

## 0. 룰 적용 우선순위 (Priority)
Rule Engine은 아래의 우선순위(1 -> 6)에 따라 상태를 판독하고 더 높은 우선순위의 상태가 발생하면 하위 룰을 덮어씁니다.
1) `out_of_scope` (관할 외, 지원불가)
2) `insufficient_data` (필수 슬롯 누락: `buyer_type_confidence="low"` 등)
3) `manual_review_required` (엣지 케이스, 복수 품목 혼선)
4) `conditional_review` (추가 정보/갱신 필요)
5) `review_candidate` (정상 매핑)
6) `not_triggered` (기본 상태)

> **주의**: `buyer_type_confidence="low"`에 의한 `insufficient_data`는 Item Eligibility 로직에 우선하여 적용됩니다.

## 1. 기본 슬롯 검증 라우팅
| 상태 | 조건 (`GatewayResponse`) | `review_outcome` | `missing_required_slots` | 비고 |
|:---|:---|:---|:---|:---|
| 필수 슬롯 누락 | `source_context.buyer_type_confidence == "low"` | `insufficient_data` | `["buyer_type"]` 추가 | `buyer_type_assumed=True` 할당. Item 로직보다 우선. |
| 데이터 부족 | `item_eligibility_result.resolver_status == "data_unavailable"` | `insufficient_data` | `["detail_item_code"]` 등 추가 | |

## 2. Route Resolver 매핑 (오버레이)
| 상태 | 조건 | `route_directive` | `dual_routing_active` | `review_outcome` 변경 |
|:---|:---|:---|:---|:---|
| 단가계약(MAS) 적용 | `route_context.overlay_applied == True` | `base_law_plus_pps_overlay_review` | `True` | - (Item/우선순위에 위임) |
| 오버레이 미적용 | `route_context.overlay_applied == False` | `None` | `False` | - |

## 3. Item Eligibility 매핑
| `resolver_status` | `trigger_grade` | 세부 조건 | `review_outcome` | `item_action_required` | `manual_review_reasons` |
|:---|:---|:---|:---|:---|:---|
| `resolved` | `explicit` | 직생/중기간제품 `company_cert_status == "valid"` | `review_candidate` | `verify_direct_production_cert` | |
| `resolved` | `explicit` | 직생/중기간제품 `company_cert_status == "unknown"` | `conditional_review` | `request_cert_submission` | |
| `ambiguous` | `explicit`/`silent` | 복수 품목 후보 탐지 (`detail_item_candidates` > 1) | `manual_review_required` | `disambiguate_item` | `["detail_item_code_ambiguous"]` |
| `not_triggered` | `null` | 특별 관리 품목이 아님 | `not_triggered` | `None` | |
