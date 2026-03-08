#!/bin/bash
# Скрипт запуска бота анализа документов для Mattermost

set -e  # Прерывание выполнения при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция логирования
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Проверка Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 не установлен!"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l 2>/dev/null || echo "1") == "1" ]]; then
        warning "Рекомендуется Python 3.8+, у вас версия $PYTHON_VERSION"
    fi
}

# Проверка виртуального окружения
check_venv() {
    if [[ ! -d "venv" ]]; then
        log "Создание виртуального окружения..."
        python3 -m venv venv
    fi
    
    log "Активация виртуального окружения..."
    source venv/bin/activate
    
    # Обновляем pip
    pip install --upgrade pip > /dev/null 2>&1
}

# Установка зависимостей
install_dependencies() {
    if [[ -f "requirements.txt" ]]; then
        log "Установка зависимостей..."
        pip install -r requirements.txt > /dev/null 2>&1
        success "Зависимости установлены"
    else
        error "Файл requirements.txt не найден!"
        exit 1
    fi
}

# Проверка файла конфигурации
check_config() {
    if [[ ! -f ".env" ]]; then
        warning "Файл .env не найден!"
        if [[ -f "env.example" ]]; then
            log "Создание .env из примера..."
            cp env.example .env
            warning "Отредактируйте файл .env перед запуском бота!"
            error "Заполните все необходимые переменные в .env файле"
            exit 1
        else
            error "Файл env.example не найден!"
            exit 1
        fi
    fi
}

# Проверка обязательных переменных
check_env_vars() {
    source .env 2>/dev/null || true
    
    REQUIRED_VARS=(
        "MATTERMOST_URL"
        "MATTERMOST_TOKEN"  
        "MATTERMOST_USERNAME"
        "LLM_PROXY_TOKEN"
        "LLM_BASE_URL"
        "LLM_MODEL"
        "CONFLUENCE_BASE_URL"
    )
    
    MISSING_VARS=()
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [[ -z "${!var}" || "${!var}" == "your_"* || "${!var}" == "https://your-"* ]]; then
            MISSING_VARS+=("$var")
        fi
    done
    
    if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
        error "Не заполнены обязательные переменные:"
        for var in "${MISSING_VARS[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Отредактируйте файл .env и заполните все переменные."
        echo "Смотрите SETUP_PRODUCTION.md для подробных инструкций."
        exit 1
    fi
}

# Тестирование компонентов
test_components() {
    if [[ -f "test_components.py" ]]; then
        log "Запуск тестов компонентов..."
        if python3 test_components.py > test_output.log 2>&1; then
            success "Все тесты прошли успешно"
            rm -f test_output.log
        else
            error "Тесты не прошли. Проверьте конфигурацию:"
            cat test_output.log
            rm -f test_output.log
            exit 1
        fi
    fi
}

# Запуск бота
start_bot() {
    log "Запуск бота анализа документов..."
    echo ""
    echo "=== БОТ АНАЛИЗА ДОКУМЕНТОВ ==="
    echo "Для остановки нажмите Ctrl+C"
    echo "=============================="
    echo ""
    
    # Запускаем бота с перенаправлением логов
    python3 main.py 2>&1 | tee -a bot.log
}

# Обработка сигналов
cleanup() {
    echo ""
    log "Завершение работы бота..."
    exit 0
}

trap cleanup SIGINT SIGTERM

# Основная логика
main() {
    echo "🤖 ЗАПУСК БОТА АНАЛИЗА ДОКУМЕНТОВ"
    echo "=================================="
    
    # Проверки системы
    check_python
    check_venv
    install_dependencies
    check_config
    check_env_vars
    
    # Тестирование (опционально)
    if [[ "$1" != "--skip-tests" ]]; then
        test_components
    fi
    
    success "Все проверки пройдены! Запуск бота..."
    echo ""
    
    # Запуск
    start_bot
}

# Помощь
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "Использование: $0 [опции]"
    echo ""
    echo "Опции:"
    echo "  --skip-tests    Пропустить тестирование компонентов"
    echo "  --help, -h      Показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0                    # Полный запуск с тестами"
    echo "  $0 --skip-tests       # Быстрый запуск без тестов"
    echo ""
    exit 0
fi

# Запуск основной функции
main "$@" 