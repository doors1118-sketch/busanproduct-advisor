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
    route_review_section: AnswerSection
    item_eligibility_section: AnswerSection
    procedure_guidance_section: AnswerSection
    candidate_table_section: CandidateTableSection
    caution_section: AnswerSection
    
    # 2. 법적 책임 면책 고지
    disclaimer: str
    
    # 3. 최종 출력물
    rendered_markdown: str
    
    # 4. 방어 로직 (금지 표현 스캔 상태)
    forbidden_phrase_scan_passed: bool = False
    blocked_phrases_found: List[str] = field(default_factory=list)
