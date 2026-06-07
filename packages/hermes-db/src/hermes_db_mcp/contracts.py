"""
Topic 写接口契约、常量、校验 helper 和结构化结果模型。

本模块定义:
- 字段白名单和可清空字段集合
- priority/resonance 合法值
- 结构化成功结果和错误模型
- 通用校验 helper
"""

from datetime import date, datetime
from typing import TypedDict, NotRequired
from uuid import UUID


# ============================================================================
# Constants - Field Whitelists
# ============================================================================

# 可通过单条更新接口编辑的字段
EDITABLE_TOPIC_FIELDS = frozenset(
    [
        "title",
        "angle",
        "priority",
        "column_name",
        "resonance",
        "content",
        "revisit_of",
        "mother_theme",
    ]
)

# 可通过批量更新接口编辑的运营字段(不触发 embedding)
BULK_TOPIC_FIELDS = frozenset(
    [
        "priority",
        "resonance",
        "column_name",
    ]
)

# 可通过 clear_fields 清空的 nullable 字段
CLEARABLE_TOPIC_FIELDS = frozenset(
    [
        "angle",
        "column_name",
        "resonance",
        "content",
        "revisit_of",
        "mother_theme",
    ]
)

# Priority 合法值
VALID_PRIORITIES = frozenset(["A", "B", "C"])

# Resonance 合法值
VALID_RESONANCES = frozenset(["高", "中", "低"])

# 批量更新上限
MAX_BATCH_SIZE = 100
MAX_WORKFLOW_INLINE_CONTENT_BYTES = 256 * 1024
DEFAULT_WORKFLOW_ARTIFACT_LIMIT = 50
MAX_WORKFLOW_ARTIFACT_LIMIT = 200
DEFAULT_WECHAT_ARTICLE_LIMIT = 50
MAX_WECHAT_ARTICLE_LIMIT = 200
MAX_WECHAT_ARTICLE_REF_LENGTH = 2048
DEFAULT_WECHAT_ANALYTICS_LIMIT = 50
MAX_WECHAT_ANALYTICS_LIMIT = 200
DEFAULT_WECHAT_RETROSPECTIVE_LIMIT = 50
MAX_WECHAT_RETROSPECTIVE_LIMIT = 200

WECHAT_ARTICLE_STATUSES = frozenset(
    [
        "drafted",
        "published",
        "published_missing_url",
        "publish_reference_missing",
        "archived",
    ]
)

WECHAT_ARTICLE_REF_TYPES = frozenset(
    [
        "published_url",
        "canonical_url",
        "wechat_msg_id",
        "wechat_biz_mid_idx_sn",
        "youmind_ref",
        "publish_target_ref",
        "manual_repair",
        "external_reference",
    ]
)

WECHAT_ARTICLE_PATCH_FIELDS = frozenset(
    [
        "published_url",
        "canonical_url",
        "external_reference",
        "status",
        "published_at",
        "metadata",
    ]
)

WECHAT_ANALYTICS_SOURCES = frozenset(
    [
        "manual_json",
        "manual_csv",
        "manual_xls",
        "wechat_api",
        "browser_automation",
        "manual_patch",
    ]
)

WECHAT_ANALYTICS_RESPONSE_STATUSES = frozenset(
    [
        "completed",
        "completed_with_errors",
        "failed",
        "dry_run",
    ]
)

WECHAT_ANALYTICS_COUNT_FIELDS = frozenset(
    [
        "read_user_count",
        "new_follow_user_count",
        "share_user_count",
        "wow_user_count",
        "like_user_count",
        "favorite_user_count",
        "reward_cents",
        "comment_count",
        "delivered_user_count",
        "account_message_read_user_count",
        "first_share_user_count",
        "total_share_user_count",
        "share_generated_read_user_count",
    ]
)

WECHAT_ANALYTICS_CHANNEL_COUNT_FIELDS = frozenset(
    [
        "read_user_count",
        "share_user_count",
    ]
)

WECHAT_RETROSPECTIVE_REPORT_TYPES = frozenset(
    ["article", "weekly", "monthly", "custom_period"]
)
WECHAT_RETROSPECTIVE_GENERATION_MODES = frozenset(
    ["structured_only", "structured_plus_llm"]
)
WECHAT_RETROSPECTIVE_REPORT_STATUSES = frozenset(
    ["draft", "completed", "completed_with_warnings", "failed"]
)
TOPIC_OPTIMIZATION_SUGGESTION_TYPES = frozenset(
    ["revisit", "cooldown", "priority_adjust", "ranking_hint", "seed_prompt_hint"]
)
TOPIC_OPTIMIZATION_TARGET_KINDS = frozenset(
    ["topic", "mother_theme", "column", "title_pattern", "account"]
)
TOPIC_OPTIMIZATION_REVIEW_STATUSES = frozenset(
    ["pending", "approved", "rejected", "expired", "applied"]
)
TOPIC_OPTIMIZATION_REVIEW_TARGET_STATUSES = frozenset(
    ["approved", "rejected", "expired"]
)
TOPIC_OPTIMIZATION_APPROVED_HINT_STATUSES = frozenset(["approved", "applied"])
LEARNING_CANDIDATE_TYPES = frozenset(
    [
        "topic_strategy",
        "title_strategy",
        "column_strategy",
        "writing_constraint",
        "review_gate",
    ]
)
LEARNING_CANDIDATE_STATUSES = frozenset(
    ["pending_review", "approved", "rejected", "exported_to_policy", "disabled"]
)
LEARNING_CANDIDATE_REVIEW_TARGET_STATUSES = frozenset(
    ["approved", "rejected", "disabled"]
)
RETROSPECTIVE_SCORE_FIELDS = frozenset(
    [
        "normalized_score",
        "read_score",
        "engagement_score",
        "share_score",
        "conversion_score",
    ]
)


