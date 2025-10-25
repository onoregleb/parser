# 🚀 Быстрый старт - Zara Parser

## Простой запуск (3 команды)

### 1️⃣ Запуск мужской коллекции

```bash
cd parser
docker-compose -f docker-compose-zara.yaml up --build
```

### 2️⃣ Запуск женской коллекции

```bash
cd parser
docker-compose -f docker-compose-zara.yaml --profile female up --build
```

### 3️⃣ Остановка

```bash
docker-compose -f docker-compose-zara.yaml down
```

---

## 🎯 Интерактивный запуск (рекомендуется)

```bash
cd parser
./start-zara.sh
```

Выберите нужное действие из меню:
1. Запустить парсер MALE
2. Запустить парсер FEMALE  
3. Запустить оба парсера
4. Остановить все
5. Посмотреть логи
6. Очистить данные
7. MongoDB консоль
8. Выход

---

## 📊 Результаты парсинга

После завершения найдете:

- **JSON файлы:**
  - `zara_male_collection.json`
  - `zara_female_collection.json`

- **MongoDB:**
  - База: `zara_db`
  - Коллекции: `zara_male_collection`, `zara_female_collection`
  - Порт: `27018`

---

## 🔍 Просмотр данных

### MongoDB консоль:

```bash
docker exec -it zara-mongo mongosh -u admin123 -p password123
```

```javascript
use zara_db
db.zara_male_collection.countDocuments()  // Количество товаров
db.zara_male_collection.find().limit(5)   // Первые 5 товаров
```

### Логи парсера:

```bash
docker logs -f zara-parser-male
```

---

## ⚙️ Настройки

Файл: `config/config_zara.yaml`

```yaml
items_limit: 200               # Лимит товаров на категорию
request_delay_min: 24          # Минимальная задержка (сек)
request_delay_max: 60          # Максимальная задержка (сек)
```

---

## ❓ Частые вопросы

**Q: Сколько длится парсинг?**  
A: ~2-4 часа на 1 категорию (200 товаров), ~20-40 часов на все 10 категорий.

**Q: Можно ли ускорить?**  
A: Да, уменьшите задержки в `config_zara.yaml`, но есть риск блокировки.

**Q: Как остановить парсинг?**  
A: Нажмите `Ctrl+C` в терминале, затем `docker-compose -f docker-compose-zara.yaml down`

**Q: Где данные?**  
A: В JSON файлах (`zara_male_collection.json`) и MongoDB (порт 27018)

**Q: Конфликт с Farfetch?**  
A: Нет, используются разные порты (27018 vs 27017) и имена контейнеров.

---

## 📝 Полная документация

См. [README_ZARA.md](README_ZARA.md)

---

**Готово! 🎉 Запускайте и парсите!**

