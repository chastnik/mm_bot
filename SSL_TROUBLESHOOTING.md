# Устранение проблем с SSL сертификатами

## Проблема

Если вы видите предупреждения типа:
```
InsecureRequestWarning: Unverified HTTPS request is being made to host 'mm.1bit.support'
```

Это означает, что SSL сертификат сервера не прошел проверку.

## Решения

### 1. Рекомендуемое решение: Исправить SSL сертификат

**Обратитесь к администратору Mattermost сервера** для исправления SSL сертификата:

- Установить корректный SSL сертификат
- Обновить цепочку доверия
- Проверить срок действия сертификата
- Настроить правильные DNS записи

### 2. Проверка SSL сертификата

Проверьте SSL сертификат вашего сервера:

```bash
# Проверка SSL сертификата
openssl s_client -connect mm.1bit.support:443 -servername mm.1bit.support

# Проверка через браузер
# Откройте https://mm.1bit.support в браузере и проверьте сертификат
```

### 3. Временное отключение SSL проверки (НЕ РЕКОМЕНДУЕТСЯ)

⚠️ **ВНИМАНИЕ**: Это снижает безопасность соединения!

Если нужно временно отключить проверку SSL, добавьте в `.env` файл:

```env
MATTERMOST_SSL_VERIFY=false
```

**Используйте это только:**
- В тестовых средах
- Как временное решение
- Когда вы полностью доверяете сети

### 4. Добавление сертификата в доверенные (Linux)

Если у вас есть правильный сертификат, но он не входит в цепочку доверия:

```bash
# Скачиваем сертификат
echo -n | openssl s_client -connect mm.1bit.support:443 | sed -ne '/-BEGIN CERTIFICATE-/,/-END CERTIFICATE-/p' > mm.1bit.support.crt

# Добавляем в доверенные (Ubuntu/Debian)
sudo cp mm.1bit.support.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates

# Добавляем в доверенные (CentOS/RHEL)
sudo cp mm.1bit.support.crt /etc/pki/ca-trust/source/anchors/
sudo update-ca-trust

# Перезапускаем бота
sudo systemctl restart document-analyzer-bot
```

### 5. Проверка настроек файрвола/прокси

Если используются корпоративные прокси или файрволы:

```bash
# Проверка доступности порта
telnet mm.1bit.support 443

# Проверка через curl
curl -I https://mm.1bit.support

# Проверка с отладкой SSL
curl -v https://mm.1bit.support
```

## Настройка в .env файле

### Безопасная настройка (рекомендуется):
```env
MATTERMOST_URL=https://mm.1bit.support
MATTERMOST_SSL_VERIFY=true
```

### Небезопасная настройка (только для тестирования):
```env
MATTERMOST_URL=https://mm.1bit.support
MATTERMOST_SSL_VERIFY=false
```

## Проверка результата

После исправления SSL проблем:

1. **Перезапустите бота:**
   ```bash
   sudo systemctl restart document-analyzer-bot
   ```

2. **Проверьте логи:**
   ```bash
   sudo journalctl -u document-analyzer-bot -f
   ```

3. **Убедитесь, что предупреждения исчезли**

## Дополнительная диагностика

### Проверка SSL через Python:
```python
import ssl
import socket

def check_ssl(hostname, port=443):
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                print(f"✅ SSL соединение успешно: {ssock.version()}")
                print(f"Сертификат: {ssock.getpeercert()['subject']}")
    except Exception as e:
        print(f"❌ SSL ошибка: {e}")

check_ssl('mm.1bit.support')
```

### Проверка с помощью бота:
```bash
# Запуск тестов компонентов
python3 test_components.py

# Должен пройти тест подключения к Mattermost без предупреждений
```

## Безопасность

### ✅ Рекомендуется:
- Использовать `MATTERMOST_SSL_VERIFY=true`
- Исправить SSL сертификат на сервере
- Регулярно обновлять сертификаты
- Мониторить срок действия сертификатов

### ❌ Не рекомендуется:
- Постоянно использовать `MATTERMOST_SSL_VERIFY=false`
- Игнорировать SSL предупреждения
- Использовать самоподписанные сертификаты в продакшене

## Контакты

Если проблема не решается:
1. Обратитесь к администратору Mattermost сервера
2. Проверьте документацию Mattermost по SSL
3. Создайте issue в репозитории проекта 