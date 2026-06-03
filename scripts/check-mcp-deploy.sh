#!/usr/bin/env bash
set -euo pipefail

tag_name="${1:-}"
nas_alias="${2:-nas}"
manifest_path="${3:-deploy/mcp-services.json}"

if [[ -z "${tag_name}" ]]; then
  echo "Usage: $0 <service>-vX.Y.Z [nas-alias] [manifest-path]" >&2
  exit 2
fi

release_json="$(node scripts/resolve-mcp-release.mjs "${tag_name}" "${manifest_path}" 2>/dev/null)"

json_get() {
  RELEASE_JSON="${release_json}" node -e '
const release = JSON.parse(process.env.RELEASE_JSON);
const value = release[process.argv[1]] ?? "";
process.stdout.write(String(value));
' "$1"
}

shell_quote() {
  printf "%q" "$1"
}

service_name="$(json_get service)"
version="$(json_get version)"
image_ref="$(json_get image_ref)"
compose_project_dir="$(json_get compose_project_dir)"
compose_file="$(json_get compose_file)"
compose_service="$(json_get compose_service)"
container_name="$(json_get container_name)"
smoke_url="$(json_get smoke_url)"
smoke_token_env="$(json_get smoke_token_env)"
smoke_capabilities="$(json_get smoke_capabilities)"

cat <<SUMMARY
release_tag=${tag_name}
service=${service_name}
version=${version}
expected_image=${image_ref}
nas_alias=${nas_alias}
compose_project=${compose_project_dir}
SUMMARY

ssh "${nas_alias}" \
  "SERVICE_NAME=$(shell_quote "${service_name}") VERSION=$(shell_quote "${version}") IMAGE_REF=$(shell_quote "${image_ref}") COMPOSE_PROJECT_DIR=$(shell_quote "${compose_project_dir}") COMPOSE_FILE=$(shell_quote "${compose_file}") COMPOSE_SERVICE=$(shell_quote "${compose_service}") CONTAINER_NAME=$(shell_quote "${container_name}") SMOKE_URL=$(shell_quote "${smoke_url}") SMOKE_TOKEN_ENV=$(shell_quote "${smoke_token_env}") SMOKE_CAPABILITIES=$(shell_quote "${smoke_capabilities}") bash -s" <<'REMOTE'
set -euo pipefail

cd "${COMPOSE_PROJECT_DIR}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_PROJECT_DIR}/${COMPOSE_FILE}" >&2
  exit 1
fi

running="$(docker inspect "${CONTAINER_NAME}" --format "{{.State.Running}}")"
actual_image="$(docker inspect "${CONTAINER_NAME}" --format "{{.Config.Image}}")"

if [[ "${running}" != "true" ]]; then
  echo "Container ${CONTAINER_NAME} is not running" >&2
  docker logs --tail 120 "${CONTAINER_NAME}" >&2 || true
  exit 1
fi

if [[ "${actual_image}" != "${IMAGE_REF}" ]]; then
  echo "Container ${CONTAINER_NAME} is running unexpected image: ${actual_image}" >&2
  echo "Expected: ${IMAGE_REF}" >&2
  exit 1
fi

echo "container=${CONTAINER_NAME}"
echo "image=${actual_image}"
echo "running=${running}"

if [[ -n "${SMOKE_URL}" ]]; then
  token=""
  if [[ -n "${SMOKE_TOKEN_ENV}" ]]; then
    token="$(docker inspect "${CONTAINER_NAME}" --format "{{range .Config.Env}}{{println .}}{{end}}" | sed -n "s/^${SMOKE_TOKEN_ENV}=//p" | head -n 1)"
    if [[ -z "${token}" ]]; then
      echo "Smoke token env var is empty: ${SMOKE_TOKEN_ENV}" >&2
      exit 1
    fi
  fi

  python3 - "${SMOKE_URL}" "${token}" "${SMOKE_CAPABILITIES}" <<'PY'
import json
import sys
import time
import urllib.request
from urllib.error import URLError

url, token, capabilities = sys.argv[1:4]
required = [item for item in capabilities.split(",") if item]
headers = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}
if token:
    headers["Authorization"] = f"Bearer {token}"

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "health", "arguments": {}},
}
request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers=headers,
    method="POST",
)
last_error = None
for attempt in range(1, 11):
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
        break
    except (ConnectionError, TimeoutError, URLError, OSError) as exc:
        last_error = exc
        if attempt == 10:
            raise
        time.sleep(min(attempt, 5))
else:
    raise SystemExit(f"MCP health smoke failed: {last_error}")

data = json.loads(raw)
if "error" in data:
    raise SystemExit(f"MCP health returned error: {data['error']}")
content = data.get("result", {}).get("content", [])
structured = data.get("result", {}).get("structuredContent")
if isinstance(structured, dict):
    health = structured
else:
    if not content:
        raise SystemExit(f"MCP health response missing content: {data}")
    text = content[0].get("text")
    if text is None:
        raise SystemExit(f"MCP health response missing text content: {data}")
    health = json.loads(text)
if health.get("pg") != "ok":
    raise SystemExit(f"PostgreSQL health is not ok: {health.get('pg')}")
capability_map = health.get("capabilities") or {}
missing = [name for name in required if capability_map.get(name) is not True]
if missing:
    raise SystemExit(f"Missing capabilities: {missing}; health={health}")
print(json.dumps({
    "version": health.get("version"),
    "schema_revision": health.get("schema_revision"),
    "pg": health.get("pg"),
    "capabilities": capability_map,
}, ensure_ascii=False))
PY
fi

if [[ "${SERVICE_NAME}" == "hermes-db" ]]; then
  echo "schema_check=hermes-db-topic-revisit"
  docker exec -i "${CONTAINER_NAME}" python - <<'PY'
import os
import psycopg2

dsn = os.environ.get("MIGRATION_PG_DSN") or os.environ["PG_DSN"]
conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute("select version_num from alembic_version")
print("alembic=" + repr(cur.fetchone()))
cur.execute(
    """
    select column_name
    from information_schema.columns
    where table_schema=%s
      and table_name=%s
      and column_name in (%s, %s)
    order by column_name
    """,
    ("hermes", "topics", "mother_theme", "revisit_of"),
)
columns = cur.fetchall()
print("columns=" + repr(columns))
cur.execute(
    """
    select constraint_name
    from information_schema.table_constraints
    where table_schema=%s
      and table_name=%s
      and constraint_name in (%s, %s)
    order by constraint_name
    """,
    ("hermes", "topics", "chk_topics_revisit_of_not_self", "fk_topics_revisit_of"),
)
constraints = cur.fetchall()
print("constraints=" + repr(constraints))
cur.close()
conn.close()
expected_columns = {("mother_theme",), ("revisit_of",)}
expected_constraints = {("chk_topics_revisit_of_not_self",), ("fk_topics_revisit_of",)}
if set(columns) != expected_columns:
    raise SystemExit(f"Unexpected hermes.topics columns: {columns}")
if set(constraints) != expected_constraints:
    raise SystemExit(f"Unexpected hermes.topics constraints: {constraints}")
PY
fi
REMOTE
