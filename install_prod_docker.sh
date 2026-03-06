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

if [[ ! -f "docker-compose.yml" || ! -f "Dockerfile" ]]; then
  fail "Не найдены Dockerfile/docker-compose.yml. Запускайте скрипт из корня проекта."
fi

if [[ ! -f "env.example" ]]; then
  fail "Не найден env.example."
fi

SUDO_CMD=""
if [[ "${EUID}" -ne 0 ]]; then
  if command -v sudo >/dev/null 2>&1; then
    SUDO_CMD="sudo"
  else
    fail "Для установки зависимостей нужен root или sudo."
  fi
fi

install_docker_if_needed() {
  if command -v docker >/dev/null 2>&1; then
    ok "Docker уже установлен."
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    fail "Автоустановка Docker поддерживается только для Debian/Ubuntu (apt-get)."
  fi

  log "Устанавливаю Docker и Docker Compose..."
  ${SUDO_CMD} apt-get update
  ${SUDO_CMD} apt-get install -y docker.io docker-compose-plugin
  ${SUDO_CMD} systemctl enable --now docker
  ok "Docker установлен."
}

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

ensure_env_file() {
  if [[ -f ".env" ]]; then
    ok "Файл .env найден."
    return
  fi

  cp env.example .env
  warn "Создан .env из env.example. Заполните значения и запустите скрипт повторно."
  exit 1
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
    fail "Заполните .env и запустите установку заново."
  fi

  ok ".env прошел базовую проверку."
}

install_docker_if_needed

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon недоступен. Проверьте, что служба docker запущена."
fi

COMPOSE_CMD="$(get_compose_cmd)"
ensure_env_file
validate_env_vars

log "Собираю Docker-образ..."
${COMPOSE_CMD} build --pull

log "Запускаю контейнер в фоне..."
${COMPOSE_CMD} up -d

log "Проверяю статус контейнера..."
if docker ps --format '{{.Names}}' | rg -q '^ai-docs-bot$'; then
  ok "Контейнер ai-docs-bot запущен."
else
  fail "Контейнер ai-docs-bot не запустился. Проверьте логи: ${COMPOSE_CMD} logs --tail=200"
fi

echo
ok "Установка завершена."
echo "Полезные команды:"
echo " - ${COMPOSE_CMD} logs -f"
echo " - ${COMPOSE_CMD} ps"
echo " - ${COMPOSE_CMD} restart"
