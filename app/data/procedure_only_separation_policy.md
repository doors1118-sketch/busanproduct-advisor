# Procedure Only Separation Policy (v0.1.3a)

심의위원회 구성, 운영규정, 물가변동 처리규정, 제안서 평가절차 등은 계약의 '가능 여부(성립 여부)' 자체를 판단하는 근거가 아닙니다.
따라서 Rule Engine의 핵심 판단 로직에서는 철저히 배제되어야 합니다.

## Separation Rules
1. **`active_for_rule = false`**: 이 속성에 의해 해당 규정들은 Rule Engine의 적격성(Eligibility) 판단 쿼리에서 자동 제외됩니다.
2. **`active_for_procedure = true`**: 계약 체결 후 사후관리, 위원회 개최 등 절차적 체크리스트를 위한 보조 쿼리에서만 이 규정들이 호출됩니다.
3. **`judgment_eligible = false`**: 어떠한 경우에도 계약 방식, 낙찰자 결정 가능 여부를 확정하는 데 쓰일 수 없음을 강제합니다.
