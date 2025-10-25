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
            print(f"URL: {data_sample['url']} уже добавлен в базу")


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

    def safe_goto(self, url, add_delay=True):
        """Переход на страницу с retry и обработкой баннеров"""
        # Случайная задержка перед запросом (против rate limiting)
        # Только для страниц каталога, не для карточек товаров
        if add_delay and "items.aspx" in url:
            import random
            delay = random.uniform(1, 2)  # 1-2 секунды для страниц каталога
            print(f"⏳ Задержка {delay:.1f}s перед запросом...")
            time.sleep(delay)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Проверяем статус ответа
                if response and response.status == 429:
                    print(f"🚫 Rate limit! Ждем 60 секунд...")
                    time.sleep(60)
                    return False
                elif response and response.status >= 400:
                    print(f"⚠️ HTTP ошибка {response.status}")
                    return False
                
                # Проверяем, что не произошел редирект на главную или другую страницу
                current_url = self.page.url
                if "items.aspx" not in current_url and "page=" in url:
                    print(f"⚠️ Редирект обнаружен: {current_url}")
                    return False
                
                # Проверяем, что страница не пустая и содержит контент
                self.page.wait_for_selector(
                    '[data-component="PriceCallout"], [data-testid="productCard"], [data-component="PaginationLabel"]',
                    timeout=15000  # Уменьшен таймаут для быстрого обнаружения пустых страниц
                )

                # Закрываем pop-up / куки только при первой загрузке
                if attempt == 0:
                    for btn_text in ["Accept All", "Continue", "Принять"]:
                        try:
                            self.page.locator(f'button:has-text("{btn_text}")').click(timeout=2000)
                        except:
                            pass

                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ Попытка {attempt+1}/{max_retries} не удалась: {type(e).__name__}")
                    time.sleep(3 * (attempt + 1))  # Увеличиваем задержку с каждой попыткой
                else:
                    print(f"❌ Не удалось загрузить: {type(e).__name__}")
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
            # Ждем появления каталога
            self.page.wait_for_selector('#catalog-grid', timeout=10000)
            catalog_links = self.page.locator('#catalog-grid [data-component="ProductCardLink"]')
            
            # Проверяем, есть ли вообще карточки товаров
            count = catalog_links.count()
            if count == 0:
                print(f"⚠️ Страница не содержит товаров")
                return []
            
            hrefs = catalog_links.evaluate_all("els => els.map(e => e.href)")
            print(f"✓ Найдено {len(hrefs)} товаров на странице")
            return hrefs or []
        except Exception as exc:
            print(f"⚠️ Ошибка при получении ссылок: {type(exc).__name__}")
            return []

    def parse_elements(self, links, category, gender):
        data = []
        for i, link in enumerate(links):
            # Небольшая задержка между товарами (0.5-1 сек)
            if i > 0:
                import random
                time.sleep(random.uniform(0.5, 1))
            
            if not self.safe_goto(link, add_delay=False):
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