# ============================================================================
# Structured Result Models
# ============================================================================


class TopicUpdateResult(TypedDict):
    """单条 topic 更新成功结果"""

    id: str
    updated_fields: list[str]
    embedding_regenerated: bool
    embedding_pending: NotRequired[bool]
    updated_at: str


class BatchTopicUpdateResult(TypedDict):
    """批量 topic 更新成功结果"""

    requested_count: int
    unique_count: int
    matched: int
    updated: int
    updated_fields: list[str]
    not_found_ids: list[str]


class TopicListResult(TypedDict):
    """Topic 列表结果"""

    items: list[dict]
    total: int


class RevisitChainItem(TypedDict):
    """revisit_of 祖先链条目"""

    id: str
    title: str
    status: str
    created_at: str
    published_url: str | None


class RevisitChainResult(TypedDict):
    """revisit_of 祖先链查询结果"""

    items: list[RevisitChainItem]
    truncated: bool


class ToolError(TypedDict):
    """工具错误结果"""

    error: str
    message: NotRequired[str]
    field: NotRequired[str]
    details: NotRequired[dict]


# ============================================================================
# Error Codes
# ============================================================================

ERROR_CODES = {
    # 输入校验错误
    "missing_required_field": "缺少必填字段",
    "invalid_field": "字段值不合法",
    "field_too_long": "字段超长",
    "invalid_uuid": "UUID 格式错误",
    "no_fields_to_update": "未提供任何可更新字段",
    "invalid_clear_field": "不可清空的字段",
    "batch_size_exceeded": "批量更新超限",
    "empty_ids": "批量 ids 为空",
    # 数据状态错误
    "not_found": "记录不存在",
    "invalid_revisit_of_self": "revisit_of 不能指向自身",
    "revisit_target_not_found": "revisit_of 指向的 topic 不存在",
    "invalid_transition": "状态流转不合法",
    # 系统错误
    "embedding_unavailable": "embedding 服务不可用",
    "database_error": "数据库错误",
    # workflow persistence
    "content_too_large": "正文超过 inline 存储上限",
    "content_missing": "content_text 和 content_ref 至少需要一个",
    "artifact_id_conflict": "artifact_id 已存在但内容 hash 不一致",
    "schema_drift": "数据库 schema 未满足工具要求",
    "invalid_filter": "查询过滤条件不合法",
    # wechat article ledger
    "conflict": "记录冲突",
}


# ============================================================================
# Validation Helpers
# ============================================================================


def validate_priority(priority: str | None) -> ToolError | None:
    """校验 priority 字段"""
    if priority is not None and priority not in VALID_PRIORITIES:
        return {
            "error": "invalid_field",
            "field": "priority",
            "message": f"priority 必须是 {', '.join(VALID_PRIORITIES)} 之一",
            "details": {"valid_values": list(VALID_PRIORITIES)},
        }
    return None


def validate_resonance(resonance: str | None) -> ToolError | None:
    """校验 resonance 字段"""
    if resonance is not None and resonance not in VALID_RESONANCES:
        return {
            "error": "invalid_field",
            "field": "resonance",
            "message": f"resonance 必须是 {', '.join(VALID_RESONANCES)} 之一",
            "details": {"valid_values": list(VALID_RESONANCES)},
        }
    return None


def validate_title(title: str | None) -> ToolError | None:
    """校验 title 字段"""
    if title is not None:
        if not title or not title.strip():
            return {
                "error": "invalid_field",
                "field": "title",
                "message": "title 不能为空",
            }
        if len(title) > 200:
            return {
                "error": "field_too_long",
                "field": "title",
                "message": "title 超过 200 字符",
                "details": {"max_length": 200, "actual_length": len(title)},
            }
    return None


def validate_clear_fields(clear_fields: list[str] | None) -> ToolError | None:
    """校验 clear_fields 参数"""
    if clear_fields:
        invalid = set(clear_fields) - CLEARABLE_TOPIC_FIELDS
        if invalid:
            return {
                "error": "invalid_clear_field",
                "message": f"以下字段不可清空: {', '.join(invalid)}",
                "details": {
                    "invalid_fields": list(invalid),
                    "clearable_fields": list(CLEARABLE_TOPIC_FIELDS),
                },
            }
    return None


def validate_batch_ids(ids: list[str]) -> tuple[list[UUID], ToolError | None]:
    """
    校验批量 ids 参数

    Returns:
        (parsed_uuids, error)
        - 成功: (去重后的 UUID 列表, None)
        - 失败: ([], ToolError)
    """
    if not ids:
        return [], {
            "error": "empty_ids",
            "message": "批量 ids 不能为空",
        }

    if len(ids) > MAX_BATCH_SIZE:
        return [], {
            "error": "batch_size_exceeded",
            "message": f"批量更新超限,最多 {MAX_BATCH_SIZE} 条",
            "details": {
                "max_size": MAX_BATCH_SIZE,
                "requested": len(ids),
            },
        }

    # 解析并去重
    parsed = []
    seen = set()
    for id_str in ids:
        try:
            uuid_obj = UUID(id_str)
            if uuid_obj not in seen:
                parsed.append(uuid_obj)
                seen.add(uuid_obj)
        except (ValueError, AttributeError):
            return [], {
                "error": "invalid_uuid",
                "message": f"非法 UUID: {id_str}",
                "field": "ids",
            }

    return parsed, None


