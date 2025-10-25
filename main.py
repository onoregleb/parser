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
    mongo = MongoInterface("mongodb://admin123:password123@localhost:27017/")
    try:
        mongo.create_collection(f"{gender}_collection")
    except:
        pass

    urls = getattr(config, gender).urls
    categories = getattr(config, gender).categories
    for url, category in zip(urls, categories):
        print(f"Parsing category: {category}")
        try:
            pages = driver.get_number_of_pages(url=url)
        except Exception as exc:
            print(f"Error in parsing pages: {url}\n", str(exc))
            print()
            continue
        print("pages: ", pages)
        for page in range(1, pages + 1):
            url_page = f"{url}?page={page}"
            print(f"Parsing: {url_page} out of {pages}")

            links = driver.get_elements(url=url_page)
            parsed_data = driver.parse_elements(links, category, gender)

            save_to_file(f"{gender}_collection.json", parsed_data)
            save_to_mongo(mongo, f"{gender}_collection", parsed_data)
            print("----------------------")


if __name__ == "__main__":
    args = arguments_parser.parse_args()

    config = Config.from_yaml("config/config.yaml")
    run_scrapper(config=config, gender=args.gender)
