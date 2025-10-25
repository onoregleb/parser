# FarFetch Parser

Парсер товаров с сайта FarFetch с поддержкой Docker для параллельного сбора данных.

## 🚀 Запуск через Docker (Рекомендуется)

### Быстрый старт

```bash
# 1. Собрать и запустить все сервисы (MongoDB + 2 парсера)
docker-compose up --build

# 2. Запуск в фоновом режиме
docker-compose up -d --build

# 3. Остановка
docker-compose down
```

### Просмотр логов

```bash
# Логи всех сервисов в реальном времени
docker-compose logs -f

# Логи только мужского парсера
docker-compose logs -f parser-male

# Логи только женского парсера
docker-compose logs -f parser-female

# Последние 100 строк логов
docker-compose logs --tail=100 parser-male

# Логи MongoDB
docker-compose logs -f mongo
```

### Управление отдельными сервисами

```bash
# Запустить только MongoDB
docker-compose up mongo

# Запустить только мужской парсер
docker-compose up parser-male

# Запустить только женский парсер
docker-compose up parser-female

# Перезапустить конкретный сервис
docker-compose restart parser-male

# Остановить конкретный сервис
docker-compose stop parser-female
```

### Очистка

```bash
# Остановить и удалить контейнеры
docker-compose down

# Удалить контейнеры + volumes (ВНИМАНИЕ: удалит данные MongoDB!)
docker-compose down -v

# Пересобрать образы с нуля
docker-compose build --no-cache
```

## 📁 Структура проекта

```
parser/
├── main.py                    # Основной скрипт парсера
├── requirements.txt           # Python зависимости
├── Dockerfile                 # Образ для парсера
├── docker-compose.yaml        # Оркестрация сервисов
├── .dockerignore             # Исключения при сборке образа
├── .gitignore                # Git исключения
├── config/
│   ├── config.yaml           # Конфигурация парсера
│   └── config_models.py      # Pydantic модели конфигурации
├── scripts/
│   └── interfaces.py         # WebDriver, MongoDB, Playwright интерфейсы
├── male_collection.json      # Результаты парсинга (мужчины)
├── female_collection.json    # Результаты парсинга (женщины)
└── mongo_data/               # Данные MongoDB (создается автоматически)
```

## 🐍 Локальный запуск (без Docker)

### Установка зависимостей

```bash
pip install -r requirements.txt
playwright install chromium
```

### Запуск

```bash
# Парсинг мужской коллекции
python main.py --gender male

# Парсинг женской коллекции
python main.py --gender female
```

## ⚙️ Как это работает

### Docker архитектура

1. **mongo** - MongoDB база данных
   - Порт: 27017
   - Данные хранятся в volume `mongo_data`
   - Healthcheck для проверки готовности

2. **parser-male** - Парсер мужской коллекции
   - Зависит от MongoDB
   - Логи пишутся в stdout (доступны через `docker logs`)
   - Результаты сохраняются в `male_collection.json` и MongoDB

3. **parser-female** - Парсер женской коллекции
   - Зависит от MongoDB
   - Логи пишутся в stdout (доступны через `docker logs`)
   - Результаты сохраняются в `female_collection.json` и MongoDB

### Логирование

- **В файлы**: `male_collection.json`, `female_collection.json` (на хосте)
- **В Docker**: все `print()` автоматически попадают в stdout контейнера
- **Ротация**: логи Docker ограничены 10MB × 3 файла (настраивается в docker-compose.yaml)

### Volumes

- `./male_collection.json:/app/male_collection.json` - результаты парсинга мужчин
- `./female_collection.json:/app/female_collection.json` - результаты парсинга женщин
- `./config:/app/config:ro` - конфигурация (read-only)
- `mongo_data:/data/db` - данные MongoDB

## 🔧 Настройка

### MongoDB подключение

Для локального запуска используется `localhost`, для Docker - `mongo` (имя сервиса).
Автоматически определяется через переменную окружения `MONGO_HOST`.

### Конфигурация парсера

Редактируйте `config/config.yaml`:
- URLs категорий
- Время загрузки страниц
- Другие параметры парсинга

## 📊 Мониторинг

```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Проверка подключения к MongoDB
docker exec -it farfetch-mongo mongosh -u admin123 -p password123

# Количество документов в коллекциях
docker exec -it farfetch-mongo mongosh -u admin123 -p password123 farfetch_db \
  --eval "db.male_collection.countDocuments({})"
```

## ❗ Troubleshooting

### Ошибка "Cannot connect to MongoDB"
```bash
# Проверьте, что MongoDB запущен и здоров
docker-compose ps mongo
docker-compose logs mongo

# Перезапустите MongoDB
docker-compose restart mongo
```

### Браузер Playwright не найден
```bash
# Пересоберите образ
docker-compose build --no-cache parser-male parser-female
```

### Файлы JSON не обновляются
```bash
# Проверьте, что файлы существуют на хосте
ls -lh male_collection.json female_collection.json

# Создайте пустые файлы если нужно
echo "[]" > male_collection.json
echo "[]" > female_collection.json
```

### Очистка зависших контейнеров
```bash
docker-compose down
docker system prune -a
```

## 📝 Примечания

- Парсеры работают **параллельно** для ускорения сбора данных
- При падении одного парсера, второй продолжит работу
- Логи автоматически ротируются (не займут весь диск)
- JSON файлы доступны на хосте в реальном времени
- MongoDB данные персистентны (сохраняются между перезапусками)

## 🎯 Рекомендации

1. Запускайте парсеры в фоне: `docker-compose up -d`
2. Следите за логами: `docker-compose logs -f`
3. Периодически проверяйте прогресс в JSON файлах
4. Делайте бэкапы `mongo_data/` для сохранения данных БД

