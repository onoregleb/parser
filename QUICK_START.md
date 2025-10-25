# 🚀 Быстрый старт - Zara API Parser

## ⚡ Запуск за 3 шага

### 1️⃣ Запустите Docker Compose

```bash
cd parser
docker-compose -f docker-compose-zara.yaml up
```

Это запустит:
- MongoDB сервер
- Парсер мужской коллекции

### 2️⃣ Следите за прогрессом

Логи будут показывать прогресс в реальном времени:

```
🚀 Starting Zara API parser for: male
🔧 Initializing API parser...
⏱️ Задержка между запросами: 0.5-1.5 секунд
📦 Лимит товаров на категорию: 200

📂 Parsing category: man-jackets-l640
✅ Найдено 200 товаров
[1/200] Парсинг товара...
✅ TECHNICAL PUFFER JACKET
   💰 Цена: 49990.0 KZT
   🎨 Цвет: Black
...
```

### 3️⃣ Получите результаты

Результаты будут сохранены в:
- **Файл:** `zara_male_collection.json`
- **MongoDB:** база `zara_db`, коллекция `zara_male_collection`

---

## 🎯 Дополнительные команды

### Запустить женскую коллекцию

```bash
docker-compose -f docker-compose-zara.yaml --profile female up zara-parser-female
```

### Запустить обе коллекции одновременно

```bash
docker-compose -f docker-compose-zara.yaml --profile female up
```

### Остановить парсеры

```bash
docker-compose -f docker-compose-zara.yaml down
```

### Пересобрать контейнеры

```bash
docker-compose -f docker-compose-zara.yaml build --no-cache
docker-compose -f docker-compose-zara.yaml up
```

---

## ⚙️ Настройка

Отредактируйте `config/config_zara.yaml`:

```yaml
request_delay_min: 0.5   # Быстрее = 0.3, Медленнее = 1.0
request_delay_max: 1.5   # Быстрее = 1.0, Медленнее = 2.0
items_limit: 200         # Или None для всех товаров
```

---

## 📊 Просмотр данных в MongoDB

```bash
# Подключитесь к MongoDB
docker exec -it zara-mongo mongosh -u admin123 -p password123

# Выполните команды
use zara_db
db.zara_male_collection.countDocuments()
db.zara_male_collection.findOne()
```

---

## 🐛 Проблемы?

**Порт 27018 занят:**
```bash
# Измените порт в docker-compose-zara.yaml
ports:
  - "27019:27017"  # Используйте другой порт
```

**Слишком медленно:**
```bash
# Уменьшите items_limit в config_zara.yaml
items_limit: 50  # Или 100
```

**Нужна помощь:**
- Смотрите полную документацию в `ZARA_API_PARSER_README.md`
- Проверьте логи: `docker logs -f zara-parser-male`

---

**Всё готово! Запускайте парсер и получайте данные в 10-100 раз быстрее! 🚀**

