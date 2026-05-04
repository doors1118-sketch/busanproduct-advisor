# Manual PDF Metadata Watch Policy

## 1. 대상
법제처 API로 원문 자동 수집이 불가능하지만, `active_for_rule=true`이면서 `official_url`이 존재하는 PDF manual 원천입니다.

현재 대상 (2건):
1. **지방자치단체 입찰 및 계약집행기준** (행정안전부 예규)
2. **지방자치단체 입찰시 낙찰자 결정기준** (행정안전부 예규)

## 2. 이중 주기 정책 (Dual-Frequency)

| 작업 유형 | 주기 | 방법 | 자동화 |
|---|---|---|---|
| **메타데이터 변경 감지** | Weekly | `official_url` 접속하여 시행일·개정일·공포번호 변경 여부 확인 | 반자동 (URL 접근 가능 시) |
| **원문 PDF Refresh** | Monthly 또는 수시 | 행안부 사이트에서 PDF 재다운로드 → 텍스트 추출 → hash 비교 | 수동 |

## 3. Manifest 필드 매핑

```json
{
  "source_refresh_method": "pdf_manual",
  "metadata_watch_enabled": true,
  "metadata_watch_frequency": "weekly",
  "full_text_refresh_frequency": "monthly",
  "law_api_target": "none"
}
```

## 4. 감지 시 처리 흐름
1. 메타데이터(시행일 등) 변경 감지 → `legal_interpretation_impact_queue`에 등록
2. 원문 PDF 변경 확인 필요 표시 → 수동 다운로드 대기
3. PDF 재다운로드 후 텍스트 추출 → `full_text_hash` 비교
4. 변경 시 `diff_legal_versions` → `classify_legal_update_impact` 파이프라인 진입
5. `active_for_rule=true`이므로 impact level 기준 Fail-Closed 적용

## 5. 주의사항
- 이 2건은 지방계약의 핵심 기준이므로 개정 감지 누락은 심각한 리스크입니다.
- 메타데이터 변경만으로도 `review_queue`에 등록하여 담당자가 인지할 수 있게 합니다.
- 원문 PDF refresh 없이 메타데이터 변경만 감지된 경우에도 "현행성 확인 필요" 경고를 붙입니다.
