# Acceptance Record: Hermes DB WeChat Retrospective Topic Optimizer

**Workspace**: `hermes-db-wechat-retrospective-topic-optimizer` | **Date**: 2026-06-07 | **Spec**: [spec.md](spec.md)

## Evidence Table

| Requirement | Evidence | Test or File | Verdict |
|---|---|---|---|
| FR-001 performance upsert/list | 新增 `topic_performance` migration、contract validators、repository upsert/list、MCP tools；focused suite 覆盖幂等 upsert、filters、pagination 和 JSON serialization。 | `packages/hermes-db/migrations/versions/0005_wechat_retrospective_topic_optimizer.py`; `rtk uv run pytest tests/test_migration_sql.py tests/test_wechat_retrospective_contracts.py tests/test_wechat_retrospective_repo_sql.py tests/test_wechat_retrospective_tools.py tests/test_wechat_retrospective_schema_health.py -q` -> 70 passed | PASS |
| FR-002 reports create/get/list | 新增 report table、repository helpers 和 MCP tools；测试覆盖 create/get/list、not_found 和 schema drift mapping。 | `packages/hermes-db/src/hermes_db_mcp/tools/wechat_retrospective.py`; focused suite -> 70 passed | PASS |
| FR-003 suggestions create/list/review | 新增 suggestions table、batch create/list/review、review 状态校验；review tool 不允许写 `applied`。 | `packages/hermes-db/tests/test_wechat_retrospective_tools.py`; focused suite -> 70 passed | PASS |
| FR-004 learning candidates create/list/review | 新增 learning candidates table、batch create/list/review；审核只更新 candidate row，不应用 policy。 | `packages/hermes-db/src/hermes_db_mcp/repositories/wechat_retrospective_repo.py`; focused suite -> 70 passed | PASS |
| FR-005 approved ranking hints | `list_approved_topic_ranking_hints` 只返回 approved/applied 且未过期 suggestions，并支持 target filters。 | `packages/hermes-db/tests/test_wechat_retrospective_repo_sql.py`; `packages/hermes-db/tests/test_wechat_retrospective_tools.py`; focused suite -> 70 passed | PASS |
| FR-006 list pagination with total | Retrospective list tools 返回 `{items,total,limit,offset}`；repository 使用 count query。 | `packages/hermes-db/tests/test_wechat_retrospective_repo_sql.py`; `packages/hermes-db/tests/test_wechat_retrospective_tools.py`; focused suite -> 70 passed | PASS |
| FR-009/FR-010 health capability/schema drift gate | `health` 默认 `wechat_retrospective_topic_optimizer=false`；PG OK 时合并 schema inspector；inspector 检查四表 columns、PK/unique/check/FK constraints 和 indexes。 | `rtk uv run pytest tests/test_wechat_retrospective_schema_health.py tests/test_health.py -q` -> 10 passed | PASS |
| FR-011 structured errors | Tool 层映射 validation、FK not_found、schema_drift、invalid_transition 和 generic database_error。 | `packages/hermes-db/tests/test_wechat_retrospective_tools.py`; focused suite -> 70 passed | PASS |
| FR-012 downgrade safety | downgrade 按 learning candidates -> suggestions -> reports -> performance 删除 retrospective 表，不修改旧 feature 表。 | `packages/hermes-db/tests/test_migration_sql.py`; focused suite -> 70 passed | PASS |
| Existing capability regression | 旧 health、analytics、article、workflow、topic update tests 未被新 tool/module 破坏。 | `rtk uv run pytest tests/test_health.py tests/test_wechat_analytics_tools.py tests/test_wechat_article_tools.py tests/test_workflow_tools.py tests/test_tools_updates.py -q` -> 46 passed | PASS |
| Code quality | 全包 ruff 通过。 | `rtk uv run ruff check .` -> All checks passed | PASS |
| DB integration smoke | 新增真实 DB smoke 测试；当前本地未设置 `DATABASE_URL`，执行结果为 clean skip，未证明真实 migrated DB roundtrip。 | `rtk uv run pytest tests/test_wechat_retrospective_integration.py -q` -> 1 skipped | PARTIAL |
| Local MCP smoke | 当前本地没有 `DATABASE_URL`，本地 Docker 无运行容器；未启动 hermes-db MCP 和 migrated test DB。 | `rtk printenv DATABASE_URL` -> unset; local `docker ps` -> no containers | PARTIAL |
| Deployed NAS health smoke | 当前 NAS `hermes-db-mcp` 运行 `ghcr.io/north-sea/hermes-db-mcp:v0.2.12`，health OK 但 schema revision 仍为 `0004_wechat_analytics_ingestion`，缺少 retrospective capability。 | `rtk bash scripts/check-mcp-deploy.sh hermes-db-v0.2.12 nas deploy/mcp-services.json` -> missing `wechat_retrospective_topic_optimizer` | PARTIAL |
| Agents handoff smoke | 因 deployed capability 尚未为 true，未执行 agents production adapter live smoke。 | T045 依赖 T044 | PARTIAL |

