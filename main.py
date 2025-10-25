import argparse
import json

from scripts.interfaces import WebDriverInterface, MongoInterface, PlaywrightInterface
from config.config_models import Config


arguments_parser = argparse.ArgumentParser(description="FarFetch argument parser")
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


def run_scrapper(config: Config, gender: str):
    print(f"Chosen catalog: {gender}")

    driver = PlaywrightInterface(page_loading_time=config.page_loading_time)
    # Используем 'mongo' как имя хоста в Docker, 'localhost' для локального запуска
    import os
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    mongo = MongoInterface(f"mongodb://admin123:password123@{mongo_host}:27017/")
    
    try:
        mongo.create_collection(f"{gender}_collection")
    except:
        pass

    urls = getattr(config, gender).urls
    categories = getattr(config, gender).categories
    
    try:
        for url, category in zip(urls, categories):
            print(f"\n{'='*50}")
            print(f"Parsing category: {category}")
            print(f"{'='*50}")
            try:
                pages = driver.get_number_of_pages(url=url)
            except Exception as exc:
                print(f"Error in parsing pages: {url}\n", str(exc))
                print()
                continue
            print(f"Всего страниц: {pages}")
            
            # Счетчик пустых страниц подряд
            consecutive_empty_pages = 0
            max_consecutive_empty = 5  # Остановиться после 5 пустых страниц подряд
            
            for page in range(1, pages + 1):
                url_page = f"{url}?page={page}"
                print(f"\n[{page}/{pages}] Parsing: {url_page}")

                links = driver.get_elements(url=url_page)
                
                # Проверка на пустую страницу
                if not links:
                    consecutive_empty_pages += 1
                    print(f"⚠️ Пустая страница ({consecutive_empty_pages}/{max_consecutive_empty})")
                    if consecutive_empty_pages >= max_consecutive_empty:
                        print(f"❌ Остановка парсинга категории {category}: {max_consecutive_empty} пустых страниц подряд")
                        break
                    continue
                else:
                    consecutive_empty_pages = 0  # Сброс счетчика при успешной загрузке
                
                parsed_data = driver.parse_elements(links, category, gender)

                save_to_file(f"{gender}_collection.json", parsed_data)
                save_to_mongo(mongo, f"{gender}_collection", parsed_data)
                print(f"✓ Сохранено {len(parsed_data)} товаров")
                print("-" * 50)
    finally:
        # Закрываем браузер в любом случае
        driver.close()
        print("\n✓ Парсинг завершен, браузер закрыт")


if __name__ == "__main__":
    args = arguments_parser.parse_args()

    config = Config.from_yaml("config/config.yaml")
    run_scrapper(config=config, gender=args.gender)
