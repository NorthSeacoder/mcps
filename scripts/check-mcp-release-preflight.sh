#!/usr/bin/env bash
set -euo pipefail

required_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env: ${name}" >&2
    exit 2
  fi
}

required_env SERVICE_NAME
required_env IMAGE_REF
required_env COMPOSE_PROJECT_DIR
required_env COMPOSE_FILE
required_env COMPOSE_SERVICE
required_env CONTAINER_NAME

MIGRATION_COMMAND="${MIGRATION_COMMAND:-}"
SMOKE_TOKEN_ENV="${SMOKE_TOKEN_ENV:-}"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "python3 or python is required" >&2
    exit 1
  fi
fi

cd "${COMPOSE_PROJECT_DIR}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "Compose file not found: ${COMPOSE_PROJECT_DIR}/${COMPOSE_FILE}" >&2
  exit 1
fi

override_file="$(mktemp)"
compose_config_json="$(mktemp)"
trap 'rm -f "${override_file}" "${compose_config_json}"' EXIT
printf '%s\n' 'services:' "  ${COMPOSE_SERVICE}:" "    image: ${IMAGE_REF}" > "${override_file}"
docker compose -f "${COMPOSE_FILE}" -f "${override_file}" config --format json > "${compose_config_json}"
"${PYTHON_BIN}" - "${compose_config_json}" "${COMPOSE_SERVICE}" "${IMAGE_REF}" <<'PY'
import json
import sys

path, service_name, image_ref = sys.argv[1:4]
with open(path, "r", encoding="utf-8") as fh:
    config = json.load(fh)
service = config.get("services", {}).get(service_name)
if not service:
    raise SystemExit(f"Compose service not found after config: {service_name}")
actual_image = service.get("image")
if actual_image != image_ref:
    raise SystemExit(f"Compose image mismatch: {actual_image} != {image_ref}")
print(f"image: {actual_image}")
PY

required_env_keys=("PG_DSN")
if [[ -n "${SMOKE_TOKEN_ENV}" ]]; then
  required_env_keys+=("${SMOKE_TOKEN_ENV}")
fi
if [[ -n "${MIGRATION_COMMAND}" ]]; then
  required_env_keys+=("MIGRATION_PG_DSN")
fi

"${PYTHON_BIN}" - "${compose_config_json}" "${COMPOSE_SERVICE}" "${required_env_keys[@]}" <<'PY'
import json
import sys

path = sys.argv[1]
service_name = sys.argv[2]
required = sys.argv[3:]
with open(path, "r", encoding="utf-8") as fh:
    config = json.load(fh)
service = config.get("services", {}).get(service_name, {})
environment = service.get("environment") or {}
if isinstance(environment, list):
    present = {item.split("=", 1)[0] for item in environment if "=" in item}
elif isinstance(environment, dict):
    present = set(environment)
else:
    present = set()
missing = [key for key in required if key not in present]
if missing:
    raise SystemExit(f"Missing required env keys: {' '.join(missing)}")
PY

migration_role_summary="not checked"
if [[ -n "${MIGRATION_COMMAND}" ]] && docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  migration_role_summary="$(docker exec -i "${CONTAINER_NAME}" python - <<'PY'
import os
import psycopg2

dsn = os.environ.get("MIGRATION_PG_DSN")
if not dsn:
    raise SystemExit("MIGRATION_PG_DSN is not present in the running container")
conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute("select current_user")
current_user = cur.fetchone()[0]
cur.execute(
    "select tableowner from pg_tables where schemaname=%s and tablename=%s",
    ("hermes", "topics"),
)
owner_row = cur.fetchone()
table_owner = owner_row[0] if owner_row else "missing"
cur.execute("select rolsuper from pg_roles where rolname = current_user")
is_superuser = bool(cur.fetchone()[0])
cur.close()
conn.close()
print(f"current_user={current_user}; hermes.topics owner={table_owner}; superuser={is_superuser}")
if table_owner != "missing" and current_user != table_owner and not is_superuser:
    raise SystemExit("Migration role is neither hermes.topics owner nor superuser")
PY
  )"
fi

{
  echo "## NAS deploy preflight"
  echo
  echo "- Service: ${SERVICE_NAME}"
  echo "- Target image: ${IMAGE_REF}"
  echo "- Compose project: ${COMPOSE_PROJECT_DIR}"
  echo "- Compose file: ${COMPOSE_FILE}"
  echo "- Compose service: ${COMPOSE_SERVICE}"
  echo "- Container: ${CONTAINER_NAME}"
  echo "- Compose environment keys checked: ${required_env_keys[*]}"
  echo "- Required env keys present: ${required_env_keys[*]}"
  echo "- Migration role: ${migration_role_summary}"
} | tee /tmp/mcp-release-preflight-summary.md

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat /tmp/mcp-release-preflight-summary.md >> "${GITHUB_STEP_SUMMARY}"
fi
