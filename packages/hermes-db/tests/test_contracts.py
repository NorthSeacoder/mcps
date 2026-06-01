"""
测试 contracts 模块的常量、校验 helper 和结构化结果模型
"""

from uuid import uuid4

from hermes_db_mcp.contracts import (
    EDITABLE_TOPIC_FIELDS,
    BULK_TOPIC_FIELDS,
    CLEARABLE_TOPIC_FIELDS,
    VALID_PRIORITIES,
    VALID_RESONANCES,
    MAX_BATCH_SIZE,
    validate_priority,
    validate_resonance,
    validate_title,
    validate_clear_fields,
    validate_batch_ids,
    validate_pagination,
    error,
)


class TestConstants:
    """测试字段白名单和常量定义"""

    def test_editable_fields_coverage(self):
        """T001: 可编辑字段集合符合 spec"""
        assert "title" in EDITABLE_TOPIC_FIELDS
        assert "angle" in EDITABLE_TOPIC_FIELDS
        assert "priority" in EDITABLE_TOPIC_FIELDS
        assert "column_name" in EDITABLE_TOPIC_FIELDS
        assert "resonance" in EDITABLE_TOPIC_FIELDS
        assert "content" in EDITABLE_TOPIC_FIELDS

        # 不可编辑字段
        assert "status" not in EDITABLE_TOPIC_FIELDS
        assert "account" not in EDITABLE_TOPIC_FIELDS
        assert "published_url" not in EDITABLE_TOPIC_FIELDS
        assert "source" not in EDITABLE_TOPIC_FIELDS

    def test_bulk_fields_subset(self):
        """T001: 批量字段是可编辑字段的子集,且不包含语义字段"""
        assert BULK_TOPIC_FIELDS.issubset(EDITABLE_TOPIC_FIELDS)
        assert "priority" in BULK_TOPIC_FIELDS
        assert "resonance" in BULK_TOPIC_FIELDS
        assert "column_name" in BULK_TOPIC_FIELDS

        # 语义字段不在批量字段中
        assert "title" not in BULK_TOPIC_FIELDS
        assert "angle" not in BULK_TOPIC_FIELDS
        assert "content" not in BULK_TOPIC_FIELDS

    def test_clearable_fields_subset(self):
        """T001: 可清空字段是可编辑字段的子集,且不包含必填字段"""
        assert CLEARABLE_TOPIC_FIELDS.issubset(EDITABLE_TOPIC_FIELDS)
        assert "angle" in CLEARABLE_TOPIC_FIELDS
        assert "column_name" in CLEARABLE_TOPIC_FIELDS
        assert "resonance" in CLEARABLE_TOPIC_FIELDS
        assert "content" in CLEARABLE_TOPIC_FIELDS

        # 必填字段不可清空
        assert "title" not in CLEARABLE_TOPIC_FIELDS
        assert "priority" not in CLEARABLE_TOPIC_FIELDS

    def test_valid_priorities(self):
        """T001: priority 合法值"""
        assert VALID_PRIORITIES == {"A", "B", "C"}

    def test_valid_resonances(self):
        """T001: resonance 合法值"""
        assert VALID_RESONANCES == {"高", "中", "低"}

    def test_max_batch_size(self):
        """T001: 批量上限"""
        assert MAX_BATCH_SIZE == 100


