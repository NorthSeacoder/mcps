from uuid import uuid4

from hermes_db_mcp.contracts import (
    MAX_WORKFLOW_ARTIFACT_LIMIT,
    MAX_WORKFLOW_INLINE_CONTENT_BYTES,
    validate_workflow_artifact_payload,
    validate_workflow_artifact_query,
    validate_workflow_run_payload,
)


def test_validate_workflow_run_payload_requires_identity_and_state():
    assert validate_workflow_run_payload(run_id="run-1", phase="draft", status="running") is None

    err = validate_workflow_run_payload(run_id="", phase="draft", status="running")
    assert err["error"] == "missing_required_field"
    assert err["field"] == "run_id"


def test_validate_workflow_artifact_payload_accepts_inline_markdown():
    err = validate_workflow_artifact_payload(
        run_id="run-1",
        stage="draft",
        type="draft",
        name="draft",
        content_hash="sha256:abc",
        content_size_bytes=12,
        content_text="# Draft",
        content_ref=None,
        topic_id=str(uuid4()),
    )
    assert err is None


def test_validate_workflow_artifact_payload_requires_content():
    err = validate_workflow_artifact_payload(
        run_id="run-1",
        stage="draft",
        type="draft",
        name="draft",
        content_hash="sha256:abc",
        content_size_bytes=12,
        content_text=None,
        content_ref=None,
    )
    assert err["error"] == "content_missing"


def test_validate_workflow_artifact_payload_rejects_large_inline_content():
    err = validate_workflow_artifact_payload(
        run_id="run-1",
        stage="draft",
        type="draft",
        name="draft",
        content_hash="sha256:abc",
        content_size_bytes=MAX_WORKFLOW_INLINE_CONTENT_BYTES + 1,
        content_text="x" * (MAX_WORKFLOW_INLINE_CONTENT_BYTES + 1),
        content_ref=None,
    )
    assert err["error"] == "content_too_large"


def test_validate_workflow_artifact_query_requires_filter_or_explicit_limit():
    err = validate_workflow_artifact_query(explicit_limit=False)
    assert err["error"] == "invalid_filter"

    assert validate_workflow_artifact_query(run_id="run-1") is None
    assert validate_workflow_artifact_query(limit=1, explicit_limit=True) is None

    err = validate_workflow_artifact_query(
        limit=MAX_WORKFLOW_ARTIFACT_LIMIT + 1,
        explicit_limit=True,
    )
    assert err["error"] == "invalid_field"
    assert err["field"] == "limit"
