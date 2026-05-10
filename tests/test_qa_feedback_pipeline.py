from pathlib import Path

from app import qa_test_logger
from scripts.build_intent_rag_feedback_candidates import build_candidates


def test_qa_log_returns_id_and_feedback_is_saved(tmp_path, monkeypatch):
    qa_dir = tmp_path / "qa_test_logs"
    fb_dir = tmp_path / "qa_feedback"
    monkeypatch.setattr(qa_test_logger, "_LOG_DIR", str(qa_dir))
    monkeypatch.setattr(qa_test_logger, "_FEEDBACK_DIR", str(fb_dir))

    qa_log_id = qa_test_logger.save_qa_log(
        question="CCTV 구매 절차 말고 업체 후보만 보고 싶어",
        answer="후보를 정리했습니다.",
        latency_ms=1200,
        extra_meta={"intent_rag_confidence": 0.86},
    )
    feedback_id = qa_test_logger.save_qa_feedback(
        qa_log_id=qa_log_id,
        rating=2,
        satisfied=False,
        issue_tags=["의도틀림"],
        comment="절차 설명이 섞였음",
    )

    assert qa_log_id.startswith("qa_")
    assert feedback_id.startswith("fb_")
    assert qa_test_logger.get_qa_logs(limit=10)[0]["qa_log_id"] == qa_log_id
    assert qa_test_logger.get_qa_feedback(limit=10)[0]["qa_log_id"] == qa_log_id


def test_feedback_candidate_builder_marks_low_rating(tmp_path, monkeypatch):
    qa_dir = tmp_path / "qa_test_logs"
    fb_dir = tmp_path / "qa_feedback"
    data_dir = tmp_path / "data"
    qa_dir.mkdir(parents=True)
    fb_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    date = "20260509"
    qa_log_id = "qa_test_001"
    (qa_dir / f"qa_log_{date}.jsonl").write_text(
        '{"qa_log_id":"qa_test_001","question":"예산은 6천이고 노트북 구매 예정인데 계약방법 알려줘","answer":"응답","latency_ms":45000,"tool_call_count":9,"extra":{"intent_rag_confidence":0.2}}\n',
        encoding="utf-8",
    )
    (fb_dir / f"qa_feedback_{date}.jsonl").write_text(
        '{"feedback_id":"fb_test_001","qa_log_id":"qa_test_001","rating":1,"satisfied":false,"issue_tags":["응답느림"],"comment":"느림"}\n',
        encoding="utf-8",
    )

    import scripts.build_intent_rag_feedback_candidates as builder

    monkeypatch.setattr(builder, "QA_LOG_DIR", qa_dir)
    monkeypatch.setattr(builder, "QA_FEEDBACK_DIR", fb_dir)

    candidates = build_candidates(date=date)

    assert len(candidates) == 1
    assert candidates[0]["qa_log_id"] == qa_log_id
    assert "low_user_rating" in candidates[0]["candidate_reasons"]
    assert "slow_latency_over_30s" in candidates[0]["candidate_reasons"]
    assert candidates[0]["review_status"] == "needs_review"
    assert candidates[0]["suggested_record"]["intent_labels"]
