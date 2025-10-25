import tempfile
import time

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from playwright.sync_api import sync_playwright
from pymongo.errors import DuplicateKeyError
from selenium.webdriver.common.by import By
from pymongo import MongoClient
from selenium import webdriver


class MongoInterface:
    def __init__(self, connection_uri: str, database: str = "farfetch_db"):
        self._client = MongoClient(connection_uri)
        self._database = self._client[database]

    def create_collection(self, collection_name: str):
        if collection_name in self._database.list_collection_names():
            raise Exception(f"Коллекция {collection_name} уже существует")    
        
        collection = self._database[collection_name]
        collection.create_index("url", unique=True)

    def insert_data(self, collection_name, data_sample):
        collection = self._database[collection_name]
        try:
            collection.insert_one(data_sample)
        except DuplicateKeyError as exc:
            print(f"URL: {data_sample["url"]} уже добавлен в базу")


class WebDriverInterface:
    def __init__(self, page_loading_time: int = 3):
        chrome_options = Options()
        chrome_options.binary_location = "/usr/bin/chromium-browser"
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        temp_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")

        self.driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)
        self._page_loading_time = page_loading_time

    def get_number_of_pages(self, url: str):
        self.driver.get(url)
        time.sleep(self._page_loading_time)
        element = self.driver.find_element(By.XPATH, '//*[@data-component="PaginationLabel"]')
        if element:
            return int(element.text.split(" из ")[1])
        return 0

    def get_elements(self, url: str):
        self.driver.get(url=url)
        time.sleep(self._page_loading_time)
        catalog = self.driver.find_element(By.ID, 'catalog-grid')
        elements = catalog.find_elements(By.XPATH, './/*[@data-component="ProductCardLink"]')
        if elements:
            return [x.get_attribute("href") for x in elements]
        return []

    def parse_elements(self, links, category, gender):
        data = []
        for link in links[:10]:
            self.driver.get(link)
            time.sleep(self._page_loading_time)
            try:
                page = self.driver.find_element(By.ID, 'content')
            except Exception as exc:
                print(f"Content parsing error in {link}")
                continue

            images = [x.get_attribute("src") for x in page.find_elements(By.XPATH, './/*[@data-component="Img"]')]
            try:
                price = page.find_element(By.XPATH, './/*[@data-component="PriceLarge"]').text
            except Exception as exc:
                print(f"Price parsing error in {link}")
                price = None
            
            try:
                short_description = page.find_element(By.XPATH, './/*[@data-component="Body"][@data-testid="product-short-description"]').text
            except Exception as exc:
                print(f"Short description parsing error in {link}")
                short_description = None

            data.append({
                "url": link,
                "images": images,
                "price": price,
                "short_description": short_description,
                "category": category,
                "gender": gender
            })

        return data


import time
from playwright.sync_api import sync_playwright

class PlaywrightInterface:
    def __init__(self, page_loading_time: int = 3, headless: bool = True):
        self.page_loading_time = page_loading_time
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        
        # Имитируем реальный браузер
        self.page = self.browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))

        # Таймауты
        self.page.set_default_timeout(30000)             # 30 секунд для локаторов
        self.page.set_default_navigation_timeout(60000) # 60 секунд для goto

    def safe_goto(self, url):
        """Переход на страницу с retry и обработкой баннеров"""
        for attempt in range(5):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                self.page.wait_for_selector(
                    '[data-component="PriceCallout"], [data-testid="productCard"], [data-component="PaginationLabel"]',
                    timeout=40000
                )

                # Закрываем pop-up / куки
                for btn_text in ["Accept All", "Continue"]:
                    try:
                        self.page.locator(f'button:has-text("{btn_text}")').click(timeout=2000)
                    except:
                        pass

                return True
            except Exception as e:
                print(f"⚠️ Попытка {attempt+1}/3 не удалась ({url}): {e}")
                time.sleep(2)
        print(f"❌ Не удалось загрузить {url}")
        return False

    def get_number_of_pages(self, url: str):
        if not self.safe_goto(url):
            return 0
        try:
            element = self.page.locator('[data-component="PaginationLabel"]').first
            text = element.text_content()
            if text:
                return int(text.split(" из ")[1])
        except Exception:
            return 0
        return 0

    def get_elements(self, url: str):
        if not self.safe_goto(url):
            return []
        try:
            catalog_links = self.page.locator('#catalog-grid [data-component="ProductCardLink"]')
            hrefs = catalog_links.evaluate_all("els => els.map(e => e.href)")
            return hrefs or []
        except Exception as exc:
            print(f"⚠️ Ошибка при получении ссылок {url}: {exc}")
            return []

    def parse_elements(self, links, category, gender):
        data = []
        for link in links:
            if not self.safe_goto(link):
                continue
            try:
                # Получаем изображения
                images = self.page.locator('[data-component="Img"]').evaluate_all(
                    "els => els.map(e => e.src)"
                )

                # Поиск цены в разных селекторах
                price_selector = (
                    '[data-component="PriceLarge"], '
                    '[data-component="PriceFinal"], '
                    '[data-component="PriceOriginal"], '
                    '[data-component="PriceWithSchema"], '
                    '[itemprop="price"]'
                )
                try:
                    self.page.wait_for_selector(price_selector, timeout=30000)
                    price = self.page.locator(price_selector).first.text_content()
                except:
                    print(f"⚠️ Цена не найдена на {link}")
                    price = None

                # Короткое описание
                try:
                    short_description = self.page.locator(
                        '[data-component="Body"][data-testid="product-short-description"]'
                    ).first.text_content()
                except:
                    short_description = None

                data.append({
                    "url": link,
                    "images": images,
                    "price": price,
                    "short_description": short_description,
                    "category": category,
                    "gender": gender
                })
            except Exception as exc:
                print(f"⚠️ Ошибка при парсинге {link}: {exc}")
                continue

        return data

    def close(self):
        """Закрытие браузера и Playwright"""
        self.browser.close()
        self.playwright.stop()
