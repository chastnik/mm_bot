# Настройка бота для рабочего Mattermost сервера

## Пошаговая инструкция развертывания

### 1. Подготовка сервера

```bash
# Обновляем систему
sudo apt update && sudo apt upgrade -y

# Устанавливаем Python 3.8+
sudo apt install python3 python3-pip python3-venv -y

# Устанавливаем шрифты для PDF
sudo apt install fonts-dejavu fonts-liberation -y

# Устанавливаем git
sudo apt install git -y
```

### 2. Развертывание бота

```bash
# Клонируем репозиторий
git clone <your-repository-url>
cd python

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
3. **Нажмите "Add Bot Account"**
4. **Заполните поля:**
   ```
   Username: document-analyzer-bot
   Display Name: Анализатор документов
   Description: Бот для анализа документации ИТ проектов
   Role: Member (или System Admin для доступа ко всем каналам)
   ```
5. **Сохраните Access Token - это важно!**

#### 3.2 Настройка прав бота

1. **Добавьте бота в команду:**
   - Перейдите в Team Settings
   - Invite Members → Invite Bot
   - Выберите `document-analyzer-bot`

2. **Настройте права канала:**
   - Добавьте бота в нужные каналы
   - Предоставьте права "Post All" и "Use Channel Mentions"

### 4. Получение OpenAI API ключа

1. **Зарегистрируйтесь на https://platform.openai.com/**
2. **Перейдите в API Keys**
3. **Создайте новый API ключ**
4. **Сохраните ключ - он больше не будет показан!**

### 5. Настройка Confluence (если нужно)

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
MATTERMOST_USERNAME=document-analyzer-bot
MATTERMOST_PASSWORD=your-bot-password-if-needed
MATTERMOST_TEAM=your-team-name

# === ОБЯЗАТЕЛЬНЫЕ НАСТРОЙКИ OPENAI ===
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4-turbo

# === НАСТРОЙКИ CONFLUENCE (ОПЦИОНАЛЬНО) ===
CONFLUENCE_USERNAME=your-confluence-email@company.com
CONFLUENCE_PASSWORD=your-confluence-app-password

# === ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ ===
DEBUG=false
LOG_LEVEL=INFO
```

### 7. Тестирование настроек

```bash
# Проверяем все компоненты
python3 test_components.py

# Если все тесты прошли успешно, запускаем бота
python3 main.py
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
WorkingDirectory=/path/to/your/python
Environment=PATH=/path/to/your/python/venv/bin
ExecStart=/path/to/your/python/venv/bin/python main.py
Restart=always
RestartSec=10

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
# Просмотр логов в реальном времени
sudo journalctl -u document-analyzer-bot -f

# Просмотр логов бота
tail -f bot.log

# Проверка статуса сервиса
sudo systemctl status document-analyzer-bot
```

## Проверка работоспособности

### 1. Тест подключения к Mattermost

```bash
curl -H "Authorization: Bearer YOUR_BOT_TOKEN" \
     https://your-mattermost-server.com/api/v4/users/me
```

**Ожидаемый результат:** JSON с информацией о боте

### 2. Тест OpenAI API

```bash
curl -H "Authorization: Bearer YOUR_OPENAI_KEY" \
     https://api.openai.com/v1/models
```

**Ожидаемый результат:** JSON со списком доступных моделей

### 3. Тест бота в Mattermost

1. **Напишите боту в личные сообщения:** `Привет`
2. **Ожидаемый ответ:** Приветственное сообщение с кнопкой "Начать анализ"
3. **Нажмите "Начать анализ"**
4. **Ожидаемый результат:** Кнопки выбора типов проектов

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

### Проблема: "Rate limit exceeded" от OpenAI

**Решение:**
1. Проверьте лимиты в OpenAI dashboard
2. Уменьшите частоту запросов
3. Рассмотрите апгрейд тарифного плана

### Проблема: Русские символы в PDF отображаются как квадратики

**Решение:**
```bash
# Установите русские шрифты
sudo apt install fonts-dejavu fonts-liberation fonts-noto

# Перезапустите бота
sudo systemctl restart document-analyzer-bot
```

## Обновление бота

```bash
# Остановите сервис
sudo systemctl stop document-analyzer-bot

# Обновите код
cd /path/to/your/python
git pull origin main

# Активируйте виртуальное окружение
source venv/bin/activate

# Обновите зависимости
pip install -r requirements.txt

# Запустите сервис
sudo systemctl start document-analyzer-bot
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

## Производительность

### Рекомендуемые ресурсы:
- **CPU:** 2 ядра
- **RAM:** 1GB (минимум 512MB)
- **Диск:** 5GB свободного места
- **Сеть:** Стабильное подключение (минимум 10 Mbps)

### Оптимизация:
- Используйте SSD диски для быстрой обработки файлов
- Настройте ротацию логов
- Мониторьте использование API квот

Готово! Ваш бот настроен для работы с рабочим Mattermost сервером. 🚀 