# Настройка бота для рабочего Mattermost сервера

## Пошаговая инструкция развертывания

### 1. Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python 3.8+
sudo apt install python3 python3-pip python3-venv -y

# Устанавливаем шрифты для PDF (обязательно для корректного отображения русского текста)
sudo apt install fonts-dejavu fonts-liberation fonts-noto -y

# Устанавливаем git
sudo apt install git -y

# Устанавливаем дополнительные зависимости для обработки файлов
sudo apt install libmagic1 -y
```

### 2. Развертывание бота

```bash
# Клонируем репозиторий
git clone https://github.com/chastnik/mm_bot.git
cd mm_bot

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 3. Настройка Mattermost

#### 3.1 Создание бота в Mattermost

1. **Войдите как системный администратор**
2. **Перейдите в System Console > Integrations > Bot Accounts**
3. **Включите Bot Accounts если отключены**
4. **Нажмите "Add Bot Account"**
5. **Заполните поля:**
   ```
   Username: ai_bot (или любое другое имя)
   Display Name: Анализатор документов ИТ проектов
   Description: Бот для анализа документации ИТ проектов с помощью ИИ
   Role: Member (достаточно для работы в Direct Messages)
   ```
6. **Сохраните Access Token - это важно!**

#### 3.2 Настройка прав бота

1. **Добавьте бота в команду:**
   - Перейдите в Team Settings
   - Invite Members → Invite Bot
   - Выберите созданного бота

2. **Важно:** Бот работает **только в Direct Messages** для безопасности
   - Пользователи пишут боту в личные сообщения
   - Бот автоматически обнаруживает новых пользователей каждые 30 секунд

### 4. Настройка корпоративной LLM

**Внимание:** Бот использует корпоративную LLM вместо OpenAI API.

1. **Получите доступ к корпоративной LLM:**
   - Обратитесь к администратору для получения `LLM_PROXY_TOKEN`
   - Уточните базовый URL LLM API
   - Выберите подходящую модель

2. **Проверьте доступность LLM:**
   ```bash
   # Тест подключения к LLM
   python3 test_llm.py
   ```

### 5. Настройка Confluence (опционально)

Если планируется анализ документов из Confluence:

1. **Создайте App Password:**
   - Войдите в Atlassian Account
   - Перейдите в Security → API tokens
   - Создайте новый token
   - Сохраните username и app password

### 6. Конфигурация .env файла

```bash
# Создаем .env файл
cp env.example .env
nano .env
```

**Заполните следующие обязательные поля:**

```env
# === ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ MATTERMOST ===
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_TOKEN=xoxb-your-bot-access-token-here
MATTERMOST_USERNAME=ai_bot
MATTERMOST_PASSWORD=your-bot-password-if-needed
MATTERMOST_TEAM=your-team-name
MATTERMOST_SSL_VERIFY=true  # false для отключения SSL проверки (не рекомендуется)

# === ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ КОРПОРАТИВНОЙ LLM ===
LLM_PROXY_TOKEN=your-llm-proxy-token
LLM_BASE_URL=https://litellm.yourserver.ru  # LiteLLM proxy
LLM_MODEL=gpt-5  # или другая доступная модель через LiteLLM

# === НАСТРОЙКИ CONFLUENCE (ОПЦИОНАЛЬНО) ===
CONFLUENCE_USERNAME=your-confluence-email@company.com
CONFLUENCE_PASSWORD=your-confluence-app-password
CONFLUENCE_BASE_URL=https://confluence.yourcompany.ru/

# === ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ===
DEBUG=false
LOG_LEVEL=INFO
```

### 7. Тестирование настроек

```bash
# Проверяем все компоненты
python3 test_components.py

# Проверяем подключение к LLM
python3 test_llm.py

# Если все тесты прошли успешно, запускаем бота
python3 main.py
```

**Ожидаемый вывод при успешном запуске:**
```
🤖 Запуск бота анализа документов...
✅ Сервер отвечает. Status: 200
Бот успешно подключился к Mattermost
📋 Инициализация команд и каналов...
✅ Добавлен Direct Message канал: [каналы пользователей]
👂 Начинаю слушать сообщения с времени: [timestamp]
🔗 Подключен к каналам: [количество]
```

### 8. Настройка автозапуска (systemd)

Создайте systemd сервис для автоматического запуска:

```bash
sudo nano /etc/systemd/system/document-analyzer-bot.service
```

```ini
[Unit]
Description=Document Analyzer Bot for Mattermost
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/your/mm_bot
Environment=PATH=/path/to/your/mm_bot/venv/bin
ExecStart=/path/to/your/mm_bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/your/mm_bot/bot.log
StandardError=append:/path/to/your/mm_bot/bot.log

[Install]
WantedBy=multi-user.target
```

Активируйте сервис:
```bash
sudo systemctl daemon-reload
sudo systemctl enable document-analyzer-bot
sudo systemctl start document-analyzer-bot
sudo systemctl status document-analyzer-bot
```

### 9. Мониторинг и логи

```bash
# Просмотр логов systemd в реальном времени
sudo journalctl -u document-analyzer-bot -f

# Просмотр логов бота
tail -f bot.log

# Проверка статуса сервиса
sudo systemctl status document-analyzer-bot

# Поиск новых пользователей в логах
grep "🆕 Обнаружен новый Direct Message канал" bot.log
```