def validate_pagination(limit: int, offset: int) -> ToolError | None:
    """校验分页参数"""
    if limit < 1 or limit > 100:
        return {
            "error": "invalid_field",
            "field": "limit",
            "message": "limit 必须在 1-100 之间",
            "details": {"min": 1, "max": 100, "actual": limit},
        }
    if offset < 0:
        return {
            "error": "invalid_field",
            "field": "offset",
            "message": "offset 不能为负数",
            "details": {"actual": offset},
        }
    return None


def validate_required_text(value: str | None, field: str) -> ToolError | None:
    if value is None or not str(value).strip():
        return error("missing_required_field", field=field)
    return None


def validate_optional_uuid(value: str | None, field: str) -> tuple[UUID | None, ToolError | None]:
    if value is None:
        return None, None
    try:
        return UUID(value), None
    except (ValueError, AttributeError):
        return None, error("invalid_uuid", field=field, details={"value": value})


def validate_workflow_run_payload(
    *,
    run_id: str | None,
    phase: str | None,
    status: str | None,
) -> ToolError | None:
    for field, value in (
        ("run_id", run_id),
        ("phase", phase),
        ("status", status),
    ):
        err = validate_required_text(value, field)
        if err:
            return err
    return None


def validate_finish_workflow_run_payload(
    *,
    run_id: str | None,
    phase: str | None,
    status: str | None,
) -> ToolError | None:
    return validate_workflow_run_payload(run_id=run_id, phase=phase, status=status)


def validate_workflow_artifact_payload(
    *,
    run_id: str | None,
    stage: str | None,
    type: str | None,
    name: str | None,
    content_hash: str | None,
    content_size_bytes: int | None,
    content_text: str | None,
    content_ref: str | None,
    topic_id: str | None = None,
    parent_artifact_id: str | None = None,
) -> ToolError | None:
    for field, value in (
        ("run_id", run_id),
        ("stage", stage),
        ("type", type),
        ("name", name),
        ("content_hash", content_hash),
    ):
        err = validate_required_text(value, field)
        if err:
            return err

    if content_size_bytes is None or content_size_bytes < 0:
        return error(
            "invalid_field",
            field="content_size_bytes",
            details={"actual": content_size_bytes},
        )
    if content_text is None and content_ref is None:
        return error("content_missing")
    if content_text is not None:
        size = len(content_text.encode("utf-8"))
        if size > MAX_WORKFLOW_INLINE_CONTENT_BYTES:
            return error(
                "content_too_large",
                field="content_text",
                details={
                    "max_bytes": MAX_WORKFLOW_INLINE_CONTENT_BYTES,
                    "actual_bytes": size,
                },
            )
        if "\x00" in content_text:
            return error("invalid_field", field="content_text")

    _, topic_err = validate_optional_uuid(topic_id, "topic_id")
    if topic_err:
        return topic_err
    if parent_artifact_id is not None and not parent_artifact_id.strip():
        return error("invalid_field", field="parent_artifact_id")
    return None


