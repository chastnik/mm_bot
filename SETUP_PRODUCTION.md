# Настройка бота в production через Docker

Документ описывает установку и обновление `Mattermost Document Analyzer Bot` только через Docker-скрипты:

- `install_prod_docker.sh` - первичная установка;
- `update_prod_docker.sh` - обновление уже установленного бота.

## 1. Что подготовить заранее

### Сервер

- Linux-сервер с выходом в интернет.
- Права пользователя с `sudo` (или root).
- Установленный `git`.

### Доступы

- Доступ к Mattermost (URL сервера, бот-токен, имя команды).
- Доступ к корпоративной LLM (`LLM_PROXY_TOKEN`, `LLM_BASE_URL`, `LLM_MODEL`).
- Доступ к Confluence (если используете ссылки в анализе).

## 2. Подготовка бота в Mattermost

1. Войдите в Mattermost под администратором.
2. Откройте `System Console -> Integrations -> Bot Accounts`.
3. Создайте бот-аккаунт и сохраните `Access Token`.
4. Добавьте бота в нужную команду (`Team`), в которой пользователи будут писать боту в DM.

## 3. Клонирование репозитория

```bash
git clone https://github.com/chastnik/mm_bot.git
cd mm_bot
```

## 4. Настройка `.env`

Скопируйте шаблон:

```bash
cp env.example .env
```

Заполните обязательные переменные:

```env
# Mattermost
MATTERMOST_URL=https://your-mattermost-server.com
MATTERMOST_TOKEN=your_bot_token_here
MATTERMOST_USERNAME=your_bot_username
MATTERMOST_PASSWORD=your_bot_password
MATTERMOST_TEAM=your_team_name
MATTERMOST_SSL_VERIFY=true

# Confluence
CONFLUENCE_BASE_URL=https://confluence.yourcompany.ru/

# LLM
LLM_PROXY_TOKEN=sk-your-token
LLM_BASE_URL=https://litellm.yourserver.ru
LLM_MODEL=gpt-5

# Опционально
DEBUG=false
LOG_LEVEL=INFO
SETTINGS_DB_PATH=data/bot_settings.db
```

Важно:

- скрипты проверяют, что обязательные переменные заполнены;
- плейсхолдеры вида `your_*` и `https://your-*` считаются незаполненными;
- если `.env` отсутствует, `install_prod_docker.sh` создаст его из `env.example` и завершится с подсказкой заполнить файл.

## 5. Первичная установка (Docker)

Запустите:

```bash
./install_prod_docker.sh
```

Что делает скрипт:

1. Проверяет, что запуск из корня проекта.
2. Устанавливает Docker и Compose (для Debian/Ubuntu через `apt-get`), если их нет.
3. Проверяет доступность Docker daemon.
4. Проверяет `.env`.
5. Собирает образ (`build --pull`) и поднимает контейнер.
6. Выполняет инициализацию БД настроек внутри контейнера:
   ```bash
   python init_settings_db.py
   ```
7. Проверяет, что контейнер `ai-docs-bot` запущен.

## 6. Проверка после установки

```bash
docker compose ps
docker compose logs -f --tail=200
```

Ожидается:

- контейнер `ai-docs-bot` в состоянии `Up`;
- в логах нет ошибок валидации конфигурации (`Config().validate()`).

Дополнительно проверьте в Mattermost:

1. Напишите боту в личные сообщения.
2. Отправьте команду `начать анализ`.
3. Убедитесь, что бот отвечает и запускает сценарий.

## 7. Обновление установленного бота

Для обновления используйте:

```bash
./update_prod_docker.sh
```

Что делает скрипт:

1. Проверяет `.git`, `Dockerfile`, `docker-compose.yml` и `.env`.
2. Делает `git fetch --all --prune`.
3. Выполняет fast-forward обновление текущей ветки:
   ```bash
   git pull --ff-only origin <current_branch>
   ```
4. Проверяет `.env`.
5. Останавливает текущий контейнер (`down`).
6. Пересобирает и запускает контейнер (`up -d --build --remove-orphans`).
7. Повторно применяет инициализацию/миграции `init_settings_db.py`.
8. Проверяет, что контейнер `ai-docs-bot` запущен.

## 8. Полезные команды эксплуатации

```bash
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d
```

Проверка healthcheck:

```bash
docker inspect --format='{{json .State.Health}}' ai-docs-bot
```

## 9. Типовые проблемы

### Docker daemon недоступен

Проверьте сервис Docker:

```bash
sudo systemctl status docker
sudo systemctl restart docker
```

### Ошибка: не заполнены переменные `.env`

- Откройте `.env`.
- Заполните все обязательные поля реальными значениями.
- Повторите запуск нужного скрипта.

### Ошибка `git pull --ff-only`

Обычно означает, что есть локальные коммиты или расхождение истории.

Рекомендуемый путь:

1. Разберите локальные изменения (`git status`).
2. Синхронизируйте ветку вручную.
3. Повторно запустите `./update_prod_docker.sh`.

### Бот не отвечает в Mattermost

Проверьте:

- правильность `MATTERMOST_URL`, `MATTERMOST_TOKEN`, `MATTERMOST_TEAM`;
- добавлен ли бот в нужную команду;
- логи контейнера:
  ```bash
  docker compose logs -f --tail=300
  ```

## 10. Безопасность

- Не коммитьте `.env`.
- Установите права на `.env`:

```bash
chmod 600 .env
```

- Используйте `MATTERMOST_SSL_VERIFY=true` в production.
- Храните токены и пароли только в секретах/`.env` на сервере.