## Проверка работоспособности

### 1. Тест подключения к Mattermost

```bash
curl -H "Authorization: Bearer YOUR_BOT_TOKEN" \
     https://your-mattermost-server.com/api/v4/users/me
```

**Ожидаемый результат:** JSON с информацией о боте

### 2. Тест корпоративной LLM

```bash
# Используйте скрипт проверки
python3 test_llm.py
```

**Ожидаемый результат:** Успешный ответ от LLM

### 3. Тест бота в Mattermost

1. **Напишите боту в личные сообщения:** `Привет`
2. **Ожидаемый ответ:** Приветственное сообщение с инструкциями
3. **Напишите:** `начать анализ`
4. **Ожидаемый результат:** Меню выбора типов проектов (BI, DWH, RPA, MDM)

### 4. Тест многопользовательской работы

1. **Попросите коллегу написать боту с другой учетки**
2. **Проверьте логи:** должно появиться сообщение `🆕 Обнаружен новый Direct Message канал`
3. **Убедитесь:** что бот отвечает в течение 30 секунд

## Новые функции (версия 2025-06-19)

### Автоматическое обнаружение новых пользователей
- ✅ Бот автоматически обнаруживает новых пользователей каждые 30 секунд
- ✅ Поддержка неограниченного количества пользователей одновременно
- ✅ Каждый пользователь имеет независимую сессию

### Улучшенная обработка документов
- ✅ Поддержка PDF, DOCX, XLSX, RTF файлов
- ✅ Анализ ссылок Confluence
- ✅ Генерация PDF отчетов с русскими шрифтами

## Устранение проблем

### Проблема: "Connection refused" к Mattermost

**Решение:**
```bash
# Проверьте доступность сервера
ping your-mattermost-server.com

# Проверьте порт
telnet your-mattermost-server.com 443

# Проверьте SSL сертификат
openssl s_client -connect your-mattermost-server.com:443
```

### Проблема: "Invalid token" от Mattermost

**Решение:**
1. Пересоздайте токен бота в Mattermost
2. Обновите `MATTERMOST_TOKEN` в `.env`
3. Перезапустите бота

### Проблема: "SSL verification failed"

**Решение:**
```env
# В .env файле установите:
MATTERMOST_SSL_VERIFY=false
```
**Внимание:** Отключение SSL проверки снижает безопасность!

### Проблема: Бот не отвечает новым пользователям

**Диагностика:**
```bash
# Проверьте логи на наличие новых каналов
grep "🆕 Обнаружен новый Direct Message канал" bot.log

# Если нет - проверьте права бота в команде
```

### Проблема: "Rate limit exceeded" от LLM

**Решение:**
1. Проверьте квоты в LLM системе
2. Уменьшите частоту запросов
3. Обратитесь к администратору LLM

### Проблема: Русские символы в PDF отображаются неверно

**Решение:**
```bash
# Установите дополнительные шрифты
sudo apt install fonts-dejavu fonts-liberation fonts-noto fonts-freefont-ttf

# Перезапустите бота
sudo systemctl restart document-analyzer-bot
```

### Проблема: Ошибки обработки файлов

**Решение:**
```bash
# Установите libmagic для определения типов файлов
sudo apt install libmagic1

# Проверьте права на временную папку
sudo chmod 777 /tmp
```

## Обновление бота

```bash
# Остановите сервис
sudo systemctl stop document-analyzer-bot

# Обновите код
cd /path/to/your/mm_bot
git pull origin main

# Активируйте виртуальное окружение
source venv/bin/activate

# Обновите зависимости
pip install -r requirements.txt

# Запустите сервис
sudo systemctl start document-analyzer-bot

# Проверьте статус
sudo systemctl status document-analyzer-bot
```

## Безопасность

### 1. Защита .env файла
```bash
chmod 600 .env        # Только владелец может читать
chown your-user:your-user .env
```

### 2. Настройка файрвола
```bash
# Разрешить только исходящие HTTPS соединения
sudo ufw allow out 443
sudo ufw allow out 80
```

### 3. Ротация токенов
- Обновляйте токены каждые 90 дней
- Используйте разные токены для разных окружений
- Не коммитьте токены в git

### 4. Мониторинг безопасности
- Регулярно проверяйте логи на подозрительную активность
- Ограничьте доступ к серверу с ботом
- Используйте HTTPS для всех соединений

## Производительность

### Рекомендуемые ресурсы:
- **CPU:** 2 ядра (минимум 1 ядро)
- **RAM:** 2GB (минимум 1GB)
- **Диск:** 10GB свободного места
- **Сеть:** Стабильное подключение (минимум 10 Mbps)

### Оптимизация:
- Используйте SSD диски для быстрой обработки файлов
- Настройте ротацию логов: `logrotate`
- Мониторьте использование LLM квот
- Регулярно очищайте временные файлы

### Мониторинг производительности:
```bash
# Мониторинг использования ресурсов
htop

# Размер логов
du -h bot.log

# Статистика запросов к LLM
grep "Отправляю запрос к LLM" bot.log | wc -l
```