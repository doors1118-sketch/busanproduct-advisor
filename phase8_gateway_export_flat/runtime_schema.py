"""
Phase 10.4: Runtime Schema

챗봇 런타임 파이프라인 입출력 데이터 구조.
"""
from typing import Any, Optional, List
from pydantic import BaseModel, Field
from app.router.intent_schema import RouterResult
from app.answer_builder.schema import AnswerBuilderOutput


class ChatbotRuntimeRequest(BaseModel):
    user_query: str
    mock_gemini_response: Optional[dict] = None
    user_context: Optional[dict] = None
    runtime_options: Optional[dict] = None


class RuntimeStageResult(BaseModel):
    stage_name: str
    status: str  # success, skipped, degraded, failed
    skipped: bool = False
    reason: Optional[str] = None


class ChatbotRuntimeResponse(BaseModel):
    user_query: str
    router_result: RouterResult
    gateway_response: Optional[Any] = None
    decision_context: Optional[Any] = None
    answer_output: AnswerBuilderOutput
    runtime_stages: List[RuntimeStageResult] = Field(default_factory=list)
    runtime_status: str = "success"  # success, degraded, failed
    fallback_applied: bool = False
    errors: List[str] = Field(default_factory=list)
