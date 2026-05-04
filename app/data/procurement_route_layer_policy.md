# Procurement Route Layer Policy (v0.1.3)

본 정책은 조달청 계약 경로(pps_delegated_contract 등)를 이용할 때, 기본 관할 법령(국가계약법, 지방계약법 등) 위에 조달청 절차 기준을 추가 적용(이중 라우팅)하는 정책을 명문화합니다.

## 1. 이중 라우팅 (Dual Routing) 구조
계약 근거 판단은 수요기관의 `buyer_type`에 따른 기본 법령체계를 우선하며, `procurement_route`가 조달청일 경우 조달청 기준이 `Route Layer`로서 병합(Overlay) 적용됩니다.
- 조달청 기준은 지방자치단체나 국가기관의 자체 계약 법령을 **완전히 대체하지 않습니다**.
- 조달청 경로라 할지라도 수요기관의 기본 조례/지침은 함께 검토되어야 합니다.

## 2. Activation Mode 발동 조건
- `procurement_route_required`: 조달청 경로가 식별되었을 때 강제로 발동됩니다. (단순 지방/국가 자체 계약 질문 시 절대 발동 금지)
- `procurement_route_and_subtype_required`: 조달청 경로 + 특정 분야(공공주택, 건설엔지니어링 등)가 교집합으로 일치할 때만 발동됩니다.

## 3. Fail-Closed 원칙
`required_slots`에 지정된 슬롯이 질문에 충족되지 않으면 해당 법령 소스는 활성화되지 않습니다.
