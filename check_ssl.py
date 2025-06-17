#!/usr/bin/env python3
"""
Скрипт для диагностики SSL соединения с Mattermost сервером
"""

import ssl
import socket
import requests
import urllib3
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

def check_ssl_certificate(hostname, port=443):
    """Проверяет SSL сертификат сервера"""
    print(f"🔍 Проверка SSL сертификата: {hostname}:{port}")
    print("-" * 50)
    
    try:
        # Создаем SSL контекст
        context = ssl.create_default_context()
        
        # Устанавливаем соединение
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # Получаем информацию о сертификате
                cert = ssock.getpeercert()
                
                print(f"✅ SSL соединение успешно установлено")
                print(f"   Версия TLS: {ssock.version()}")
                print(f"   Шифр: {ssock.cipher()}")
                
                # Информация о сертификате
                subject = dict(x[0] for x in cert['subject'])
                issuer = dict(x[0] for x in cert['issuer'])
                
                print(f"\n📋 Информация о сертификате:")
                print(f"   Выдан для: {subject.get('commonName', 'Не указано')}")
                print(f"   Выдан: {issuer.get('organizationName', 'Не указано')}")
                print(f"   Действителен с: {cert.get('notBefore', 'Не указано')}")
                print(f"   Действителен до: {cert.get('notAfter', 'Не указано')}")
                
                # Альтернативные имена
                san = cert.get('subjectAltName', [])
                if san:
                    print(f"   Альтернативные имена: {', '.join([name[1] for name in san])}")
                
                return True
                
    except ssl.SSLError as e:
        print(f"❌ SSL ошибка: {e}")
        return False
    except socket.timeout:
        print(f"❌ Таймаут соединения")
        return False
    except Exception as e:
        print(f"❌ Ошибка соединения: {e}")
        return False

def check_http_response(url, verify_ssl=True):
    """Проверяет HTTP ответ сервера"""
    print(f"\n🌐 Проверка HTTP ответа: {url}")
    print("-" * 50)
    
    try:
        # Отключаем предупреждения SSL если нужно
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.get(url, timeout=10, verify=verify_ssl)
        
        print(f"✅ HTTP ответ получен")
        print(f"   Статус: {response.status_code}")
        print(f"   Сервер: {response.headers.get('Server', 'Не указано')}")
        print(f"   Тип содержимого: {response.headers.get('Content-Type', 'Не указано')}")
        
        if not verify_ssl:
            print(f"⚠️  SSL проверка была отключена")
        
        return True
        
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL ошибка HTTP: {e}")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения: {e}")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Таймаут HTTP запроса")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    """Основная функция диагностики"""
    print("🔧 ДИАГНОСТИКА SSL СОЕДИНЕНИЯ С MATTERMOST")
    print("=" * 60)
    
    # Загружаем конфигурацию
    load_dotenv()
    
    mattermost_url = os.getenv('MATTERMOST_URL', '')
    ssl_verify = os.getenv('MATTERMOST_SSL_VERIFY', 'true').lower() == 'true'
    
    if not mattermost_url:
        print("❌ MATTERMOST_URL не задан в .env файле")
        print("Используем тестовый URL: https://mm.1bit.support")
        mattermost_url = "https://mm.1bit.support"
    
    print(f"📝 Настройки:")
    print(f"   URL: {mattermost_url}")
    print(f"   SSL проверка: {'включена' if ssl_verify else 'отключена'}")
    print()
    
    # Парсим URL
    parsed = urlparse(mattermost_url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    
    if not hostname:
        print("❌ Некорректный URL в MATTERMOST_URL")
        return False
    
    # 1. Проверяем SSL сертификат
    ssl_ok = check_ssl_certificate(hostname, port)
    
    # 2. Проверяем HTTP ответ с SSL проверкой
    if ssl_ok:
        http_ok = check_http_response(mattermost_url, verify_ssl=True)
    else:
        print(f"\n⚠️  SSL сертификат имеет проблемы. Пробуем без проверки SSL...")
        http_ok = check_http_response(mattermost_url, verify_ssl=False)
    
    # Итоговый результат
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТ ДИАГНОСТИКИ")
    print("=" * 60)
    
    if ssl_ok and http_ok:
        print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
        print("   SSL сертификат корректный")
        print("   HTTP соединение работает")
        print("   Рекомендация: MATTERMOST_SSL_VERIFY=true")
        
    elif http_ok and not ssl_ok:
        print("⚠️  ЧАСТИЧНЫЙ УСПЕХ")
        print("   HTTP соединение работает")
        print("   SSL сертификат имеет проблемы")
        print("   Рекомендация:")
        print("     - Исправить SSL сертификат на сервере (предпочтительно)")
        print("     - Временно: MATTERMOST_SSL_VERIFY=false")
        
    else:
        print("❌ ПРОБЛЕМЫ С ПОДКЛЮЧЕНИЕМ")
        print("   Сервер недоступен или имеет серьезные проблемы")
        print("   Рекомендация:")
        print("     - Проверить доступность сервера")
        print("     - Проверить настройки сети/файрвола")
        print("     - Обратиться к администратору сервера")
    
    print("\n💡 ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ДЛЯ ДИАГНОСТИКИ:")
    print(f"   curl -I {mattermost_url}")
    print(f"   openssl s_client -connect {hostname}:{port}")
    print(f"   telnet {hostname} {port}")
    
    return ssl_ok and http_ok

if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Диагностика прервана пользователем")
        exit(1)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        exit(1) 