## Verdict Summary

| Dimension | Verdict | Notes |
|---|---|---|
| Component capability | PASS | Migration、contracts、repository、MCP tools、health inspector、docs 和 regression tests 已完成。 |
| Workflow closure | PARTIAL | 新增 DB integration smoke 文件，但缺少真实 `DATABASE_URL` 下的 migrated DB roundtrip 和 local MCP smoke。 |
| User-visible outcome | PARTIAL | NAS 当前仍是旧 revision/capability，agents production live smoke 尚未解除阻塞。 |

**Overall**: CONDITIONAL PASS

**三维不一致说明**: 当前只能宣布 hermes-db 本地实现准备好，不能宣布 feature 完成。完成条件仍依赖部署 `0005_wechat_retro_opt` migration、新镜像 health capability true、以及 agents live smoke。

## Workflow Replay

- **输入摘要**: agents 侧将微信文章 analytics 结果转为 performance、report、suggestion、learning candidate payload。
- **最终 payload 摘要**: 新增 integration test 覆盖 performance upsert -> report create/get/list -> suggestion approve -> ranking hints -> learning candidate approve/list。
- **用户可见结果断言**: approved ranking hints 和 reviewed learning candidates 可被 agents 后续排序/策略链路读取。
- **Replay 类型**: fixture + skipped real DB。当前环境未设置 `DATABASE_URL`，真实 DB replay 需部署后补跑。

## Closeout Checklist

| Item | Status | Evidence / Rationale | Next Step |
|---|---|---|---|
| 旧逻辑、旧路径、fallback 或临时兼容退役 | 不适用 | 本 feature 是 additive migration 和 additive MCP tools；未替换旧工具。 | 无 |
| 发布、提交、CI 或 follow-through | 阻塞 | 本地实现测试通过，但 NAS 仍缺少 retrospective capability。 | 部署新镜像并执行 Alembic upgrade head 后补 T044。 |
| 文档、阶段说明、模板或验收记录更新 | 已完成 | README、部署说明、deploy manifest 和本 acceptance 已更新。 | 部署后补充最终 smoke 证据。 |
| ADR、架构债或演进触发信号 | 延后 | `applied` suggestion 和 `exported_to_policy` 仍为 future trace/export 状态。 | 后续如 agents 需要写回应用 trace，再新增 mark-applied/export tool。 |
| 知识同步或经验沉淀 | 延后 | 当前尚未完成 deployed/agents live smoke。 | Feature 完成后再沉淀最终部署结论。 |

## Commit Result

| Field | Value |
|---|---|
| Status | not_submitted |
| Commit Hashes | 无 |
| Commit Messages | 无 |
| Included Files | 无 |
| Excluded / Remaining Files | 当前 feature 相关 diff 尚未提交 |
| Reason | 用户未要求提交；SDD closeout 不自动 `git add` / `git commit`。 |

## Completion Record

- **最终结论**: CONDITIONAL PASS
- **完成依据**: 本地 focused suite 70 passed、existing regression 46 passed、health/schema 10 passed、ruff all passed。
- **阻塞项**: T042 local MCP smoke 缺真实 DB/MCP 环境；T044 NAS deployed capability 当前为 false；T045 agents live smoke 依赖 T044。
- **延后项**: 部署后补真实 DB integration、MCP health/tools smoke、agents production adapter smoke。
- **退役结论**: 不适用。
- **提交结论**: not_submitted。
- **后续动作**: 部署新 hermes-db 镜像并执行 migration 后，补跑 T042/T044/T045，再进入最终 verify/closeout。
