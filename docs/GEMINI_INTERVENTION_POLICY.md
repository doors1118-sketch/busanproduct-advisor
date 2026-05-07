# Gemini/LLM 개입 정책 (Intervention Policy)

본 문서는 부산 조달 챗봇 파이프라인 내에서 대형 언어 모델(LLM, Gemini)이 수행하는 역할과 권한의 한계를 명확히 규정합니다. 

파이프라인의 안전성과 법적 정확성을 보장하기 위해, Gemini는 사용자의 자연어를 시스템이 이해할 수 있는 스키마로 구조화하는 역할만 수행하며, 어떠한 법적 판단이나 수치적 결정도 내리지 않습니다.

---

## 1. LLM(Gemini) 허용 역할 (Allowed Roles)
Gemini는 기본적으로 `RouterResult` 스키마를 채우는 **자연어 해석 계층**으로만 사용됩니다.

- **Intent 분류**: 사용자의 의도를 사전에 정의된 Enum(`primary_intent`, `secondary_intents`)으로 분류합니다.
- **Slot 후보 추출**: 사용자 질문 내의 정보(품목명, 금액, 업체명, 지역 등)를 `slots`에 추출합니다.
- **Routing Decision 후보 선택**: 의도에 따라 어떤 Flow를 타야 할지 초기 결정(`routing_decision`)을 내립니다.
- **Clarification Needed 후보 생성**: 정보가 부족할 경우 되물을 질문(`clarification_needed`)을 생성합니다.
- **비정형 표현 매핑**: 라우터가 정규식으로 놓치기 쉬운 다양한 자연어 표현을 기존 스키마 구조로 매핑합니다.

## 2. LLM(Gemini) 금지 역할 (Disallowed Roles)
Gemini는 시스템의 결정론적(Deterministic) 계층을 오염시킬 수 있는 다음 행위를 절대 수행해서는 안 됩니다.

- **계약/구매 가능 여부 판단 금지**: "계약 가능합니다", "수의계약 가능합니다" 등의 최종 판단을 내리지 않습니다.
- **법령 기준금액 생성 금지**: 법령에 명시된 기준금액을 스스로 생성하거나 추론하지 않습니다.
- **중기경쟁제품 여부 단정 금지**: 특정 품목이 중소기업자간 경쟁제품인지 확정하지 않습니다.
- **직접생산확인 대상 여부 단정 금지**: 특정 품목이 직접생산확인 대상인지 확정하지 않습니다.
- **업체 적격 여부 단정 금지**: 특정 업체의 적격성 여부를 최종 결정하지 않습니다.
- **Final Markdown 생성 금지**: Evidence Builder를 우회하여 독자적으로 마크다운 리포트를 렌더링하지 않습니다.
- **새로운 Rule ID 생성 금지**: 사전에 정의되지 않은 법령/제도 ID를 만들지 않습니다.
- **새로운 Routing Decision 생성 금지**: 기존 `routing_decision` Enum 외의 새로운 파이프라인 경로를 만들지 않습니다.

## 3. LLM 추가 활용 허용 영역 (Advanced Allow-list)
기본 라우팅 외에 다음 영역에서는 제한적으로 LLM 개입을 허용합니다. 단, 판단 계층에는 여전히 개입할 수 없습니다.

1. **Gemini Semantic Fallback Router**
   - 기존 Router와 Slot Repair가 충분히 구조화하지 못한 질문을 기존 `RouterResult` 스키마로 재매핑합니다.
   - 새 intent, 새 flow, 새 rule_id는 생성 불가합니다.
2. **Query Expansion**
   - 품목명·업체검색어 후보를 확장하여 생성합니다.
   - 생성된 후보는 반드시 내부의 Company API / Item Eligibility API 조회를 거쳐야 합니다.
   - LLM이 직접 품목이나 업체의 적격성을 판단하지 않습니다.
3. **Clarification Generator**
   - 부족한 slot을 사용자에게 되묻는 친절한 문장을 생성합니다.
   - 단, 법령 판단이나 계약 가능성 판단을 질문 내용에 포함시켜서는 안 됩니다.
4. **Answer Style Rewriter**
   - Evidence Builder가 만든 구조화된 결과를 사용자가 더 읽기 쉬운 문장으로 다듬습니다.
   - 새로운 수치, 법령, 결론을 절대 추가하지 않습니다.
   - 최종 Forbidden Phrase Scan(금지어 필터링)을 반드시 통과해야 합니다.

## 4. LLM 모델 정책
- **기본 Router 모델**: Gemini Flash (비용 및 속도 최적화)
- **Fallback 모델**: Gemini Pro (JSON 스키마 파싱 실패, 복합 intent 파싱 실패, 극히 비정형적인 표현 처리 시 제한적 사용)
- **Pro Fallback 결과 처리**: Pro 모델이 내린 결과 역시 최종 판단값이 아니라, 일반적인 `RouterResult` 구조화 후보값으로만 취급됩니다.

---

## 5. Slot Repair와의 관계 및 Flow 승격 정책

Gemini Output 생성 직후에는 반드시 **Slot Repair 계층(`slot_repair.py`)**을 거칩니다.

- **최종 결정권**: Gemini Output은 후보 슬롯(Candidate Slot)일 뿐 최종 판단값이 아닙니다.
- **보정 범위**: Slot Repair는 기본적으로 비어 있는 슬롯만 보정하며, 만약 Gemini와 Slot Repair 간 충돌이 발생하면 결정론적 보정(Deterministic Repair)을 우선하거나 `clarification_required` 상태를 유지합니다.
- **금액 처리 원칙**: Slot Repair가 추출하는 금액은 오직 **사용자 입력 금액**으로만 쓰입니다. 법령상 기준금액은 Amount Layer가 Source Map의 `resolved_value`에서만 가져옵니다.
- **Flow 승격 (Promotion)**:
  - Gemini가 초기 판단에서 `clarification_required`를 내렸더라도, Slot Repair를 통해 충분한 슬롯(금액, 업체유형, 품목 등)이 확보되면 기존 정의된 Flow(`contract_review_flow`, `candidate_search_flow` 등)로 승격시킵니다.
  - 단, 승격 과정에서 새로운 커스텀 Flow를 만들지 않습니다.

## 6. Evidence 노출 정책
- 최종 결정된 Routing Decision이 `clarification_required`일 경우 Evidence Section 출력을 생략합니다.
- Slot Repair를 통해 정상 Flow로 승격된 경우에 한정하여 Evidence Builder를 실행합니다.
- 어떠한 경우에도 내부 디버깅용 변수인 `expected_value_hint`나 `parameter_ref`가 최종 렌더링된 마크다운에 노출되어서는 안 됩니다.
- 법령 기준금액 표시는 Source Map에서 `parameter_status=resolved` 이고 `requires_manual_numeric_verification=false`인 값에 한해서만 사용자에게 표시됩니다.
