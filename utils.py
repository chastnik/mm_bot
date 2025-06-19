import datetime

def log_with_timestamp(message: str):
    """Выводит сообщение с timestamp и записывает в лог-файл"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    
    # Также записываем в файл лога
    try:
        with open('bot.log', 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except Exception as e:
        print(f"Ошибка записи в лог: {e}") 