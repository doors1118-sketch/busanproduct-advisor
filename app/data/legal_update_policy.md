# Legal DB Update Policy

본 문서는 Rule Engine이 참조하는 법령 및 행정규칙 데이터(Source Layer)의 현행화를 관리하되, 시스템 장애를 예방하기 위한 안전장치(Review Queue)를 포함하는 업데이트 파이프라인의 원칙과 배포 체계를 명문화합니다.

## 1. 기본 원칙 (Separation of Concerns)
업데이트는 한 번에 모두 자동으로 반영되지 않습니다.
1. **Source Layer Update**: 법령 원문의 개정, 시행일 변경, 조문 추가/삭제 감지 및 수집.
2. **Interpretation Layer Update**: Rule Engine이 특정 법령을 어떻게 인용할지에 대한 메타데이터(`activation_mode`, `active_for_rule` 등) 갱신.
3. **Rule Layer Update**: Rule Engine 파이프라인(RAG, Answer Builder)에 반영.

> **핵심 원칙**: 법령의 원문(Source)이 개정되었다고 해서 해당 법령의 해석(Interpretation)이나 Rule이 맹목적으로 자동 갱신되어서는 안 됩니다. 시스템은 변경을 자동 감지하되, '계약방식, 금액, 예외조항' 등 해석에 심대한 영향을 미치는 사안은 반드시 `Review Queue`를 거쳐 수동 승인되어야 합니다 (Fail-Closed).

## 2. 업데이트 주기 및 대상
매일 무거운 전체 원문 수집을 방지하기 위해 빈도(Frequency)를 차등화합니다.

- **Daily (매일)**: 핵심 계약 기준들의 '해시/메타데이터 변경 여부'만 가볍게 체크.
  - 대상: `active_for_rule=true`, `active_for_procedure=true`, 조달청 기준, 국가/지방계약 핵심기준, 한시적 특례 고시(`time_bounded`)
- **Weekly (주 1회)**: 우선순위가 낮은 후보군 점검.
  - 대상: `candidate_needs_review`, 계약예규 후보 등
- **Monthly (월 1회) / 수시**: 수동 관리 대상 점검.
  - 대상: 기관별 조례/내부규정, PDF 수동 원천, 전체 DB 정합성 감사

## 3. 업데이트 파이프라인 단계별 동작
1. **Lightweight Change Check**: 법제처 API나 수동 원천으로부터 메타데이터/해시만 비교하여 변경 여부 판별.
2. **Selective Refresh**: 해시가 달라진(개정된) 법령에 한해서만 전문 재수집 및 조문 단위 분할 수행.
3. **Diff 생성**: 구 버전과 신 버전의 조문 차이(Diff) 분석. (`metadata_only`, `article_added`, `procedure_changed` 등 분류)
4. **Impact Classifier**: 
   - `low` (오탈자 등): 자동 갱신 권장
   - `medium` (절차/서류 변경): Review Queue 진입
   - `high` / `critical` (금액, 낙찰자 결정방식 변경 등): Review 필수, 임시로 `fail_closed_until_review` 처리하여 답변 금지.
5. **Review Queue**: 관리자가 해석에 대한 판단을 내리고 `activation_mode` 등을 유지/변경.

## 4. DB 환경 및 배포 정책
운영 중인 데이터베이스에 업데이트를 직접 덮어쓰지 않습니다.
- `legal_db_current.sqlite`: 현재 운영(Production) 참고용.
- `legal_db_vX_Y.sqlite`: 기준선(Baseline) 스냅샷.
- `legal_db_vX_Y_staging.sqlite`: 백그라운드에서 업데이트 파이프라인이 돌고 검증하는 환경.
- **배포 프로세스**: Staging 업데이트 완료 → Validation 검증(Orphan 제로, 판단오류 제로) → 최소 8개 시나리오 Regression Test → 승인 후 Current 교체.
