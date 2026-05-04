from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AnswerSection:
    title: str
    content: str
    bullets: List[str] = field(default_factory=list)

@dataclass
class CandidateTableRow:
    company_name_masked: str
    location: str
    business_type: Optional[str] = None
    enrichment_info: Optional[str] = None  # 직생/중기간제품 증명 보조정보 렌더링용

@dataclass
class CandidateTableSection:
    title: str
    description: str
    rows: List[CandidateTableRow] = field(default_factory=list)

@dataclass
class AnswerBuilderOutput:
    # 1. 필수 응답 섹션들
    summary_section: AnswerSection
    caution_section: AnswerSection
    
    # 2. 법적 책임 면책 고지
    disclaimer: str
    
    # 3. 최종 출력물
    rendered_markdown: str
    
    # 4. 선택적 섹션들
    local_purchase_support_review_section: Optional[AnswerSection] = None
    route_review_section: Optional[AnswerSection] = None
    item_eligibility_section: Optional[AnswerSection] = None
    procedure_guidance_section: Optional[AnswerSection] = None
    candidate_table_section: Optional[CandidateTableSection] = None
    
    # 5. 방어 로직 (금지 표현 스캔 상태)
    forbidden_phrase_scan_passed: bool = False
    blocked_phrases_found: List[str] = field(default_factory=list)
    fallback_applied: bool = False
