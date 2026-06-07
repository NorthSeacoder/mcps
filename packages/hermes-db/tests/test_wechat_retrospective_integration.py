from datetime import date

import pytest

from hermes_db_mcp.repositories import (
    wechat_article_repo,
    wechat_retrospective_repo,
    workflow_repo,
)


async def _cleanup(db_pool, *, account: str, run_id: str) -> None:
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM hermes.learning_candidates WHERE account = $1",
            account,
        )
        await conn.execute(
            "DELETE FROM hermes.topic_optimization_suggestions WHERE account = $1",
            account,
        )
        await conn.execute(
            "DELETE FROM hermes.wechat_retrospective_reports WHERE account = $1",
            account,
        )
        await conn.execute(
            "DELETE FROM hermes.topic_performance WHERE account = $1",
            account,
        )
        await conn.execute(
            """
            DELETE FROM hermes.wechat_article_external_refs
            WHERE article_id IN (
                SELECT article_id FROM hermes.wechat_articles
                WHERE account = $1
            )
            """,
            account,
        )
        await conn.execute("DELETE FROM hermes.wechat_articles WHERE account = $1", account)
        await conn.execute(
            "DELETE FROM hermes.wechat_workflow_runs WHERE run_id = $1",
            run_id,
        )


@pytest.mark.asyncio
async def test_wechat_retrospective_roundtrip(db_pool):
    account = "pytest-retrospective-account"
    run_id = "pytest-wechat-retrospective-run"

    await _cleanup(db_pool, account=account, run_id=run_id)

    try:
        await workflow_repo.upsert_run(
            db_pool,
            run_id=run_id,
            phase="retrospective",
            current_stage="analytics",
            status="completed",
            dry_run=False,
            metadata={"source": "pytest"},
        )
        article, _created = await wechat_article_repo.upsert_article(
            db_pool,
            publication_idempotency_key="pytest-retrospective-article",
            account=account,
            run_id=run_id,
            status="published",
            title="Retrospective smoke article",
            published_url="https://mp.weixin.qq.com/s/pytest-retrospective",
            metadata={"source": "pytest"},
        )

        performance = await wechat_retrospective_repo.upsert_topic_performance(
            db_pool,
            {
                "account": account,
                "article_id": article["article_id"],
                "stat_date": date(2026, 6, 7),
                "window_label": "D+7",
                "scoring_version": "wechat-retro-v1",
                "baseline_version": "account-rolling-v1",
                "normalized_score": 86.4,
                "read_score": 90,
                "engagement_score": 80,
                "share_score": 88,
                "conversion_score": 70,
                "confidence": 0.82,
                "metric_snapshot_ids": [],
                "baseline_snapshot": {"sample": 12},
                "diagnosis": {"summary": "above baseline"},
                "evidence_refs": {"article_id": str(article["article_id"])},
                "warnings": [],
            },
        )
        performance_again = await wechat_retrospective_repo.upsert_topic_performance(
            db_pool,
            {
                "account": account,
                "article_id": article["article_id"],
                "stat_date": date(2026, 6, 7),
                "window_label": "D+7",
                "scoring_version": "wechat-retro-v1",
                "baseline_version": "account-rolling-v1",
                "normalized_score": 88.0,
                "confidence": 0.84,
            },
        )

        assert performance_again["performance_id"] == performance["performance_id"]
        assert performance_again["normalized_score"] == 88.0

        listed_performance = await wechat_retrospective_repo.list_topic_performance(
            db_pool,
            account=account,
            article_id=article["article_id"],
            window_label="D+7",
            scoring_version="wechat-retro-v1",
        )
        assert listed_performance["total"] == 1
        assert listed_performance["items"][0]["performance_id"] == performance["performance_id"]

        report = await wechat_retrospective_repo.create_wechat_retrospective_report(
            db_pool,
            {
                "account": account,
                "report_type": "article",
                "period_start": date(2026, 6, 1),
                "period_end": date(2026, 6, 7),
                "article_id": article["article_id"],
                "scoring_version": "wechat-retro-v1",
                "generation_mode": "structured_only",
                "status": "completed",
                "sample_size": 1,
                "performance_ids": [str(performance["performance_id"])],
                "summary": {"normalized_score": 88.0},
                "narrative_markdown": "Smoke retrospective.",
                "high_performing_themes": [],
                "low_performing_themes": [],
                "title_patterns": [],
                "recommendations": [],
                "evidence_refs": {"performance_id": str(performance["performance_id"])},
                "warnings": [],
            },
        )

        loaded_report = await wechat_retrospective_repo.get_wechat_retrospective_report(
            db_pool,
            report["report_id"],
        )
        listed_reports = await wechat_retrospective_repo.list_wechat_retrospective_reports(
            db_pool,
            account=account,
            report_type="article",
            article_id=article["article_id"],
        )

        assert loaded_report["report_id"] == report["report_id"]
        assert listed_reports["total"] == 1

        suggestions = await wechat_retrospective_repo.create_topic_optimization_suggestions(
            db_pool,
            account=account,
            report_id=report["report_id"],
            items=[
                {
                    "suggestion_type": "ranking_hint",
                    "target_kind": "mother_theme",
                    "target_key": "pytest-theme",
                    "current_value": {"priority": "B"},
                    "proposed_value": {"boost": 0.2},
                    "rationale": "Smoke-tested theme outperformed baseline.",
                    "confidence": 0.76,
                    "evidence_refs": {"report_id": str(report["report_id"])},
                }
            ],
        )
        suggestion = suggestions[0]
        reviewed_suggestion = (
            await wechat_retrospective_repo.review_topic_optimization_suggestion(
                db_pool,
                suggestion_id=suggestion["suggestion_id"],
                review_status="approved",
                reviewed_by="pytest",
                review_note="approved for smoke",
            )
        )
        ranking_hints = await wechat_retrospective_repo.list_approved_topic_ranking_hints(
            db_pool,
            account=account,
            target_kind="mother_theme",
            target_key="pytest-theme",
        )

        assert reviewed_suggestion["review_status"] == "approved"
        assert ranking_hints["total"] == 1
        assert ranking_hints["items"][0]["suggestion_id"] == suggestion["suggestion_id"]

        candidates = await wechat_retrospective_repo.create_learning_candidates(
            db_pool,
            account=account,
            source_report_id=report["report_id"],
            items=[
                {
                    "domain": "wechat",
                    "source_suggestion_ids": [str(suggestion["suggestion_id"])],
                    "candidate_type": "topic_strategy",
                    "scope": {"account": account},
                    "trigger_conditions": {"min_sample_size": 1},
                    "proposed_policy": {"boost": 0.2},
                    "confidence": 0.78,
                    "evidence_refs": {"suggestion_id": str(suggestion["suggestion_id"])},
                }
            ],
        )
        candidate = candidates[0]
        reviewed_candidate = await wechat_retrospective_repo.review_learning_candidate(
            db_pool,
            candidate_id=candidate["candidate_id"],
            status="approved",
            reviewed_by="pytest",
            review_note="approved for smoke",
            policy_id="pytest-policy",
        )
        listed_candidates = await wechat_retrospective_repo.list_learning_candidates(
            db_pool,
            account=account,
            domain="wechat",
            status="approved",
        )

        assert reviewed_candidate["status"] == "approved"
        assert reviewed_candidate["policy_id"] == "pytest-policy"
        assert listed_candidates["total"] == 1
        assert listed_candidates["items"][0]["candidate_id"] == candidate["candidate_id"]
    finally:
        await _cleanup(db_pool, account=account, run_id=run_id)
