import tempfile
import time
import random
from pathlib import Path

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from playwright.sync_api import sync_playwright
from pymongo.errors import DuplicateKeyError
from selenium.webdriver.common.by import By
from pymongo import MongoClient
from selenium import webdriver


class MongoInterface:
    def __init__(self, connection_uri: str, database: str = "farfetch_db"):
        """
        Инициализация MongoDB клиента
        
        Args:
            connection_uri: URI подключения к MongoDB
            database: Имя базы данных (по умолчанию 'farfetch_db')
        """
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


class PlaywrightInterface:
    def __init__(self, page_loading_time: int = 3, headless: bool = True, request_delay: tuple = (24, 60)):
        """
        Инициализация Playwright интерфейса
        
        Args:
            page_loading_time: время ожидания загрузки страницы
            headless: запускать браузер в headless режиме
            request_delay: диапазон задержки между запросами в секундах (min, max)
        """
        self.page_loading_time = page_loading_time
        self.request_delay = request_delay
        self.playwright = sync_playwright().start()
        
        # Инициализируем браузер
        self._init_browser(headless)

    def _init_browser(self, headless: bool = True):
        """Инициализация браузера"""
        self.browser = self.playwright.chromium.launch(headless=headless)
        
        # Имитируем реальный браузер
        self.page = self.browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))

        # Таймауты
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(60000)

    def safe_goto(self, url, add_delay=True):
        """Переход на страницу с retry и обработкой баннеров"""
        # Случайная задержка перед запросом
        if add_delay:
            delay = random.uniform(self.request_delay[0], self.request_delay[1])
            print(f"⏳ Задержка {delay:.1f}s перед запросом...")
            time.sleep(delay)
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Проверяем статус ответа
                if response and response.status == 429:
                    print(f"🚫 Rate limit (429)! Ждем 60 секунд...")
                    time.sleep(60)
                    continue
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
                    timeout=15000
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
                error_name = type(e).__name__
                error_msg = str(e)
                print(f"⚠️ Попытка {attempt+1}/{max_retries} не удалась:")
                print(f"   Тип ошибки: {error_name}")
                print(f"   Сообщение: {error_msg[:200]}")
                
                if attempt < max_retries - 1:
                    delay = 5 * (attempt + 1)
                    print(f"⏱️ Ждем {delay} секунд перед следующей попыткой...")
                    time.sleep(delay)
                else:
                    print(f"❌ Не удалось загрузить после {max_retries} попыток")
                    print(f"   Последняя ошибка: {error_name} - {error_msg[:100]}")
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
            # Задержка между товарами (используем request_delay)
            if i > 0:
                delay = random.uniform(self.request_delay[0], self.request_delay[1])
                print(f"⏳ Задержка {delay:.1f}s между товарами...")
                time.sleep(delay)
            
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


