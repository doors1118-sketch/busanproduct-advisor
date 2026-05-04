# Legal Diff Engine Plan v0.1.1

본 문서는 법령 원문의 구버전과 신버전 간 조문 단위 차이(Diff)를 추출하는 엔진의 설계 계획입니다.

## 1. Diff 엔진 동작 원칙
- **입력**: `old_version_hash`(현 DB에 저장된 해시), `new_version_hash`(재수집 후 계산된 해시)
- **비교 단위**: 법령 전체(`full_text_hash`)와 개별 조문(`article_hash`)의 2단계 비교
- **비교 불가 시**: `new_version_hash`가 `None`이면 diff를 수행하지 않고 `skipped` 처리

## 2. Diff 유형 분류
| diff_type | 의미 |
|---|---|
| `none` | 해시 일치, 변경 없음 |
| `metadata_only` | 시행일·공포번호만 변경 |
| `article_text_changed` | 기존 조문의 텍스트 변경 |
| `article_added` | 신규 조문 추가 |
| `article_deleted` | 기존 조문 삭제 |
| `amount_threshold_changed` | 금액 기준 변경 |
| `date_period_changed` | 적용기간/유효기간 변경 |
| `definition_changed` | 용어 정의 변경 |
| `procedure_changed` | 절차적 규정 변경 |
| `relation_changed` | 타 법령 참조 관계 변경 |
| `unknown_change` | 미분류 변경 |

## 3. 조문별 해시 비교 (Article-Level Diff) 설계

### 3.1 해시 생성 방식
```
article_hash = SHA256(article_no + article_title + article_body_text)
```
- 공백·줄바꿈을 정규화한 뒤 해싱
- 별표(附表)가 포함된 경우 별표 내용도 해시에 포함

### 3.2 비교 로직
1. 전체 `full_text_hash` 비교 → 일치하면 즉시 `none` 반환
2. 불일치 시, 조문 목록을 순회하며 `article_hash` 비교
3. 구버전에만 존재하는 조문 → `article_deleted`
4. 신버전에만 존재하는 조문 → `article_added`
5. 양쪽 모두 존재하나 해시 불일치 → `article_text_changed`

### 3.3 민감 키워드 태깅
변경된 조문의 텍스트에서 민감 키워드(금액, 수의계약, 낙찰자 결정 등)를 자동 스캔하여 `classify_legal_update_impact` 모듈에 전달합니다.

## 4. 현재 상태 (v0.1.1)
- 원문 재수집 파이프라인이 아직 구축되지 않았으므로, `new_version_hash`는 항상 `None`
- 따라서 모든 diff 요청은 `skipped` 상태로 반환
- 향후 `refresh_changed_legal_sources.py` 구현 후 실제 diff가 동작 가능
