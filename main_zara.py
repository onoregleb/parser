import argparse
import json

from scripts.interfaces import ZaraPlaywrightInterface, MongoInterface
from config.config_models import ZaraConfig


arguments_parser = argparse.ArgumentParser(description="Zara argument parser")
arguments_parser.add_argument(
    "--gender",
    type=str,
    choices=["male", "female"],
    required=True,
    help="Male or Female catalog"
)


def save_to_mongo(mongo, collection, data):
    for sample in data:
        mongo.insert_data(collection, sample)


def save_to_file(filepath: str, data):
    print("SAVING")
    print(data)
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            info = json.load(file)
    except FileNotFoundError:
        info = []

    info.extend(data)
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(info, file, ensure_ascii=False, indent=4)


def run_scrapper(config: ZaraConfig, gender: str):
    print(f"🚀 Starting Zara parser for: {gender}", flush=True)
    print(f"⏰ Timestamp: {__import__('datetime').datetime.now()}", flush=True)

    print("🌐 Initializing Playwright browser...", flush=True)
    driver = ZaraPlaywrightInterface(
        page_loading_time=config.page_loading_time,
        request_delay=(config.request_delay_min, config.request_delay_max),
        items_limit=config.items_limit
    )
    print("✅ Browser initialized", flush=True)
    print(f"⏱️ Задержка между запросами: {config.request_delay_min}-{config.request_delay_max} секунд", flush=True)
    print(f"📦 Лимит товаров на категорию: {config.items_limit}", flush=True)
    
    # Используем 'mongo' как имя хоста в Docker, 'localhost' для локального запуска
    import os
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

    urls = getattr(config, gender).urls
    categories = getattr(config, gender).categories
    
    try:
        for url, category_name in zip(urls, categories):
            print(f"\n{'='*50}")
            print(f"Parsing category: {category_name}")
            print(f"URL: {url}")
            print(f"{'='*50}")
            
            try:
                # Получаем список ссылок на товары (с лимитом)
                links = driver.get_elements(url=url)
                
                if not links:
                    print(f"⚠️ Не найдено товаров в категории {category_name}")
                    continue
                
                print(f"✓ Найдено товаров: {len(links)}")
                
                # Парсим товары
                parsed_data = driver.parse_elements(links, category_name, gender)

                if parsed_data:
                    save_to_file(f"zara_{gender}_collection.json", parsed_data)
                    save_to_mongo(mongo, f"zara_{gender}_collection", parsed_data)
                    print(f"✓ Сохранено {len(parsed_data)} товаров")
                else:
                    print(f"⚠️ Не удалось спарсить товары из категории {category_name}")
                
                print("-" * 50)
                
            except Exception as exc:
                print(f"Error in parsing category: {category_name}\n", str(exc))
                print()
                continue
                
    finally:
        # Закрываем браузер в любом случае
        driver.close()
        print("\n✓ Парсинг завершен, браузер закрыт")


if __name__ == "__main__":
    args = arguments_parser.parse_args()

    config = ZaraConfig.from_yaml("config/config_zara.yaml")
    run_scrapper(config=config, gender=args.gender)