class ZaraPlaywrightInterface:
    def __init__(self, page_loading_time: int = 3, headless: bool = True, request_delay: tuple = (24, 60), items_limit: int = 200):
        """
        Инициализация Playwright интерфейса для Zara
        
        Args:
            page_loading_time: время ожидания загрузки страницы
            headless: запускать браузер в headless режиме
            request_delay: диапазон задержки между запросами в секундах (min, max)
            items_limit: лимит товаров для парсинга из каждой категории
        """
        self.page_loading_time = page_loading_time
        self.request_delay = request_delay
        self.items_limit = items_limit
        self.playwright = sync_playwright().start()
        
        # Инициализируем браузер
        self._init_browser(headless)

    def _init_browser(self, headless: bool = True):
        """Инициализация браузера"""
        self.browser = self.playwright.chromium.launch(headless=headless)
        
        # Имитируем реальный браузер
        self.page = self.browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ))

        # Таймауты
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(60000)

    def safe_goto(self, url, add_delay=True):
        """Переход на страницу с retry и обработкой баннеров"""
        # Случайная задержка перед запросом
        if add_delay:
            delay = random.uniform(self.request_delay[0], self.request_delay[1])
            print(f"⏳ Задержка {delay:.1f}s перед запросом...")
            time.sleep(delay)
        
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Проверяем статус ответа
                if response and response.status == 429:
                    print(f"🚫 Rate limit (429)! Ждем 60 секунд...")
                    time.sleep(60)
                    continue
                elif response and response.status >= 400:
                    print(f"⚠️ HTTP ошибка {response.status}")
                    return False
                
                # Ждем загрузки контента
                time.sleep(self.page_loading_time)

                # Закрываем cookie banner при первой загрузке
                if attempt == 0:
                    try:
                        # Пробуем найти и закрыть cookie banner
                        self.page.locator('button:has-text("Close")').first.click(timeout=3000)
                        print("✓ Cookie banner закрыт")
                    except:
                        pass

                return True
            except Exception as e:
                error_name = type(e).__name__
                error_msg = str(e)
                print(f"⚠️ Попытка {attempt+1}/{max_retries} не удалась:")
                print(f"   Тип ошибки: {error_name}")
                print(f"   Сообщение: {error_msg[:200]}")
                
                if attempt < max_retries - 1:
                    delay = 5 * (attempt + 1)
                    print(f"⏱️ Ждем {delay} секунд перед следующей попыткой...")
                    time.sleep(delay)
                else:
                    print(f"❌ Не удалось загрузить после {max_retries} попыток")
        return False

    def scroll_and_load_items(self, url: str):
        """
        Загружает страницу и скроллит для подгрузки товаров (infinite scroll)
        Возвращает список ссылок на товары
        """
        if not self.safe_goto(url):
            return []
        
        print(f"📜 Начинаем скроллинг для загрузки товаров...")
        
        all_links = []
        previous_count = 0
        no_new_items_count = 0
        max_no_new_items = 5  # Остановка после 5 попыток без новых товаров
        
        while len(all_links) < self.items_limit:
            # Скроллим вниз
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)  # Ждем подгрузки новых товаров
            
            try:
                # Ищем все ссылки на товары (используем heading level=3 как индикатор)
                product_headings = self.page.locator('heading[level="3"]').all()
                
                # Извлекаем уникальные ссылки
                current_links = set()
                for heading in product_headings:
                    try:
                        # Ищем ссылку внутри или рядом с heading
                        link_element = heading.locator('xpath=ancestor::*[self::a]').first
                        href = link_element.get_attribute('href')
                        if href and href.startswith('http'):
                            current_links.add(href)
                    except:
                        continue
                
                all_links = list(current_links)
                current_count = len(all_links)
                
                print(f"📦 Загружено товаров: {current_count}/{self.items_limit}")
                
                # Проверяем, появились ли новые товары
                if current_count == previous_count:
                    no_new_items_count += 1
                    if no_new_items_count >= max_no_new_items:
                        print(f"⚠️ Больше нет новых товаров. Остановка скроллинга.")
                        break
                else:
                    no_new_items_count = 0
                
                previous_count = current_count
                
                # Если достигли лимита, выходим
                if current_count >= self.items_limit:
                    print(f"✓ Достигнут лимит товаров: {self.items_limit}")
                    break
                    
            except Exception as e:
                print(f"⚠️ Ошибка при скроллинге: {e}")
                break
        
        # Возвращаем только первые items_limit товаров
        return all_links[:self.items_limit]

    def get_elements(self, url: str):
        """
        Получает список ссылок на товары с категории
        Использует скроллинг для infinite scroll
        """
        return self.scroll_and_load_items(url)

    def parse_elements(self, links, category, gender):
        """
        Парсит карточки товаров Zara
        Парсит только первый цвет (основной вариант товара)
        """
        data = []
        for i, link in enumerate(links):
            print(f"\n[{i+1}/{len(links)}] Парсинг: {link}")
            
            # Задержка между товарами
            if i > 0:
                delay = random.uniform(self.request_delay[0], self.request_delay[1])
                print(f"⏳ Задержка {delay:.1f}s между товарами...")
                time.sleep(delay)
            
            if not self.safe_goto(link, add_delay=False):
                continue
            
            try:
                # Название товара
                try:
                    title = self.page.locator('heading[level="1"]').first.text_content(timeout=10000)
                except:
                    print(f"⚠️ Не удалось получить название товара")
                    title = None
                
                # Цена
                try:
                    # Ищем элемент с ценой (generic элемент, содержащий "T " для тенге)
                    price_elements = self.page.locator('generic').all()
                    price = None
                    for elem in price_elements:
                        text = elem.text_content()
                        if text and text.startswith('T ') and '.' in text:
                            price = text
                            break
                    if not price:
                        print(f"⚠️ Цена не найдена")
                except:
                    print(f"⚠️ Ошибка при поиске цены")
                    price = None
                
                # Цвет и артикул
                try:
                    # Ищем параграф с кнопкой артикула
                    color_paragraph = self.page.locator('paragraph').filter(has=self.page.locator('button')).first
                    color_text = color_paragraph.text_content()
                    # Формат: "Brown | 2521/220/700"
                    if '|' in color_text:
                        color = color_text.split('|')[0].strip()
                        article = color_text.split('|')[1].strip()
                    else:
                        color = color_text
                        article = None
                except:
                    print(f"⚠️ Цвет/артикул не найден")
                    color = None
                    article = None
                
                # Описание товара
                try:
                    # Ищем paragraph с описанием (длинный текст)
                    paragraphs = self.page.locator('paragraph').all()
                    description = None
                    for p in paragraphs:
                        text = p.text_content()
                        if text and len(text) > 50:  # Описание обычно длинное
                            description = text
                            break
                except:
                    print(f"⚠️ Описание не найдено")
                    description = None
                
                # Состав
                try:
                    composition_elements = self.page.locator('generic').all()
                    composition = None
                    for elem in composition_elements:
                        text = elem.text_content()
                        if text and 'Composition:' in text:
                            composition = text.replace('Composition: ', '')
                            break
                except:
                    composition = None
                
                # Изображения - берем только основные (кнопки "Enlarge image")
                try:
                    images = []
                    enlarge_buttons = self.page.locator('button').filter(has_text='Enlarge image').all()
                    for btn in enlarge_buttons[:8]:  # Максимум 8 изображений
                        try:
                            img = btn.locator('img').first
                            img_src = img.get_attribute('src')
                            if img_src:
                                images.append(img_src)
                        except:
                            continue
                except:
                    print(f"⚠️ Ошибка при получении изображений")
                    images = []
                
                # Статус наличия
                try:
                    # Проверяем текст кнопок
                    buttons = self.page.locator('button').all()
                    availability = "Available"
                    for btn in buttons:
                        btn_text = btn.text_content()
                        if 'Notify me' in btn_text or 'Coming soon' in btn_text:
                            availability = "Coming soon"
                            break
                        elif 'Out of stock' in btn_text:
                            availability = "Out of stock"
                            break
                except:
                    availability = "Unknown"
                
                # Собираем данные
                item_data = {
                    "url": link,
                    "title": title,
                    "price": price,
                    "color": color,
                    "article": article,
                    "description": description,
                    "composition": composition,
                    "images": images,
                    "availability": availability,
                    "category": category,
                    "gender": gender
                }
                
                data.append(item_data)
                print(f"✓ Товар успешно спарсен: {title}")
                
            except Exception as exc:
                print(f"⚠️ Ошибка при парсинге {link}: {exc}")
                continue

        return data

    def close(self):
        """Закрытие браузера и Playwright"""
        self.browser.close()
        self.playwright.stop()