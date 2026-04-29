# 부산 공공조달 AI 챗봇 — 프런트엔드 MVP 스펙

> **Production deployment: HOLD**

## 1. 문서 목적
- 이 문서는 프런트엔드 MVP의 화면, API 연동, 응답 표시, 안전 표시 기준을 정의합니다.
- 본 문서는 운영 배포 승인이 아닙니다.
- **Production deployment는 HOLD** 상태를 유지합니다.

## 2. 사용자 대상
- 부산시 및 구·군 계약 담당자
- 부산시 지방공사·공단 및 출자출연기관 계약 담당자
- 공공기관 지역상품 구매 담당자
- 내부 정책 담당자

## 3. MVP 범위

**포함 (In-Scope):**
- 질문 입력
- 기관 유형 선택
- 답변 표시
- 후보업체 표 표시
- 확인 필요 사항 표시
- RAG 상태 표시
- 안전 상태 표시
- 오류/지연 메시지 표시

**제외 (Out-of-Scope):**
- 로그인/권한 관리
- 관리자 대시보드
- 캐시 기능
- 산하기관 내규 RAG
- 계약 검토 결과 저장
- PDF/엑셀 다운로드
- 운영 배포 자동화

## 4. 화면 구성

**필수 UI 구성요소:**
1. **상단 제목:** 부산 공공조달 AI 챗봇
2. **안내 문구:** "본 시스템은 지역업체 계약 검토를 지원하는 참고용 도구이며, 계약 가능 여부를 자동 확정하지 않습니다."
3. **입력 영역:**
   - 질문 입력창
   - 기관 유형 선택 Dropdown
   - 전송 버튼
4. **상태 영역:**
   - 진행 상태 영역 (Loading indicator)
   - 시스템 상태 영역 (/health, /rag/status)
5. **결과 영역:**
   - 답변 영역
   - 후보표 영역
   - 확인 필요 사항 영역
   - 근거/출처 영역
6. **안전 메타데이터:**
   - 안전 상태 배지 영역

## 5. 진행 상태 메시지

응답 대기 중 아래 상태를 순차적(또는 랜덤 주기)으로 표시하도록 설계하여 사용자 대기 경험을 개선합니다:
1. 질문 분석 중...
2. 지역업체 후보 검색 중...
3. 정책기업·인증제품 확인 중...
4. 법령·매뉴얼 근거 확인 중...
5. 안전 문구 검증 중...
6. 답변 생성 완료!

## 6. API 연동

- **기본 API base URL:** `http://<server>:8001`

**사용 Endpoint:**
- `GET /health`
- `GET /version`
- `GET /rag/status`
- `POST /chat`

**POST /chat 요청 (Request) 예시:**
```json
{
  "message": "CCTV 부산 업체 추천해줘",
  "agency_type": "지방자치단체",
  "history": []
}
```

**POST /chat 응답 (Response) 예시:**
```json
{
  "answer": "...",
  "candidate_table_source": "server_structured_formatter",
  "legal_conclusion_allowed": false,
  "contract_possible_auto_promoted": false,
  "forbidden_patterns_remaining_after_rewrite": [],
  "final_answer_scanned": true,
  "sensitive_fields_detected": [],
  "model_selected": "gemini-2.5-pro",
  "model_decision_reason": "default_model_used",
  "latency_ms": 66920,
  "rag_status": {
    "laws": "SUCCESS",
    "manuals": "SUCCESS",
    "innovation": "SUCCESS"
  },
  "production_deployment": "HOLD"
}
```

## 7. 기관 유형 매핑

프런트엔드 UI 표시값과 API(`agency_type`)에 전달되는 값의 매핑 기준입니다. (현재 백엔드가 인식하는 한글 값 기준)

| UI 표시 | API `agency_type` 전달 값 |
|---|---|
| 미지정 (소속기관 선택) | `null` |
| 부산시/구·군/교육청 | `지방자치단체` |
| 부산시 출자출연기관 | `출자출연기관` |
| 국가기관 | `국가기관` |
| 공기업/준정부기관 | `공기업/준정부기관` |

## 8. 답변 표시 기준

답변 영역은 반드시 다음 순서를 지켜 렌더링해야 합니다:
1. **안전 안내 문구:** (답변 상단에 시각적으로 분리된 경고 박스 등)
2. **후보표:** API가 별도 `structured table`을 제공하지 않는 경우, `answer` 내 포함된 Markdown 표를 렌더링.
3. **확인 필요 사항:** (`answer` 내 텍스트 렌더링)
4. **근거/출처:** 법령/가이드라인 링크 및 조문
5. **추가 확인 권고:** 최종 안내 문구

