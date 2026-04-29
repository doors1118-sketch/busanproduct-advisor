# 부산 공공조달 AI 챗봇 — 운영 배포 전 체크리스트

## 1. 기준선 정보
- **NCP E2E status**: PASS
- **Production deployment**: HOLD
- **FastAPI API smoke**: PASS
- **Streamlit UI**: 기존 유지
- **laws RAG**: SUCCESS, 808 docs
- **manuals RAG**: SUCCESS, split_collections, 3,361 docs
- **innovation index**: SUCCESS, 771 products
- **staging verification**: PASS
- **TC7/G-RT**: PASS
- **false_pass_detected**: false
- **forbidden_patterns_remaining_after_rewrite**: []
- **legal_conclusion_allowed**: false
- **contract_possible_auto_promoted**: false

## 2. 배포 전 필수 확인 항목

### A. Git / 코드 기준선
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| Git | 최신 remote commit 확인 | 원격 레포지토리 `main` 브랜치와 로컬 일치 | PASS | |
| Git | git status clean | `working tree clean` 상태 확인 | PASS | |
| Git | 운영 배포 대상 commit hash 기록 | 최신 배포 대상 commit hash 명시 | TODO | |
| Git | NCP E2E PASS artifact 존재 | `ncp_e2e_final_result.json` 등 최종 테스트 기록 파일 존재 | PASS | |
| 보안 | `.env` 미커밋 확인 | `.gitignore` 적용 및 저장소 내 `.env` 파일 부재 | PASS | |
| 보안 | logs/artifacts 불필요 파일 미커밋 확인 | 테스트 임시 파일 및 시스템 로그 노출 여부 | PASS | |

### B. 환경변수 / 비밀정보
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| 환경변수 | GEMINI_API_KEY 존재 여부 | present (값 직접 출력 금지) | TODO | |
| 환경변수 | LAW_API_OC / Korean Law MCP Key | present (값 직접 출력 금지) | TODO | |
| 환경변수 | ODCLOUD_API_KEY 존재 여부 | present (값 직접 출력 금지) | TODO | |
| 환경변수 | GEMINI_MODEL 확인 | `gemini-2.5-pro` 등 정상 모델 할당 | TODO | |
| 환경변수 | FALLBACK_MODEL 확인 | `gemini-2.5-flash` 등 정상 모델 할당 | TODO | |
| 환경변수 | PROMPT_MODE 확인 | `dynamic_v1_4_4` 또는 `legacy` 적용 여부 | TODO | |
| 환경변수 | CHROMA_DIR 계열 경로 확인 | `CHROMA_DIR`, `CHROMA_LAWS_DIR` 등 경로 설정 정상 | TODO | |
| 제약 | `.env` / API key 출력 금지 | 운영/테스트 스크립트 상에 값 노출 절대 금지 | PASS | |

### C. RAG / 데이터 상태
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| RAG | laws collection count 확인 | `808` docs 전후 | PASS | |
| RAG | manuals split collection count 확인 | `3361` docs 전후 | PASS | |
| RAG | innovation product count 확인 | `771` products 전후 | PASS | |
| RAG | manuals retrieval smoke query 확인 | 임베딩 함수 기반 검색 정상 작동 | TODO | |
| 제약 | raw chromadb query 사용 금지 | 앱 embedding function 경유 smoke test만 인정 | PASS | |
| 제약 | `app/.chroma_laws` 디렉터리 상태 | unused legacy dir로 기록, **삭제 금지** | PASS | |

### D. API 서버
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| API | GET `/health` 정상 | `status: ok` | PASS | |
| API | GET `/version` 정상 | `commit_hash` 일치 여부 | PASS | |
| API | GET `/rag/status` 정상 | 각 컬렉션 `SUCCESS` | PASS | |
| API | POST `/chat` 정상 | 질의응답 정상 응답 | PASS | |
| 메타데이터 | `production_deployment=HOLD` 반환 | 응답 JSON 내 `HOLD` 상태 유지 확인 | PASS | |
| 메타데이터 | raw traceback 노출 없음 | 시스템 에러 메시지 사용자 노출 방지 | PASS | |
| 메타데이터 | raw API error 노출 없음 | `RESOURCE_EXHAUSTED` 등 외부 에러 방어 | PASS | |
| 메타데이터 | safety metadata 포함 | 실제 안전 상태값 응답에 포함 | PASS | |

### E. Streamlit UI
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| UI | 기존 Streamlit port 8502 동작 확인 | UI 접근 정상 | TODO | |
| UI | 기존 UI와 FastAPI API 병행 구조 명시 | 두 서비스가 분리되어 병행 동작함 | PASS | |
| 제약 | Streamlit 재시작 금지 | 별도 승인 전까지 `law-chatbot.service` 재시작 금지 | HOLD | |
| 제약 | 운영 서비스 스크립트 수정 금지 | `/opt/busan` 내부 직접 수정 금지 | HOLD | |

### F. Safety / 법적 결론
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| Safety | candidate_table_source | `server_structured_formatter` 또는 `none` | PASS | |
| Safety | legal_conclusion_allowed | 직접적 근거 없으면 강제 `false` | PASS | |
| Safety | contract_possible_auto_promoted | 전면 `false` | PASS | |
| Safety | forbidden_patterns_remaining | 배열 크기 0 (`[]`) 보장 | PASS | |
| 보안 | 사업자등록번호 / 대표자명 노출 없음 | 마스킹 또는 미제공 원칙 | TODO | |
| 보안 | API key / `.env` 노출 없음 | 응답에 환경변수 유출 검증 | PASS | |
| 보안 | 내부 프롬프트/traceback 노출 없음 | 프롬프트 누출 공격(prompt leak) 방어 | TODO | |

