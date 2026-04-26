# CHANGED FILES

## 새로 생성된 파일
- `app/policies/model_routing_policy.py`: 위험도(low/high)에 따른 Pro/Flash 동적 라우팅 결정 및 Fallback 조건(`decide_fallback`) 구현.
- `run_tc8_routing.py`: TC8(모델 라우팅 정적 정책) 검증 테스트 스크립트.

## 수정된 파일 및 주요 변경 요약

### 1. `app/gemini_engine.py`
- 모델 선택을 `classify_risk()` 기반으로 전환하여 `model_selected`, `model_used` 분리.
- `_finalize_answer` 단계에서 라우팅 및 Fallback 관련 메타데이터(`legal_judgment_requested`, `flash_company_table_fallback_allowed` 등)를 로깅에 주입.

### 2. `app/policies/candidate_policy.py` & `candidate_formatter.py`
- 조달등록 부산업체, 종합쇼핑몰 등록 부산업체, 정책기업(여성기업 등), 혁신제품, 우선구매 제품 등 5종 후보군 분류 체계 구현.
- `classify_candidate_types`, `format_candidate_tables`, `split_policy_companies` 등 핵심 함수 구현을 통해 구조화된 표기 강제 및 법적 단정 방지 문구 추가.

### 3. `run_staging_verification.py` / `run_tc7_expanded.py`
- `pro_call_executed`, `model_used`, `fallback_used` 등의 런타임 추적 메타데이터를 확인하도록 검증 스크립트 고도화.
- TC7 관련 스키마 검증 로직 확장.

### 4. `.env.example`
- 라우팅 정책 활성화를 위한 설정값 추가:
  ```env
  ROUTER_MODEL=gemini-2.5-flash
  GEMINI_MODEL=gemini-2.5-pro
  FALLBACK_MODEL=gemini-2.5-flash
  MODEL_ROUTING_MODE=risk_based
  ```