class TestValidationHelpers:
    """测试校验 helper"""

    def test_validate_priority_valid(self):
        """T003: 合法 priority 通过校验"""
        assert validate_priority("A") is None
        assert validate_priority("B") is None
        assert validate_priority("C") is None
        assert validate_priority(None) is None

    def test_validate_priority_invalid(self):
        """T003: 非法 priority 返回错误"""
        err = validate_priority("D")
        assert err is not None
        assert err["error"] == "invalid_field"
        assert err["field"] == "priority"
        assert "details" in err

    def test_validate_resonance_valid(self):
        """T003: 合法 resonance 通过校验"""
        assert validate_resonance("高") is None
        assert validate_resonance("中") is None
        assert validate_resonance("低") is None
        assert validate_resonance(None) is None

    def test_validate_resonance_invalid(self):
        """T003: 非法 resonance 返回错误"""
        err = validate_resonance("极高")
        assert err is not None
        assert err["error"] == "invalid_field"
        assert err["field"] == "resonance"

    def test_validate_title_valid(self):
        """T003: 合法 title 通过校验"""
        assert validate_title("正常标题") is None
        assert validate_title("a" * 200) is None
        assert validate_title(None) is None

    def test_validate_title_empty(self):
        """T003: 空 title 返回错误"""
        err = validate_title("")
        assert err is not None
        assert err["error"] == "invalid_field"
        assert err["field"] == "title"

        err = validate_title("   ")
        assert err is not None
        assert err["error"] == "invalid_field"

    def test_validate_title_too_long(self):
        """T003: title 超长返回错误"""
        err = validate_title("a" * 201)
        assert err is not None
        assert err["error"] == "field_too_long"
        assert err["field"] == "title"
        assert err["details"]["max_length"] == 200
        assert err["details"]["actual_length"] == 201

    def test_validate_clear_fields_valid(self):
        """T003: 合法 clear_fields 通过校验"""
        assert validate_clear_fields(None) is None
        assert validate_clear_fields([]) is None
        assert validate_clear_fields(["angle"]) is None
        assert (
            validate_clear_fields(["angle", "column_name", "resonance", "content"])
            is None
        )

    def test_validate_clear_fields_invalid(self):
        """T003: 非法 clear_fields 返回错误"""
        err = validate_clear_fields(["title"])
        assert err is not None
        assert err["error"] == "invalid_clear_field"
        assert "title" in err["details"]["invalid_fields"]

        err = validate_clear_fields(["angle", "status", "priority"])
        assert err is not None
        assert set(err["details"]["invalid_fields"]) == {"status", "priority"}

    def test_validate_batch_ids_valid(self):
        """T003: 合法 batch ids 通过校验并去重"""
        id1 = str(uuid4())
        id2 = str(uuid4())

        uuids, err = validate_batch_ids([id1, id2])
        assert err is None
        assert len(uuids) == 2

        # 去重
        uuids, err = validate_batch_ids([id1, id2, id1])
        assert err is None
        assert len(uuids) == 2

    def test_validate_batch_ids_empty(self):
        """T003: 空 ids 返回错误"""
        uuids, err = validate_batch_ids([])
        assert err is not None
        assert err["error"] == "empty_ids"
        assert uuids == []

    def test_validate_batch_ids_exceeded(self):
        """T003: 超限 ids 返回错误"""
        ids = [str(uuid4()) for _ in range(101)]
        uuids, err = validate_batch_ids(ids)
        assert err is not None
        assert err["error"] == "batch_size_exceeded"
        assert err["details"]["max_size"] == 100
        assert err["details"]["requested"] == 101

    def test_validate_batch_ids_invalid_uuid(self):
        """T003: 非法 UUID 返回错误"""
        uuids, err = validate_batch_ids(["not-a-uuid"])
        assert err is not None
        assert err["error"] == "invalid_uuid"
        assert err["field"] == "ids"

    def test_validate_pagination_valid(self):
        """T003: 合法分页参数通过校验"""
        assert validate_pagination(20, 0) is None
        assert validate_pagination(1, 0) is None
        assert validate_pagination(100, 100) is None

    def test_validate_pagination_invalid_limit(self):
        """T003: 非法 limit 返回错误"""
        err = validate_pagination(0, 0)
        assert err is not None
        assert err["error"] == "invalid_field"
        assert err["field"] == "limit"

        err = validate_pagination(101, 0)
        assert err is not None
        assert err["field"] == "limit"

    def test_validate_pagination_invalid_offset(self):
        """T003: 非法 offset 返回错误"""
        err = validate_pagination(20, -1)
        assert err is not None
        assert err["error"] == "invalid_field"
        assert err["field"] == "offset"


class TestErrorHelper:
    """测试错误构造 helper"""

    def test_error_basic(self):
        """T002: 基础错误结构"""
        err = error("not_found")
        assert err["error"] == "not_found"
        assert "message" in err

    def test_error_with_field(self):
        """T002: 带字段的错误"""
        err = error("invalid_field", field="priority")
        assert err["error"] == "invalid_field"
        assert err["field"] == "priority"

    def test_error_with_details(self):
        """T002: 带详情的错误"""
        err = error("batch_size_exceeded", details={"max": 100, "actual": 150})
        assert err["error"] == "batch_size_exceeded"
        assert err["details"]["max"] == 100
        assert err["details"]["actual"] == 150
