# Инструкция по отладке троекратного ответа бота

## Проблема
Бот отвечает 3 раза на одно сообщение пользователя.

## Добавлена отладка
В код добавлено детальное логирование для выявления причины дублирования:

### 1. Логирование каналов при запуске
- Показывает количество каналов
- Перечисляет все каналы с их ID и названиями

### 2. Логирование получения сообщений  
- Показывает в каком канале найдено сообщение
- Отображает ID сообщения, текст и время
- Выявляет дубликаты сообщений между каналами

### 3. Логирование обработки сообщений
- Детальная информация о каждом этапе обработки
- Проверка защиты от дублирования
- Состояние пользователя

### 4. Логирование отправки ответов
- Каждая отправка сообщения логируется
- Видно какие сообщения отправляются и в какие каналы

## Исправления

### 1. Улучшена дедупликация в цикле прослушивания
- Сообщения собираются из всех каналов
- Удаляются дубликаты по ID
- Обрабатываются только уникальные сообщения

### 2. Фильтрация каналов
- Исключены Direct Messages (D) и Group Messages (G)
- Исключены системные каналы town-square и off-topic
- Бот подключается только к рабочим каналам

### 3. Улучшена логика состояний
- Короткие сообщения в состоянии asking_more_documents игнорируются
- Автоматический сброс состояния при стартовых командах

## Как использовать для отладки

1. **Перезапустите бота** с новым кодом
2. Обратите внимание на вывод при запуске - сколько каналов мониторится
3. Отправьте тестовое сообщение и изучите логи
4. Ищите в логах:
   - `⚠️ ОБНАРУЖЕН ДУБЛИКАТ` - одно сообщение в нескольких каналах
   - `⚠️ ДУБЛИРОВАНИЕ` - повторная обработка того же ID
   - `📤 ОТПРАВКА` - сколько раз отправляется ответ

## Ожидаемый результат
После исправлений бот должен отвечать только один раз на каждое сообщение.

## Если проблема остается
Изучите логи и найдите:
1. Сколько каналов мониторится - должно быть минимальное количество
2. Есть ли дубликаты сообщений между каналами
3. Сколько раз срабатывает отправка ответа
4. В каком состоянии находится пользователь 