## 9. 안전 상태 배지

API 응답의 안전 메타데이터 필드에 따라 화면 상단 또는 답변 하단에 Badge를 표시합니다:

- `legal_conclusion_allowed == false` → ⚠️ **법적 결론 유보**
- `contract_possible_auto_promoted == false` → 🔒 **계약 가능 자동확정 없음**
- `forbidden_patterns_remaining_after_rewrite.length == 0` → ✅ **금지표현 검사 통과**
- `candidate_table_source == "server_structured_formatter"` → 📊 **서버 생성 후보표**
- `production_deployment == "HOLD"` → 🛑 **운영 배포 HOLD**

## 10. 오류/DEGRADED 표시

일시적인 장애나 응답 지연 발생 시, **빨간색 치명적 오류 창이 아닌 노란색 경고 창**으로 우회 안내합니다.

**해당 조건:**
- Gemini API 503/429 오류
- MCP (외부 법령 API) Timeout
- RAG 일부 데이터 지연 (`/rag/status` fail 등)
- source_missing 오류
- 기타 `result_status=DEGRADED` 처리

**표시 문구:**
> "일부 외부 API 또는 데이터 조회가 지연되어 답변이 제한될 수 있습니다. 계약 전 관련 법령과 기관 내부 기준을 추가 확인하세요."

## 11. 금지 UI 표현

시스템의 확정적 판단을 암시할 수 있는 표현은 프런트엔드 UI(버튼, 툴팁, 안내문 등) 전체에서 **엄격히 금지**합니다.

**❌ 금지 표현 (절대 사용 금지):**
- 수의계약 가능
- 바로 구매 가능
- 계약 가능
- 구매 가능
- 여성기업이므로 수의계약 가능
- 혁신제품이므로 수의계약 가능

**✅ 허용 표현 (권장):**
- 검토 후보
- 확인 필요
- 법적 적격성 확인 필요
- 수의계약 가능 여부 확인 필요
- 계약 검토 보조

## 12. 응답 시간 UX

AI 및 외부 API 통합 특성상 응답이 길어질 수 있으므로, 지연 시간에 따른 동적 안내 문구를 제공합니다.

- **단순 후보 검색:** 10~25초 예상
- **후보표 + 인증 확인:** 20~45초 예상
- **고위험 법적 질문:** 45~90초 예상

**지연 안내 로직:**
- **30초 경과 시 표시:** "법령·매뉴얼 근거 확인 중입니다. 잠시만 기다려 주세요."
- **90초 경과 시 표시:** "응답이 지연되고 있습니다. 외부 API 또는 모델 응답 지연 가능성이 있습니다."

## 13. 보안/로그 정책

프런트엔드 화면에는 어떠한 경우에도 다음 정보를 노출해서는 안 됩니다:
- 사업자등록번호 원문 (반드시 마스킹 또는 미표시)
- 대표자명 원문 (반드시 마스킹 또는 미표시)
- API Key (클라이언트 단 하드코딩 금지)
- `.env` 파일 내용 및 시스템 환경변수
- 내부 AI 시스템 프롬프트 (System Prompt)
- Raw Traceback (스택 트레이스) 에러 코드

## 14. MVP 완료 기준

프런트엔드 MVP 개발 완료로 인정되기 위한 조건은 다음과 같습니다:
1. `GET /health` 통신 및 상태 표시
2. `GET /rag/status` 통신 및 데이터 적재 현황 표시
3. `POST /chat`을 통한 정상적인 질문 및 답변 응답
4. 답변 내용과 표 형식(Markdown Table)의 정상 렌더링
5. 조건부 안전 배지(Safety Badge) 표시
6. 오류/DEGRADED 상황에서 노란색 경고 안내 메시지 노출 확인
7. **"Production deployment=HOLD"** 상태 명시적 표시
8. 대표 질문 10개에 대한 수동 UI/UX 테스트 통과

## 15. 다음 단계 (Next Steps)

1. **대표 질문 QA 30개 작성 (4번 작업)**
   - 다양한 시나리오(단순 업체 검색, 고위험 법적 판단 요구 등)를 커버하는 질문셋 마련
2. **운영 배포 체크리스트 작성 (5번 작업)**
   - 보안 검수, 서버 설정, 환경변수 구성 등 사전 점검 목록 완성
3. **프런트엔드 구현 진행**
   - 상기 QA 시나리오와 체크리스트가 확정된 후, 본 스펙 문서에 기반하여 프런트엔드 MVP 개발을 시작합니다.
