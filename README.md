# BIT.Digital Mattermost Document Analyzer Bot 🤖📄

[![GitHub](https://img.shields.io/badge/GitHub-chastnik%2Fmm__bot-blue?style=flat&logo=github)](https://github.com/chastnik/mm_bot)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat&logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

Для БИТ.Цифры: Интеллектуальный бот для анализа документации ИТ проектов с использованием GPT и автоматической генерацией PDF отчетов в Mattermost.

## 🚀 Возможности

- **Интерактивный интерфейс**: Выбор типов проектов (BI, DWH, RPA, MDM)
- **Многоформатная поддержка**: PDF, DOCX, DOC, XLSX, RTF, TXT файлы
- **Confluence интеграция**: Анализ страниц Confluence по ссылкам (включая дочерние страницы и приложенные файлы)
- **ИИ анализ**: Использование LLM для поиска артефактов в документах
- **PDF отчеты**: Автоматическая генерация структурированных отчетов

## 🛠 Установка и настройка

### 1. Клонирование репозитория
```bash
git clone https://github.com/chastnik/mm_bot.git
cd mm_bot
```

### 2. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` на основе `env.example`:
```bash
cp env.example .env
```

### 5. Создание бота в Mattermost

1. **Создайте бота в Mattermost:**
   - Перейдите в **System Console** > **Integrations** > **Bot Accounts**
   - Нажмите **Add Bot Account**
   - Заполните данные бота:
     - **Username**: `document-analyzer-bot`
     - **Display Name**: `Анализатор документов`
     - **Description**: `Бот для анализа документации ИТ проектов`
   - Сохраните **Access Token**

2. **Настройте права бота:**
   - Добавьте бота в нужную команду
   - Предоставьте права на чтение/запись сообщений
   - Разрешите загрузку файлов

### 6. Проверка настроек

Запустите тест компонентов:
```bash
python3 test_components.py
```

## ▶️ Запуск бота

### Производственный запуск
```bash
python3 main.py
```

### Запуск с логированием
```bash
./start_bot.sh
```

### Фоновый запуск (Linux/Mac)
```bash
nohup python3 main.py > bot.log 2>&1 &
```

### Запуск в Docker (планируется)
```bash
# Coming soon
docker-compose up -d
```

## 📖 Использование

### 🎯 Быстрый старт с интерактивными командами

1. **Начало анализа**: `🚀 Начать анализ`
2. **Выбор типов проектов**: `📋 BI`, `📋 DWH`, `📋 RPA`, `📋 MDM`
3. **Загрузка документов**: 
   - Прикрепите файлы (PDF, DOCX, XLSX, RTF, TXT)
   - Или отправьте ссылки на Confluence страницы
4. **Управление процессом**: `➕ Добавить документы` или `🔄 Начать анализ`
5. **Получение отчета**: Бот создаст и отправит PDF отчет
6. **Новый анализ**: `🚀 Новый анализ`


## 📁 Структура проекта

```
mm_bot/
├── main.py                 # Точка входа приложения
├── config.py              # Управление конфигурацией
├── mattermost_bot.py      # Основной класс бота
├── document_processor.py  # Обработка документов
├── llm_analyzer.py        # Анализ с помощью LLM
├── gpt_analyzer.py        # GPT-специфичный анализатор
├── pdf_generator.py       # Генерация PDF отчетов
├── utils.py               # Вспомогательные функции
├── requirements.txt       # Python зависимости
├── env.example           # Пример настроек окружения
├── start_bot.sh          # Скрипт запуска
├── check_ssl.py          # Проверка SSL соединений
├── test_components.py    # Тесты компонентов
├── test_llm.py           # Тесты LLM интеграции
├── README.md             # Документация проекта
├── SETUP_PRODUCTION.md   # Руководство по продакшн развертыванию
├── SSL_TROUBLESHOOTING.md # Руководство по устранению SSL проблем
├── .github/              # GitHub Actions и настройки
│   └── dependabot.yml    # Автоматические обновления зависимостей
└── .devcontainer/        # VS Code Dev Container конфигурация
    └── devcontainer.json
```

## 🔧 Устранение неполадок

### Проблемы с подключением к Mattermost
```bash
# Проверьте доступность сервера
curl -I https://your-mattermost-server.com

# Проверьте токен бота
curl -H "Authorization: Bearer your_token" \
     https://your-mattermost-server.com/api/v4/users/me
```

### Проблемы с SSL соединениями
Запустите диагностический скрипт:
```bash
python3 check_ssl.py
```

### Проблемы с русскими символами в PDF
Система автоматически использует шрифты DejaVu Sans для корректного отображения кириллицы. Если возникают проблемы:

```bash
# Ubuntu/Debian
sudo apt-get install fonts-dejavu

# CentOS/RHEL
sudo yum install dejavu-sans-fonts
```

## 📊 Логирование

Логи сохраняются в:
- `bot.log` - основные события
- `bot_output.log` - вывод приложения
- Консольный вывод с настраиваемым уровнем детализации

Уровень логирования настраивается через переменную `LOG_LEVEL` в `.env`.

## 💻 Требования к системе

- **Python**: 3.8+
- **RAM**: минимум 512MB (рекомендуется 1GB+)
- **Диск**: 100MB для кода + место для временных файлов
- **Сеть**: доступ к Mattermost, LiteLLM (`https://litellm.1bitai.ru`), Confluence
- **ОС**: Linux, macOS, Windows
- **Рекомендуется**: использовать Pyright для проверки типизации кода

## 🔒 Безопасность

- Все API ключи храните в переменных окружения
- Используйте HTTPS для всех подключений
- Регулярно обновляйте токены доступа
- Ограничьте права бота только необходимыми каналами
- Настройте правильную конфигурацию SSL/TLS

## 🆘 Поддержка

Для получения помощи:

1. 📋 Проверьте логи бота
2. 🧪 Запустите `test_components.py` для диагностики
3. ⚙️ Убедитесь в корректности всех настроек в `.env`
4. 🐛 Создайте Issue в [GitHub репозитории](https://github.com/chastnik/mm_bot/issues)
5. 💬 Обратитесь к [документации Mattermost API](https://api.mattermost.com/)

## 📄 Лицензия

Этот проект лицензирован под MIT License - смотрите файл [LICENSE](LICENSE) для подробностей.

## 🌟 Авторы

- **@chastnik** - *Первоначальная разработка* - [GitHub](https://github.com/chastnik)