def validate_workflow_artifact_query(
    *,
    run_id: str | None = None,
    topic_id: str | None = None,
    account: str | None = None,
    type: str | None = None,
    stage: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WORKFLOW_ARTIFACT_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [run_id, topic_id, account, type, stage, date_from, date_to]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    if limit < 1 or limit > MAX_WORKFLOW_ARTIFACT_LIMIT:
        return error(
            "invalid_field",
            field="limit",
            details={"min": 1, "max": MAX_WORKFLOW_ARTIFACT_LIMIT, "actual": limit},
        )
    if offset < 0:
        return error("invalid_field", field="offset", details={"actual": offset})
    _, topic_err = validate_optional_uuid(topic_id, "topic_id")
    return topic_err


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _is_valid_iso_date(value: str | None) -> bool:
    if not _clean_text(value):
        return False
    try:
        date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return False
    return True


def _validate_allowed_source(source: str | None, field: str = "source") -> ToolError | None:
    source = _clean_text(source)
    if not source:
        return error("missing_required_field", field=field)
    if source not in WECHAT_ANALYTICS_SOURCES:
        return error(
            "invalid_field",
            field=field,
            details={"valid_values": sorted(WECHAT_ANALYTICS_SOURCES), "actual": source},
        )
    return None


def _validate_nonnegative_int(value, field: str) -> ToolError | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return error("invalid_field", field=field, details={"actual": value})
    return None


def _validate_nonnegative_number(value, field: str) -> ToolError | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return error("invalid_field", field=field, details={"actual": value})
    return None


def _has_article_resolution_fact(record: dict) -> bool:
    fields = (
        "article_id",
        "published_url",
        "canonical_url",
        "external_reference",
        "ref_value",
    )
    return any(_clean_text(record.get(field)) for field in fields)


def derive_publication_idempotency_key(
    *,
    account: str | None,
    publication_idempotency_key: str | None = None,
    publish_target: str | None = None,
    canonical_url: str | None = None,
    external_reference: str | None = None,
    run_id: str | None = None,
    publish_artifact_id: str | None = None,
    published_artifact_id: str | None = None,
) -> tuple[str | None, ToolError | None]:
    explicit_key = _clean_text(publication_idempotency_key)
    if explicit_key:
        return explicit_key, None

    account = _clean_text(account)
    if not account:
        return None, error("missing_required_field", field="account")

    publish_target = _clean_text(publish_target) or "default"
    canonical_url = _clean_text(canonical_url)
    external_reference = _clean_text(external_reference)
    run_id = _clean_text(run_id)
    publish_artifact_id = _clean_text(publish_artifact_id)
    published_artifact_id = _clean_text(published_artifact_id)

    if canonical_url:
        return f"{account}:{publish_target}:canonical_url:{canonical_url}", None
    if external_reference:
        return f"{account}:{publish_target}:external_reference:{external_reference}", None
    if run_id and publish_artifact_id:
        return f"{account}:run:{run_id}:publish_artifact:{publish_artifact_id}", None
    if run_id and published_artifact_id:
        return f"{account}:run:{run_id}:published_artifact:{published_artifact_id}", None
    return None, error("missing_required_field", field="publication_idempotency_key")


def validate_wechat_article_payload(
    *,
    account: str | None,
    run_id: str | None,
    status: str | None,
    topic_id: str | None = None,
    draft_artifact_id: str | None = None,
    published_artifact_id: str | None = None,
    publish_artifact_id: str | None = None,
    published_url: str | None = None,
    canonical_url: str | None = None,
    external_reference: str | None = None,
) -> ToolError | None:
    for field, value in (
        ("account", account),
        ("run_id", run_id),
        ("status", status),
    ):
        err = validate_required_text(value, field)
        if err:
            return err

    if status not in WECHAT_ARTICLE_STATUSES:
        return error(
            "invalid_field",
            field="status",
            details={"valid_values": sorted(WECHAT_ARTICLE_STATUSES), "actual": status},
        )

    for field, value in (
        ("topic_id", topic_id),
    ):
        _, uuid_err = validate_optional_uuid(value, field)
        if uuid_err:
            return uuid_err

    for field, value in (
        ("draft_artifact_id", draft_artifact_id),
        ("published_artifact_id", published_artifact_id),
        ("publish_artifact_id", publish_artifact_id),
    ):
        if value is not None and not str(value).strip():
            return error("invalid_field", field=field)

    refs = [
        _clean_text(published_url),
        _clean_text(canonical_url),
        _clean_text(external_reference),
    ]
    if status == "published" and not any(refs):
        return error(
            "invalid_field",
            field="published_url",
            details={"reason": "published_requires_url_or_reference"},
        )
    if status == "published_missing_url" and not _clean_text(external_reference):
        return error(
            "invalid_field",
            field="external_reference",
            details={"reason": "published_missing_url_requires_reference"},
        )
    return None


def validate_wechat_article_query(
    *,
    account: str | None = None,
    topic_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    publish_target: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WECHAT_ARTICLE_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [account, topic_id, run_id, status, publish_target, date_from, date_to]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    if status is not None and status not in WECHAT_ARTICLE_STATUSES:
        return error(
            "invalid_field",
            field="status",
            details={"valid_values": sorted(WECHAT_ARTICLE_STATUSES), "actual": status},
        )
    if limit < 1 or limit > MAX_WECHAT_ARTICLE_LIMIT:
        return error(
            "invalid_field",
            field="limit",
            details={"min": 1, "max": MAX_WECHAT_ARTICLE_LIMIT, "actual": limit},
        )
    if offset < 0:
        return error("invalid_field", field="offset", details={"actual": offset})
    _, topic_err = validate_optional_uuid(topic_id, "topic_id")
    return topic_err


def validate_wechat_article_ref_payload(
    *,
    refs: list[dict] | None = None,
    patch: dict | None = None,
) -> ToolError | None:
    refs = refs or []
    patch = patch or {}
    if not refs and not patch:
        return error("missing_required_field", field="refs")

    invalid_patch_fields = set(patch) - WECHAT_ARTICLE_PATCH_FIELDS
    if invalid_patch_fields:
        return error(
            "invalid_field",
            field="patch",
            details={"invalid_fields": sorted(invalid_patch_fields)},
        )
    if "status" in patch and patch["status"] not in WECHAT_ARTICLE_STATUSES:
        return error(
            "invalid_field",
            field="status",
            details={"valid_values": sorted(WECHAT_ARTICLE_STATUSES), "actual": patch["status"]},
        )

    for idx, ref in enumerate(refs):
        ref_type = ref.get("ref_type")
        ref_value = _clean_text(ref.get("ref_value"))
        if ref_type not in WECHAT_ARTICLE_REF_TYPES:
            return error(
                "invalid_field",
                field=f"refs[{idx}].ref_type",
                details={"valid_values": sorted(WECHAT_ARTICLE_REF_TYPES), "actual": ref_type},
            )
        if not ref_value:
            return error("missing_required_field", field=f"refs[{idx}].ref_value")
        if len(ref_value) > MAX_WECHAT_ARTICLE_REF_LENGTH:
            return error(
                "field_too_long",
                field=f"refs[{idx}].ref_value",
                details={
                    "max_length": MAX_WECHAT_ARTICLE_REF_LENGTH,
                    "actual_length": len(ref_value),
                },
            )
    return None


def validate_wechat_metric_record(record: dict, *, source: str | None = None) -> ToolError | None:
    if not isinstance(record, dict):
        return error("invalid_field", field="records[]")

    if not _has_article_resolution_fact(record):
        return error("missing_required_field", field="article_id")
    if _clean_text(record.get("article_id")):
        _, article_err = validate_optional_uuid(record.get("article_id"), "article_id")
        if article_err:
            return article_err

    for field in ("stat_date", "window_label"):
        err = validate_required_text(record.get(field), field)
        if err:
            return err
    if not _is_valid_iso_date(record.get("stat_date")):
        return error("invalid_field", field="stat_date", details={"actual": record.get("stat_date")})

    record_source = record.get("source") or source
    source_err = _validate_allowed_source(record_source, "source")
    if source_err:
        return source_err

    for field in WECHAT_ANALYTICS_COUNT_FIELDS:
        count_err = _validate_nonnegative_int(record.get(field), field)
        if count_err:
            return count_err

    stay_err = _validate_nonnegative_number(
        record.get("average_stay_seconds"),
        "average_stay_seconds",
    )
    if stay_err:
        return stay_err

    completion_rate = record.get("completion_rate")
    if completion_rate is not None:
        if (
            isinstance(completion_rate, bool)
            or not isinstance(completion_rate, (int, float))
            or completion_rate < 0
            or completion_rate > 1
        ):
            return error(
                "invalid_field",
                field="completion_rate",
                details={"min": 0, "max": 1, "actual": completion_rate},
            )

    missing_fields = record.get("missing_fields")
    if missing_fields is not None and not isinstance(missing_fields, list):
        return error("invalid_field", field="missing_fields")
    raw_json = record.get("raw_json")
    if raw_json is not None and not isinstance(raw_json, dict):
        return error("invalid_field", field="raw_json")
    return None


def validate_wechat_channel_metric(record: dict, *, source: str | None = None) -> ToolError | None:
    if not isinstance(record, dict):
        return error("invalid_field", field="channel_daily_metrics[]")

    if not _has_article_resolution_fact(record):
        return error("missing_required_field", field="article_id")
    if _clean_text(record.get("article_id")):
        _, article_err = validate_optional_uuid(record.get("article_id"), "article_id")
        if article_err:
            return article_err

    for field in ("metric_date", "channel"):
        err = validate_required_text(record.get(field), field)
        if err:
            return err
    if not _is_valid_iso_date(record.get("metric_date")):
        return error(
            "invalid_field",
            field="metric_date",
            details={"actual": record.get("metric_date")},
        )

    record_source = record.get("source") or source
    source_err = _validate_allowed_source(record_source, "source")
    if source_err:
        return source_err

    for field in WECHAT_ANALYTICS_CHANNEL_COUNT_FIELDS:
        count_err = _validate_nonnegative_int(record.get(field), field)
        if count_err:
            return count_err

    raw_json = record.get("raw_json")
    if raw_json is not None and not isinstance(raw_json, dict):
        return error("invalid_field", field="raw_json")
    return None


def validate_wechat_analytics_bulk_payload(
    *,
    account: str | None,
    source: str | None,
    records: list[dict] | None,
    channel_daily_metrics: list[dict] | None = None,
    audience_profiles: list[dict] | None = None,
    import_metadata: dict | None = None,
) -> tuple[dict, ToolError | None]:
    summary = {
        "audience_profiles_skipped": len(audience_profiles or []),
        "skip_reasons": [],
    }

    account_err = validate_required_text(account, "account")
    if account_err:
        return summary, account_err
    source_err = _validate_allowed_source(source)
    if source_err:
        return summary, source_err
    if not records:
        return summary, error("missing_required_field", field="records")
    if not isinstance(records, list):
        return summary, error("invalid_field", field="records")
    if channel_daily_metrics is not None and not isinstance(channel_daily_metrics, list):
        return summary, error("invalid_field", field="channel_daily_metrics")
    if audience_profiles is not None and not isinstance(audience_profiles, list):
        return summary, error("invalid_field", field="audience_profiles")
    if import_metadata is not None and not isinstance(import_metadata, dict):
        return summary, error("invalid_field", field="import_metadata")

    for idx, record in enumerate(records):
        record_err = validate_wechat_metric_record(record, source=source)
        if record_err:
            record_err["field"] = f"records[{idx}].{record_err.get('field', 'record')}"
            return summary, record_err

    for idx, metric in enumerate(channel_daily_metrics or []):
        metric_err = validate_wechat_channel_metric(metric, source=source)
        if metric_err:
            metric_err["field"] = (
                f"channel_daily_metrics[{idx}].{metric_err.get('field', 'record')}"
            )
            return summary, metric_err

    if audience_profiles:
        summary["skip_reasons"].append("audience_profiles_not_supported_in_mvp")
    return summary, None


def validate_wechat_metric_query(
    *,
    account: str | None = None,
    article_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    window_label: str | None = None,
    limit: int = DEFAULT_WECHAT_ANALYTICS_LIMIT,
    offset: int = 0,
    include_raw: bool = False,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [account, article_id, date_from, date_to, window_label]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    if limit < 1 or limit > MAX_WECHAT_ANALYTICS_LIMIT:
        return error(
            "invalid_field",
            field="limit",
            details={"min": 1, "max": MAX_WECHAT_ANALYTICS_LIMIT, "actual": limit},
        )
    if offset < 0:
        return error("invalid_field", field="offset", details={"actual": offset})
    if not isinstance(include_raw, bool):
        return error("invalid_field", field="include_raw", details={"actual": include_raw})
    _, article_err = validate_optional_uuid(article_id, "article_id")
    if article_err:
        return article_err
    for field, value in (("date_from", date_from), ("date_to", date_to)):
        if value is not None and not _is_valid_iso_date(value):
            return error("invalid_field", field=field, details={"actual": value})
    if date_from and date_to and date.fromisoformat(date_from) > date.fromisoformat(date_to):
        return error(
            "invalid_filter",
            field="date_from",
            details={"reason": "date_from_after_date_to"},
        )
    return None


def validate_retrospective_pagination(limit: int, offset: int) -> ToolError | None:
    if isinstance(limit, bool) or not isinstance(limit, int):
        return error("invalid_field", field="limit", details={"actual": limit})
    if limit < 1 or limit > MAX_WECHAT_RETROSPECTIVE_LIMIT:
        return error(
            "invalid_field",
            field="limit",
            details={
                "min": 1,
                "max": MAX_WECHAT_RETROSPECTIVE_LIMIT,
                "actual": limit,
            },
        )
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        return error("invalid_field", field="offset", details={"actual": offset})
    return None


def _validate_allowed_value(
    value: str | None,
    field: str,
    allowed: frozenset[str],
    *,
    required: bool = True,
) -> ToolError | None:
    value = _clean_text(value)
    if not value:
        return error("missing_required_field", field=field) if required else None
    if value not in allowed:
        return error(
            "invalid_field",
            field=field,
            details={"valid_values": sorted(allowed), "actual": value},
        )
    return None


def _validate_score(value, field: str) -> ToolError | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 100:
        return error("invalid_field", field=field, details={"min": 0, "max": 100, "actual": value})
    return None


def _validate_probability(value, field: str) -> ToolError | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value > 1:
        return error("invalid_field", field=field, details={"min": 0, "max": 1, "actual": value})
    return None


def _validate_json_object(record: dict, field: str, *, required: bool = True) -> ToolError | None:
    if field not in record:
        return error("missing_required_field", field=field) if required else None
    if not isinstance(record.get(field), dict):
        return error("invalid_field", field=field)
    return None


def _validate_json_array(record: dict, field: str, *, required: bool = True) -> ToolError | None:
    if field not in record:
        return error("missing_required_field", field=field) if required else None
    if not isinstance(record.get(field), list):
        return error("invalid_field", field=field)
    return None


def _validate_optional_iso_date(value: str | None, field: str) -> ToolError | None:
    if value is not None and not _is_valid_iso_date(value):
        return error("invalid_field", field=field, details={"actual": value})
    return None


def _validate_date_range(date_from: str | None, date_to: str | None) -> ToolError | None:
    for field, value in (("date_from", date_from), ("date_to", date_to)):
        date_err = _validate_optional_iso_date(value, field)
        if date_err:
            return date_err
    if date_from and date_to and date.fromisoformat(date_from) > date.fromisoformat(date_to):
        return error(
            "invalid_filter",
            field="date_from",
            details={"reason": "date_from_after_date_to"},
        )
    return None


def _is_valid_iso_datetime(value: str | None) -> bool:
    if not _clean_text(value):
        return False
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def _validate_optional_iso_datetime(value: str | None, field: str) -> ToolError | None:
    if value is not None and not _is_valid_iso_datetime(value):
        return error("invalid_field", field=field, details={"actual": value})
    return None


def _prefix_error_field(err: ToolError, prefix: str) -> ToolError:
    err["field"] = f"{prefix}.{err.get('field', 'record')}"
    return err


def _validate_uuid_array_values(record: dict, field: str, *, required: bool = True) -> ToolError | None:
    array_err = _validate_json_array(record, field, required=required)
    if array_err:
        return array_err
    if field not in record:
        return None
    for idx, value in enumerate(record.get(field) or []):
        _, uuid_err = validate_optional_uuid(value, f"{field}[{idx}]")
        if uuid_err:
            return uuid_err
    return None


def validate_topic_performance_payload(record: dict) -> ToolError | None:
    if not isinstance(record, dict):
        return error("invalid_field", field="input")

    for field in (
        "account",
        "article_id",
        "stat_date",
        "window_label",
        "scoring_version",
        "baseline_version",
    ):
        err = validate_required_text(record.get(field), field)
        if err:
            return err

    for field in ("article_id", "topic_id"):
        _, uuid_err = validate_optional_uuid(record.get(field), field)
        if uuid_err:
            return uuid_err

    date_err = _validate_optional_iso_date(record.get("stat_date"), "stat_date")
    if date_err:
        return date_err

    for field in RETROSPECTIVE_SCORE_FIELDS:
        score_err = _validate_score(record.get(field), field)
        if score_err:
            return score_err

    confidence_err = _validate_probability(record.get("confidence"), "confidence")
    if confidence_err:
        return confidence_err

    for field in ("provisional", "low_sample_size"):
        if field in record and not isinstance(record.get(field), bool):
            return error("invalid_field", field=field)

    for field in ("metric_snapshot_ids", "warnings"):
        array_err = _validate_json_array(record, field)
        if array_err:
            return array_err
    for field in ("baseline_snapshot", "diagnosis", "evidence_refs"):
        object_err = _validate_json_object(record, field)
        if object_err:
            return object_err
    return None


def validate_topic_performance_query(
    *,
    account: str | None = None,
    article_id: str | None = None,
    topic_id: str | None = None,
    window_label: str | None = None,
    scoring_version: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [account, article_id, topic_id, window_label, scoring_version, date_from, date_to]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    page_err = validate_retrospective_pagination(limit, offset)
    if page_err:
        return page_err
    for field, value in (("article_id", article_id), ("topic_id", topic_id)):
        _, uuid_err = validate_optional_uuid(value, field)
        if uuid_err:
            return uuid_err
    return _validate_date_range(date_from, date_to)


def validate_retrospective_report_payload(record: dict) -> ToolError | None:
    if not isinstance(record, dict):
        return error("invalid_field", field="input")

    for field in ("account", "period_start", "period_end", "scoring_version"):
        err = validate_required_text(record.get(field), field)
        if err:
            return err
    for field, allowed in (
        ("report_type", WECHAT_RETROSPECTIVE_REPORT_TYPES),
        ("generation_mode", WECHAT_RETROSPECTIVE_GENERATION_MODES),
        ("status", WECHAT_RETROSPECTIVE_REPORT_STATUSES),
    ):
        value_err = _validate_allowed_value(record.get(field), field, allowed)
        if value_err:
            return value_err

    date_err = _validate_date_range(record.get("period_start"), record.get("period_end"))
    if date_err:
        if date_err.get("field") == "date_from":
            date_err["field"] = "period_start"
        return date_err
    _, article_err = validate_optional_uuid(record.get("article_id"), "article_id")
    if article_err:
        return article_err

    sample_size = record.get("sample_size", 0)
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 0:
        return error("invalid_field", field="sample_size", details={"actual": sample_size})
    if "low_sample_size" in record and not isinstance(record.get("low_sample_size"), bool):
        return error("invalid_field", field="low_sample_size")

    for field in (
        "performance_ids",
        "high_performing_themes",
        "low_performing_themes",
        "title_patterns",
        "recommendations",
        "warnings",
    ):
        array_err = _validate_json_array(record, field)
        if array_err:
            return array_err
    for field in ("summary", "evidence_refs"):
        object_err = _validate_json_object(record, field)
        if object_err:
            return object_err
    return None


def validate_retrospective_report_query(
    *,
    account: str | None = None,
    report_type: str | None = None,
    article_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [account, report_type, article_id, date_from, date_to]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    page_err = validate_retrospective_pagination(limit, offset)
    if page_err:
        return page_err
    type_err = _validate_allowed_value(
        report_type,
        "report_type",
        WECHAT_RETROSPECTIVE_REPORT_TYPES,
        required=False,
    )
    if type_err:
        return type_err
    _, article_err = validate_optional_uuid(article_id, "article_id")
    if article_err:
        return article_err
    return _validate_date_range(date_from, date_to)


def _validate_topic_suggestion_item(
    item: dict,
    *,
    account: str,
    report_id: str,
) -> ToolError | None:
    if not isinstance(item, dict):
        return error("invalid_field", field="items[]")
    item_account = item.get("account") or account
    if item_account != account:
        return error("invalid_field", field="account", details={"reason": "account_mismatch"})
    item_report_id = item.get("report_id") or report_id
    if item_report_id != report_id:
        return error("invalid_field", field="report_id", details={"reason": "report_id_mismatch"})

    for field, allowed in (
        ("suggestion_type", TOPIC_OPTIMIZATION_SUGGESTION_TYPES),
        ("target_kind", TOPIC_OPTIMIZATION_TARGET_KINDS),
    ):
        value_err = _validate_allowed_value(item.get(field), field, allowed)
        if value_err:
            return value_err

    target_kind = item.get("target_kind")
    target_id = _clean_text(item.get("target_id"))
    target_key = _clean_text(item.get("target_key"))
    if target_id:
        _, target_err = validate_optional_uuid(target_id, "target_id")
        if target_err:
            return target_err
    if target_kind != "account" and not target_id and not target_key:
        return error("missing_required_field", field="target_id")

    for field in ("proposed_value", "evidence_refs"):
        object_err = _validate_json_object(item, field)
        if object_err:
            return object_err
    object_err = _validate_json_object(item, "current_value", required=False)
    if object_err:
        return object_err
    rationale_err = validate_required_text(item.get("rationale"), "rationale")
    if rationale_err:
        return rationale_err
    confidence_err = _validate_probability(item.get("confidence"), "confidence")
    if confidence_err:
        return confidence_err
    review_status = item.get("review_status", "pending")
    if review_status != "pending":
        return error("invalid_transition", field="review_status")
    return _validate_optional_iso_datetime(item.get("expires_at"), "expires_at")


def validate_topic_suggestions_payload(
    *,
    account: str | None,
    report_id: str | None,
    items: list[dict] | None,
) -> ToolError | None:
    account_err = validate_required_text(account, "account")
    if account_err:
        return account_err
    report_err = validate_required_text(report_id, "report_id")
    if report_err:
        return report_err
    _, uuid_err = validate_optional_uuid(report_id, "report_id")
    if uuid_err:
        return uuid_err
    if not items:
        return error("missing_required_field", field="items")
    if not isinstance(items, list):
        return error("invalid_field", field="items")
    for idx, item in enumerate(items):
        item_err = _validate_topic_suggestion_item(item, account=account, report_id=report_id)
        if item_err:
            return _prefix_error_field(item_err, f"items[{idx}]")
    return None


def validate_topic_optimization_suggestion_query(
    *,
    account: str | None = None,
    report_id: str | None = None,
    review_status: str | None = None,
    suggestion_type: str | None = None,
    target_kind: str | None = None,
    target_id: str | None = None,
    target_key: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [
        account,
        report_id,
        review_status,
        suggestion_type,
        target_kind,
        target_id,
        target_key,
    ]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    page_err = validate_retrospective_pagination(limit, offset)
    if page_err:
        return page_err
    for field, value in (("report_id", report_id), ("target_id", target_id)):
        _, uuid_err = validate_optional_uuid(value, field)
        if uuid_err:
            return uuid_err
    for field, value, allowed in (
        ("review_status", review_status, TOPIC_OPTIMIZATION_REVIEW_STATUSES),
        ("suggestion_type", suggestion_type, TOPIC_OPTIMIZATION_SUGGESTION_TYPES),
        ("target_kind", target_kind, TOPIC_OPTIMIZATION_TARGET_KINDS),
    ):
        value_err = _validate_allowed_value(value, field, allowed, required=False)
        if value_err:
            return value_err
    return None


def validate_suggestion_review(
    *,
    suggestion_id: str | None,
    review_status: str | None,
    reviewed_by: str | None = None,
    review_note: str | None = None,
    application_trace_id: str | None = None,
) -> ToolError | None:
    id_err = validate_required_text(suggestion_id, "suggestion_id")
    if id_err:
        return id_err
    _, uuid_err = validate_optional_uuid(suggestion_id, "suggestion_id")
    if uuid_err:
        return uuid_err
    status_err = _validate_allowed_value(
        review_status,
        "review_status",
        TOPIC_OPTIMIZATION_REVIEW_TARGET_STATUSES,
    )
    if status_err:
        if status_err["error"] == "invalid_field":
            status_err["error"] = "invalid_transition"
        return status_err
    if reviewed_by is not None and not _clean_text(reviewed_by):
        return error("invalid_field", field="reviewed_by")
    if review_note is not None and not isinstance(review_note, str):
        return error("invalid_field", field="review_note")
    if application_trace_id is not None:
        return error("invalid_transition", field="application_trace_id")
    return None


def validate_approved_ranking_hint_query(
    *,
    account: str | None,
    target_kind: str | None = None,
    target_id: str | None = None,
    target_key: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
) -> ToolError | None:
    account_err = validate_required_text(account, "account")
    if account_err:
        return account_err
    page_err = validate_retrospective_pagination(limit, offset)
    if page_err:
        return page_err
    kind_err = _validate_allowed_value(
        target_kind,
        "target_kind",
        TOPIC_OPTIMIZATION_TARGET_KINDS,
        required=False,
    )
    if kind_err:
        return kind_err
    _, target_err = validate_optional_uuid(target_id, "target_id")
    if target_err:
        return target_err
    if target_id and target_key:
        return error("invalid_filter", field="target_id", details={"reason": "ambiguous_target"})
    return None


def _validate_learning_candidate_item(
    item: dict,
    *,
    account: str,
    source_report_id: str,
) -> ToolError | None:
    if not isinstance(item, dict):
        return error("invalid_field", field="items[]")
    item_account = item.get("account") or account
    if item_account != account:
        return error("invalid_field", field="account", details={"reason": "account_mismatch"})
    item_report_id = item.get("source_report_id") or source_report_id
    if item_report_id != source_report_id:
        return error(
            "invalid_field",
            field="source_report_id",
            details={"reason": "source_report_id_mismatch"},
        )

    for field, allowed in (
        ("candidate_type", LEARNING_CANDIDATE_TYPES),
        ("status", LEARNING_CANDIDATE_STATUSES),
    ):
        value_err = _validate_allowed_value(item.get(field), field, allowed)
        if value_err:
            return value_err
    if item.get("status") != "pending_review":
        return error("invalid_transition", field="status")
    domain_err = validate_required_text(item.get("domain"), "domain")
    if domain_err:
        return domain_err
    uuid_array_err = _validate_uuid_array_values(item, "source_suggestion_ids")
    if uuid_array_err:
        return uuid_array_err
    for field in ("scope", "trigger_conditions", "proposed_policy", "evidence_refs"):
        object_err = _validate_json_object(item, field)
        if object_err:
            return object_err
    return _validate_probability(item.get("confidence"), "confidence")


def validate_learning_candidates_payload(
    *,
    account: str | None,
    source_report_id: str | None,
    items: list[dict] | None,
) -> ToolError | None:
    account_err = validate_required_text(account, "account")
    if account_err:
        return account_err
    report_err = validate_required_text(source_report_id, "source_report_id")
    if report_err:
        return report_err
    _, uuid_err = validate_optional_uuid(source_report_id, "source_report_id")
    if uuid_err:
        return uuid_err
    if not items:
        return error("missing_required_field", field="items")
    if not isinstance(items, list):
        return error("invalid_field", field="items")
    for idx, item in enumerate(items):
        item_err = _validate_learning_candidate_item(
            item,
            account=account,
            source_report_id=source_report_id,
        )
        if item_err:
            return _prefix_error_field(item_err, f"items[{idx}]")
    return None


def validate_learning_candidate_query(
    *,
    account: str | None = None,
    domain: str | None = None,
    source_report_id: str | None = None,
    status: str | None = None,
    candidate_type: str | None = None,
    limit: int = DEFAULT_WECHAT_RETROSPECTIVE_LIMIT,
    offset: int = 0,
    explicit_limit: bool = False,
) -> ToolError | None:
    filters = [account, domain, source_report_id, status, candidate_type]
    if not any(value is not None for value in filters) and not explicit_limit:
        return error("invalid_filter", details={"reason": "filter_or_explicit_limit_required"})
    page_err = validate_retrospective_pagination(limit, offset)
    if page_err:
        return page_err
    _, report_err = validate_optional_uuid(source_report_id, "source_report_id")
    if report_err:
        return report_err
    for field, value, allowed in (
        ("status", status, LEARNING_CANDIDATE_STATUSES),
        ("candidate_type", candidate_type, LEARNING_CANDIDATE_TYPES),
    ):
        value_err = _validate_allowed_value(value, field, allowed, required=False)
        if value_err:
            return value_err
    return None


def validate_learning_candidate_review(
    *,
    candidate_id: str | None,
    status: str | None,
    reviewed_by: str | None = None,
    review_note: str | None = None,
    policy_id: str | None = None,
) -> ToolError | None:
    id_err = validate_required_text(candidate_id, "candidate_id")
    if id_err:
        return id_err
    _, uuid_err = validate_optional_uuid(candidate_id, "candidate_id")
    if uuid_err:
        return uuid_err
    status_err = _validate_allowed_value(
        status,
        "status",
        LEARNING_CANDIDATE_REVIEW_TARGET_STATUSES,
    )
    if status_err:
        if status_err["error"] == "invalid_field":
            status_err["error"] = "invalid_transition"
        return status_err
    if reviewed_by is not None and not _clean_text(reviewed_by):
        return error("invalid_field", field="reviewed_by")
    if review_note is not None and not isinstance(review_note, str):
        return error("invalid_field", field="review_note")
    if policy_id is not None and not _clean_text(policy_id):
        return error("invalid_field", field="policy_id")
    return None


def error(
    code: str, field: str | None = None, details: dict | None = None
) -> ToolError:
    """
    构造标准错误结果

    Args:
        code: 错误码,必须在 ERROR_CODES 中
        field: 可选,关联字段名
        details: 可选,额外错误详情
    """
    result: ToolError = {
        "error": code,
        "message": ERROR_CODES.get(code, "未知错误"),
    }
    if field:
        result["field"] = field
    if details:
        result["details"] = details
    return result