### G. QA
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| QA | QA 대표 질문 실행 준비 | `docs/QA_SCENARIOS_20260429.md` 기반 | PASS | |
| QA | 최소 10개 smoke QA 통과 | 운영 반영 전 최소 필수 질문 통과 | TODO | |
| QA | 전체 30개 QA 권장 | 운영 전 Full set QA 수행 권장 | TODO | |
| QA | high-risk legal fail-closed 확인 | 고위험군 질문에 대한 판단 유보 응답 확인 | TODO | |
| QA | adversarial 질문 금지표현 차단 확인 | 유도 질문에 단정적 표현 방어 확인 | TODO | |

### H. 운영 명령 승인
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| 인가 | `/opt/busan` 직접 수정 금지 | 수동 코드 패치 엄격히 금지 | HOLD | |
| 인가 | `systemctl restart` 금지 | 서버 관리자 승인 전 서비스 재기동 금지 | HOLD | |
| 인가 | `pm2 restart` 금지 | 백그라운드 프로세스 무단 재기동 금지 | HOLD | |
| 인가 | `rm -rf` / `git reset --hard` 금지 | 무분별한 파일/코드 삭제 금지 | HOLD | |
| 인가 | 운영 DB/Chroma 삭제 금지 | 기존 운영 RAG 데이터 보존 | HOLD | |
| 인가 | 운영 ChromaDB symlink 금지 | 레거시 데이터와의 연결 안정성 파괴 방지 | HOLD | |
| 인가 | 운영 재시작 승인 절차 | 별도 운영자 승인 후 수행 | HOLD | |

### I. 롤백
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| 롤백 | 현재 운영 commit hash 기록 | 이슈 발생 시 복구 기준점 | TODO | |
| 롤백 | 신규 배포 commit hash 기록 | 배포 버전 추적 | TODO | |
| 롤백 | 이전 배포본 복구 방법 기록 | `git checkout <hash>` 및 의존성 복구 절차 | TODO | |
| 롤백 | systemd rollback 방법 (문서화 전용) | 실행하지 않고 예시 스크립트만 문서화 | TODO | |
| 백업 | RAG/Chroma 백업 경로 기록 | 장애 시 `app/.chroma` 데이터 복구 경로 | TODO | |
| 백업 | 데이터 재생성 절차 기록 | Chroma 초기화 시 재적재 스크립트 명시 | TODO | |

### J. 모니터링
| 구분 | 체크 항목 | 기준 | 상태 | 비고 |
|---|---|---|---|---|
| 모니터링 | 응답 latency 기록 | API 응답 시간 추세 로깅 | TODO | |
| 모니터링 | API 503/429 기록 | Gemini/MCP 외부 호출 실패 비율 로깅 | TODO | |
| 모니터링 | `fallback_used` 기록 | Flash 모델로 Fallback된 건수 추적 | TODO | |
| 모니터링 | `result_status=DEGRADED` 기록 | 일부 데이터 조회 지연 발생 비율 로깅 | TODO | |
| 모니터링 | forbidden pattern scanner 결과 | 금지어 검출 빈도 로깅 | TODO | |
| 모니터링 | `false_pass_detected` 기록 | 비정상 PASS 판정 추적 로깅 | TODO | |
| 모니터링 | `/rag/status` 주기 확인 | RAG 데이터 유실 모니터링 체계 점검 | TODO | |

## 3. 운영 배포 승인 조건

아래 조건을 **모두 만족해야** 운영 배포를 승인할 수 있습니다.

- NCP E2E PASS 완료
- FastAPI API smoke PASS 완료
- Streamlit UI smoke PASS 완료
- 대표 QA 30개 중 critical safety failure 0건
- `forbidden_patterns_remaining_after_rewrite` 전부 `[]`
- `legal_conclusion_allowed` 부적절한 `true` 사례 0건
- `contract_possible_auto_promoted` `true` 발생 사례 0건
- 민감정보 (사업자등록번호 등) 노출 0건
- `.env` 및 API key 노출 0건
- 롤백(Rollback) 절차 문서화 완료
- 최종 운영 승인자(담당자) 확인 완료

## 4. 운영 배포 전 금지 상태

아래 항목 중 **단 하나라도 해당하는 경우 배포를 즉시 중단(금지)**합니다.

- NCP E2E FAIL 또는 DEGRADED 원인 미해소 상태
- 결과 JSON (`ncp_e2e_final_result.json`) 없음
- `false_pass_detected=true` 발생
- raw API error (traceback 등)가 사용자 응답에 노출됨
- `final_answer_scanned=false`인데 전체 상태가 PASS로 처리됨
- `candidate_table_source="llm"` (비정형 LLM 표 생성 발견됨)
- RAG source가 누락되었음에도 상태가 SUCCESS로 표시됨
- `.env` 내용 또는 API key가 평문 노출됨
- **Production deployment가 `HOLD` 상태가 아님**

## 5. 최종 상태

```json
{
  "deployment_checklist_created": true,
  "production_deployment": "HOLD",
  "deployment_approved": false,
  "next_step": "Run QA scenarios before production deployment decision"
}
```
