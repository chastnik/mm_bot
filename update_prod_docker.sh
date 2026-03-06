#!/usr/bin/env bash

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
  echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

fail() {
  echo -e "${RED}[ERROR]${NC} $1" >&2
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -d ".git" ]]; then
  fail "Текущая директория не выглядит как git-репозиторий."
fi

if [[ ! -f "docker-compose.yml" || ! -f "Dockerfile" ]]; then
  fail "Не найдены Dockerfile/docker-compose.yml."
fi

if [[ ! -f ".env" ]]; then
  fail "Не найден .env. Сначала выполните первичную установку."
fi

if ! command -v docker >/dev/null 2>&1; then
  fail "Docker не установлен."
fi

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon недоступен. Проверьте службу docker."
fi

get_compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return
  fi

  fail "Docker Compose не найден."
}

validate_env_vars() {
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  local required_vars=(
    MATTERMOST_URL
    MATTERMOST_TOKEN
    MATTERMOST_USERNAME
    MATTERMOST_TEAM
    LLM_PROXY_TOKEN
    LLM_BASE_URL
    LLM_MODEL
    CONFLUENCE_USERNAME
    CONFLUENCE_PASSWORD
    CONFLUENCE_BASE_URL
  )

  local missing=()
  local var_name

  for var_name in "${required_vars[@]}"; do
    if [[ -z "${!var_name:-}" || "${!var_name}" == your_* || "${!var_name}" == https://your-* ]]; then
      missing+=("$var_name")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    echo "Не заполнены обязательные переменные .env:"
    printf ' - %s\n' "${missing[@]}"
    fail "Заполните .env перед обновлением."
  fi

  ok ".env прошел базовую проверку."
}

COMPOSE_CMD="$(get_compose_cmd)"

if [[ -n "$(git status --porcelain)" ]]; then
  warn "Есть локальные изменения в репозитории. Выполняю только git pull --ff-only."
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log "Обновляю код из origin/${CURRENT_BRANCH}..."
git fetch --all --prune
git pull --ff-only origin "${CURRENT_BRANCH}"

validate_env_vars

log "Останавливаю текущий контейнер..."
${COMPOSE_CMD} down

log "Пересобираю образ и поднимаю сервис..."
${COMPOSE_CMD} up -d --build --remove-orphans

log "Проверяю, что контейнер запущен..."
if docker ps --format '{{.Names}}' | rg -q '^ai-docs-bot$'; then
  ok "Обновление завершено. Контейнер ai-docs-bot запущен."
else
  fail "Контейнер ai-docs-bot не запущен. Проверьте логи: ${COMPOSE_CMD} logs --tail=200"
fi

echo
echo "Полезные команды:"
echo " - ${COMPOSE_CMD} logs -f"
echo " - ${COMPOSE_CMD} ps"
echo " - ${COMPOSE_CMD} restart"
