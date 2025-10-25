import argparse
import json
import os
import sys

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.interfaces import MongoInterface
from config.config_models import ZaraConfig
from zara_api_parser import ZaraAPIParser


arguments_parser = argparse.ArgumentParser(description="Zara argument parser")
arguments_parser.add_argument(
    "--gender",
    type=str,
    choices=["male", "female"],
    required=True,
    help="Male or Female catalog"
)


def save_to_mongo(mongo, collection, data):
    """Сохранение данных в MongoDB"""
    for sample in data:
        mongo.insert_data(collection, sample)


def save_to_file(filepath: str, data):
    """Сохранение данных в JSON файл"""
    print(f"💾 Сохранение в файл {filepath}...", flush=True)
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            info = json.load(file)
    except FileNotFoundError:
        info = []

    info.extend(data)
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(info, file, ensure_ascii=False, indent=4)
    print(f"✅ Сохранено {len(data)} товаров в файл", flush=True)


def run_scrapper(config: ZaraConfig, gender: str):
    """Основная функция парсинга через API"""
    print(f"🚀 Starting Zara API parser for: {gender}", flush=True)
    print(f"⏰ Timestamp: {__import__('datetime').datetime.now()}", flush=True)

    print("🔧 Initializing API parser...", flush=True)
    parser = ZaraAPIParser(
        request_delay=(config.request_delay_min, config.request_delay_max),
        items_limit=config.items_limit
    )
    print("✅ API parser initialized", flush=True)
    print(f"⏱️ Задержка между запросами: {config.request_delay_min}-{config.request_delay_max} секунд", flush=True)
    print(f"📦 Лимит товаров на категорию: {config.items_limit}", flush=True)
    
    # Подключение к MongoDB
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    print(f"🔌 Connecting to MongoDB at {mongo_host}:27017...", flush=True)
    mongo = MongoInterface(f"mongodb://admin123:password123@{mongo_host}:27017/", database="zara_db")
    print("✅ MongoDB connected", flush=True)
    
    try:
        print(f"📁 Creating collection: zara_{gender}_collection", flush=True)
        mongo.create_collection(f"zara_{gender}_collection")
        print("✅ Collection created", flush=True)
    except Exception as e:
        print(f"ℹ️ Collection already exists or error: {e}", flush=True)

    # Получаем URL и категории из конфига
    base_url = getattr(config, gender).url
    categories = getattr(config, gender).categories
    
    # Парсим категории
    total_products = 0
    
    for category in categories:
        # Формируем полный URL категории
        category_url = base_url.format(category=category)
        
        # Извлекаем название категории из URL
        category_name = category.split('.html')[0]
        
        print(f"\n{'='*70}", flush=True)
        print(f"📂 Parsing category: {category_name}", flush=True)
        print(f"🔗 URL: {category_url}", flush=True)
        print(f"{'='*70}", flush=True)
        
        try:
            # Парсим категорию через API
            parsed_data = parser.parse_category(category_url, category_name)
            
            if not parsed_data:
                print(f"⚠️ Не найдено товаров в категории {category_name}", flush=True)
                continue
            
            # Добавляем информацию о гендере
            for product in parsed_data:
                product['gender'] = gender
            
            print(f"\n💾 Сохранение {len(parsed_data)} товаров...", flush=True)
            
            # Сохраняем в файл
            save_to_file(f"zara_{gender}_collection.json", parsed_data)
            
            # Сохраняем в MongoDB
            save_to_mongo(mongo, f"zara_{gender}_collection", parsed_data)
            
            total_products += len(parsed_data)
            print(f"✅ Успешно сохранено {len(parsed_data)} товаров из категории {category_name}", flush=True)
            
        except Exception as exc:
            print(f"❌ Error in parsing category: {category_name}", flush=True)
            print(f"   Error: {str(exc)}", flush=True)
            continue
    
    print(f"\n{'='*70}", flush=True)
    print(f"✅ Парсинг завершен!", flush=True)
    print(f"📊 Всего спарсено товаров: {total_products}", flush=True)
    print(f"{'='*70}", flush=True)


if __name__ == "__main__":
    args = arguments_parser.parse_args()

    config = ZaraConfig.from_yaml("config/config_zara.yaml")
    run_scrapper(config=config, gender=args.gender)

