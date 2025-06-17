import datetime

def log_with_timestamp(message: str):
    """Выводит сообщение с timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}") 