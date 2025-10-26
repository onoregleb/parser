"""
Парсер Zara через API (БЕЗ Selenium/Playwright!)
Использует прямые HTTP запросы к внутреннему API Zara.

ПРЕИМУЩЕСТВА:
- В 10-100 раз быстрее чем Selenium
- Не требует браузера
- Надежнее (нет проблем с JavaScript)
- Можно парсить тысячи товаров
"""

import requests
import json
import time
import random
import sys
import os
from typing import List, Dict, Optional


class ZaraAPIParser:
    """Парсер Zara через API"""
    
    def __init__(self, config_path: str = "config.json", request_delay: tuple = None, items_limit: int = None):
        """
        Args:
            config_path: путь к файлу конфигурации
            request_delay: задержка между запросами (min, max) в секундах (переопределяет конфиг)
            items_limit: сколько товаров парсить (переопределяет конфиг)
        """
        # Загружаем конфигурацию
        self.config = self.load_config(config_path)
        
        # Устанавливаем параметры парсинга
        if request_delay:
            self.request_delay = request_delay
        else:
            self.request_delay = (
                self.config["parsing"]["request_delay"]["min"],
                self.config["parsing"]["request_delay"]["max"]
            )
            
        if items_limit is not None:
            self.items_limit = items_limit
        else:
            self.items_limit = self.config["parsing"]["items_limit"]
            
        # Настройки сайта
        self.country = self.config["site"]["country"]
        self.lang = self.config["site"]["lang"]
        self.currency = self.config["site"]["currency"]
        self.base_url = self.config["site"]["base_url"]
        
        self.session = requests.Session()
        
        # User-Agent для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://www.zara.com/{self.country}/',
        })

    def load_config(self, config_path: str) -> Dict:
        """Загружает конфигурацию из файла или переменных окружения"""
        # Пытаемся загрузить из файла
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # Дефолтная конфигурация
            config = {
                "site": {
                    "country": "us",
                    "lang": "en", 
                    "currency": "USD",
                    "base_url": "https://www.zara.com/us/en"
                },
                "parsing": {
                    "items_limit": 50,
                    "request_delay": {"min": 1.0, "max": 2.0},
                    "max_retries": 3
                }
            }
        
        # Переопределяем из переменных окружения
        if os.getenv('ZARA_COUNTRY'):
            config["site"]["country"] = os.getenv('ZARA_COUNTRY')
        if os.getenv('ZARA_LANG'):
            config["site"]["lang"] = os.getenv('ZARA_LANG')
        if os.getenv('ZARA_CURRENCY'):
            config["site"]["currency"] = os.getenv('ZARA_CURRENCY')
        if os.getenv('ZARA_ITEMS_LIMIT'):
            config["parsing"]["items_limit"] = int(os.getenv('ZARA_ITEMS_LIMIT'))
        if os.getenv('ZARA_REQUEST_DELAY_MIN'):
            config["parsing"]["request_delay"]["min"] = float(os.getenv('ZARA_REQUEST_DELAY_MIN'))
        if os.getenv('ZARA_REQUEST_DELAY_MAX'):
            config["parsing"]["request_delay"]["max"] = float(os.getenv('ZARA_REQUEST_DELAY_MAX'))
            
        # Обновляем base_url
        config["site"]["base_url"] = f"https://www.zara.com/{config['site']['country']}/{config['site']['lang']}"
        
        return config
        
    def _delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(self.request_delay[0], self.request_delay[1])
        time.sleep(delay)

    def _retry_request(self, func, max_retries: int = 3, *args, **kwargs):
        """Повторная попытка выполнения запроса при ошибке"""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[WARNING] Попытка {attempt + 1} провалилась, повторяю через 5 сек... ({str(e)})")
                    time.sleep(5)
                else:
                    print(f"[ERROR] Все {max_retries} попытки провалились")
                    raise e
    
    def get_category_products(self, country: str, lang: str, category_id: str) -> List[Dict]:
        """
        Получает список товаров из категории через API

        Args:
            country: код страны (например, 'kz', 'us', 'ru')
            lang: код языка (например, 'en', 'ru')
            category_id: ID категории (берется из URL)

        Returns:
            Список товаров с базовой информацией
        """
        print(f"\nПоиск товаров из категории {category_id}...")

        # Сначала получаем информацию о категории для получения categoryId
        categories_url = f"https://www.zara.com/{country}/{lang}/categories"
        
        def _get_category_info():
            params = {
                'categorySeoId': category_id,
                'ajax': 'true'
            }
            response = self.session.get(categories_url, params=params)
            response.raise_for_status()
            return response.json()

        def _get_products(real_category_id):
            # API эндпоинт для получения товаров категории
            api_url = f"https://www.zara.com/{country}/{lang}/category/{real_category_id}/products"
            params = {'ajax': 'true'}
            response = self.session.get(api_url, params=params)
            response.raise_for_status()
            return response.json()

        try:
            # Получаем информацию о категории
            category_info = self._retry_request(_get_category_info)
            
            # Извлекаем реальный categoryId
            real_category_id = None
            if 'categories' in category_info and category_info['categories']:
                real_category_id = category_info['categories'][0].get('id')
            
            if not real_category_id:
                print(f"[ERROR] Не удалось получить реальный ID категории для {category_id}")
                return []
                
            print(f"[INFO] Реальный ID категории: {real_category_id}")
            
            # Получаем товары
            data = self._retry_request(lambda: _get_products(real_category_id))

            # Извлекаем товары из ответа
            all_products = []

            if 'productGroups' in data:
                for group in data['productGroups']:
                    # Разные группы могут иметь разную структуру
                    elements = group.get('elements', [])
                    products = group.get('products', [])

                    # Проверяем оба поля
                    items = elements if elements else products

                    for item in items:
                        # Извлекаем commercialComponents (это и есть товары)
                        commercial_components = item.get('commercialComponents', [])

                        for product in commercial_components:
                            all_products.append(product)

            print(f"[OK] Найдено {len(all_products)} товаров")

            # Ограничиваем количество если нужно
            if self.items_limit:
                all_products = all_products[:self.items_limit]
                print(f"[INFO] Ограничено до {len(all_products)} товаров")

            return all_products

        except Exception as e:
            print(f"[ERROR] Ошибка получения товаров: {e}")
            return []
    
    def get_product_details(self, country: str, lang: str, product_id: int) -> Optional[Dict]:
        """
        Получает детальную информацию о товаре через API
        
        Args:
            country: код страны
            lang: код языка
            product_id: ID товара
        
        Returns:
            Полная информация о товаре
        """
        api_url = f"https://www.zara.com/{country}/{lang}/products/{product_id}.json"
        
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            return response.json()
        except:
            # Если API для детального товара недоступен, возвращаем None
            return None
    
    def build_product_url(self, country: str, lang: str, seo_keyword: str, seo_product_id: str, product_id: int) -> str:
        """
        Формирует URL товара на основе SEO данных
        
        Args:
            country: код страны
            lang: код языка
            seo_keyword: SEO keyword из API
            seo_product_id: SEO product ID из API
            product_id: ID товара (discernProductId)
        
        Returns:
            Полный URL товара
        """
        # Формат URL Zara: /country/lang/seo-keyword-pSEO_PRODUCT_ID.html?v1=PRODUCT_ID
        return f"https://www.zara.com/{country}/{lang}/{seo_keyword}-p{seo_product_id}.html?v1={product_id}"
    
    def parse_product(self, product_data: Dict, country: str, lang: str) -> Dict:
        """
        Парсит данные товара из API ответа
        
        Args:
            product_data: данные товара из API
            country: код страны
            lang: код языка
        
        Returns:
            Словарь с информацией о товаре
        """
        try:
            # Базовая информация
            product_id = product_data.get('id')
            name = product_data.get('name', '')
            price = product_data.get('price', 0) / 100  # Цена в копейках, делим на 100
            reference = product_data.get('reference', '')
            section_name = product_data.get('sectionName', '')
            family_name = product_data.get('familyName', '')
            
            # SEO данные для формирования URL
            seo = product_data.get('seo', {})
            seo_keyword = seo.get('keyword', '')
            seo_product_id = seo.get('seoProductId', '')
            discern_product_id = seo.get('discernProductId', product_id)
            
            # Формируем URL товара
            product_url = self.build_product_url(
                country, lang, seo_keyword, seo_product_id, discern_product_id
            )
            
            # Детали товара
            detail = product_data.get('detail', {})
            display_reference = detail.get('displayReference', reference)
            colors = detail.get('colors', [])
            
            # Информация о первом цвете (обычно основной)
            color_info = {}
            images = []
            
            if colors:
                first_color = colors[0]
                color_info = {
                    'name': first_color.get('name', ''),
                    'reference': first_color.get('reference', ''),
                    'price': first_color.get('price', price) / 100,
                    'availability': first_color.get('availability', 'unknown')
                }
                
                # Изображения
                xmedia = first_color.get('xmedia', [])
                for media in xmedia:
                    if media.get('type') == 'image':
                        img_url = media.get('url', '')
                        # Заменяем {width} на конкретное значение
                        img_url = img_url.replace('{width}', '1920')
                        images.append(img_url)
            
            # Собираем все данные
            parsed_product = {
                'url': product_url,
                'id': product_id,
                'name': name,
                'reference': reference,
                'display_reference': display_reference,
                'price': price,
                'currency': self.currency,
                'section': section_name,
                'family': family_name,
                'color': color_info.get('name', ''),
                'color_reference': color_info.get('reference', ''),
                'availability': color_info.get('availability', 'unknown'),
                'images': images,
                'description': product_data.get('description', ''),
            }
            
            return parsed_product
            
        except Exception as e:
            print(f"[WARNING] Ошибка парсинга товара: {e}")
            return {}
    
    def parse_category(self, category_url: str, category_name: str = "category") -> List[Dict]:
        """
        Парсит всю категорию
        
        Args:
            category_url: URL категории (например, https://www.zara.com/kz/en/man-jackets-l640.html?v1=2536906)
            category_name: название категории для идентификации
        
        Returns:
            Список спарсенных товаров
        """
        print(f"\n{'='*70}")
        print(f"[PARSING] ПАРСИНГ КАТЕГОРИИ: {category_name}")
        print(f"[URL] {category_url}")
        print(f"{'='*70}\n")
        
        # Извлекаем параметры из URL
        # Формат: https://www.zara.com/{country}/{lang}/man-jackets-l{category_id}.html?v1={version}
        try:
            parts = category_url.replace('https://www.zara.com/', '').split('/')
            country = parts[0]  # kz
            lang = parts[1]     # en
            
            # Извлекаем category_id из части URL (например, "man-jackets-l640.html" -> "640")
            category_part = parts[2]  # man-jackets-l640.html
            category_id = category_part.split('-l')[1].split('.')[0]  # 640
            
            # Можно также получить из параметра v1
            if '?v1=' in category_url:
                category_id = category_url.split('?v1=')[1].split('&')[0]
            
            print(f"[INFO] Страна: {country}, Язык: {lang}, ID категории: {category_id}")

        except Exception as e:
            print(f"[ERROR] Не удалось распарсить URL: {e}")
            return []

        # Получаем список товаров
        products = self.get_category_products(country, lang, category_id)

        if not products:
            print("\n[WARNING] Товары не найдены")
            return []

        # Парсим каждый товар
        print(f"\n[INFO] Парсинг {len(products)} товаров...")
        print("="*70)
        
        parsed_products = []
        
        for i, product_data in enumerate(products, 1):
            print(f"\n[{i}/{len(products)}] Парсинг товара...")
            
            # Добавляем задержку между запросами (кроме первого)
            if i > 1:
                self._delay()
            
            parsed = self.parse_product(product_data, country, lang)
            
            if parsed:
                parsed['category'] = category_name
                parsed_products.append(parsed)
                print(f"[OK] {parsed['name']}")
                print(f"   Цена: {parsed['price']} {parsed['currency']}")
                print(f"   Цвет: {parsed['color']}")
                print(f"   URL: {parsed['url'][:80]}...")
            else:
                print(f"[WARNING] Ошибка парсинга")

        print(f"\n{'='*70}")
        print(f"[SUCCESS] ЗАВЕРШЕНО: Спарсено {len(parsed_products)} товаров")
        print(f"{'='*70}")
        
        return parsed_products


def save_to_json(data: List[Dict], filename: str = "zara_products_api.json"):
    """Сохранение данных в JSON"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVE] Данные сохранены в файл: {filename}")
    print(f"[INFO] Всего товаров: {len(data)}")


def save_progress(current_index: int, categories: List[Dict], all_products: List[Dict]):
    """Сохранение прогресса парсинга"""
    progress_data = {
        "current_index": current_index,
        "categories": categories,
        "products": all_products,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open("zara_parsing_progress.json", "w", encoding="utf-8") as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)

    print(f"[SAVE] Прогресс сохранен: категория {current_index + 1}/{len(categories)}")


def load_progress() -> tuple:
    """Загрузка прогресса парсинга"""
    try:
        with open("zara_parsing_progress.json", "r", encoding="utf-8") as f:
            progress_data = json.load(f)

        current_index = progress_data.get("current_index", 0)
        categories = progress_data.get("categories", [])
        products = progress_data.get("products", [])

        print(f"[LOAD] Прогресс загружен: категория {current_index + 1}, товаров: {len(products)}")
        return current_index, categories, products

    except FileNotFoundError:
        print("[LOAD] Файл прогресса не найден, начинаем с начала")
        return 0, [], []
    except Exception as e:
        print(f"[WARNING] Ошибка загрузки прогресса: {e}")
        return 0, [], []


# ==============================================================================
# MAIN - Пример использования
# ==============================================================================

def get_zara_categories(config: Dict, mode: str = "full") -> List[Dict]:
    """
    Возвращает список категорий для парсинга в зависимости от режима
    
    Args:
        config: конфигурация с категориями
        mode: режим парсинга (test, woman, man, full)
    
    Returns:
        Список категорий для парсинга
    """
    categories = []
    
    if mode == "test":
        # Для тестирования берем по 2 категории каждой группы
        if "woman" in config.get("categories", {}):
            categories.extend(config["categories"]["woman"][:2])
        if "man" in config.get("categories", {}):
            categories.extend(config["categories"]["man"][:2])
    elif mode == "woman":
        categories = config.get("categories", {}).get("woman", [])
    elif mode == "man":
        categories = config.get("categories", {}).get("man", [])
    elif mode == "full":
        # Все категории
        if "woman" in config.get("categories", {}):
            categories.extend(config["categories"]["woman"])
        if "man" in config.get("categories", {}):
            categories.extend(config["categories"]["man"])
    
    return categories


def parse_multiple_categories(categories: List[Dict], products_per_category: int = 10, resume: bool = False) -> List[Dict]:
    """
    Парсит несколько категорий

    Args:
        categories: список категорий для парсинга
        products_per_category: количество товаров на категорию
        resume: продолжить с сохраненного прогресса

    Returns:
        Список всех спарсенных товаров
    """
    print("="*80)
    print("ZARA MULTI-CATEGORY PARSER")
    print("="*80)

    # Создаем парсер с ограничением товаров
    parser = ZaraAPIParser(
        request_delay=(1.0, 2.0),   # Увеличенная задержка для множества категорий
        items_limit=products_per_category
    )

    all_products = []
    successful_categories = 0
    failed_categories = 0

    # Определяем начальный индекс
    start_index = 0
    if resume:
        start_index, categories, all_products = load_progress()
        successful_categories = len(set(p['category'] for p in all_products))

    for i in range(start_index, len(categories)):
        category = categories[i]
        print(f"\n{'='*80}")
        print(f"[CATEGORY] [{i+1}/{len(categories)}]: {category['name']}")
        print(f"{'='*80}")

        try:
            # Парсим категорию
            products = parser.parse_category(category['url'], category['name'])

            if products:
                all_products.extend(products)
                successful_categories += 1
                print(f"\n✅ УСПЕШНО: {len(products)} товаров из '{category['name']}'")

                # Сохраняем прогресс каждые 5 категорий или при успешном парсинге
                if (i + 1) % 5 == 0 or products:
                    save_progress(i + 1, categories, all_products)

                # Пауза между категориями
                if i < len(categories) - 1:
                    print("[PAUSE] Пауза перед следующей категорией...")
                    time.sleep(random.uniform(2, 4))
            else:
                failed_categories += 1
                print(f"\n[FAILED] Не удалось получить товары из '{category['name']}'")

        except Exception as e:
            failed_categories += 1
            print(f"\n[ERROR] {category['name']} - {str(e)}")

        # Сохраняем прогресс при каждой категории
        save_progress(i + 1, categories, all_products)

    # Финальная статистика
    print(f"\n{'='*80}")
    print("[STATS] ФИНАЛЬНАЯ СТАТИСТИКА")
    print(f"{'='*80}")
    print(f"[INFO] Обработано категорий: {len(categories)}")
    print(f"[SUCCESS] Успешных: {successful_categories}")
    print(f"[FAILED] Провалено: {failed_categories}")
    print(f"[INFO] Всего товаров собрано: {len(all_products)}")

    # Статистика по наличию
    if all_products:
        in_stock = sum(1 for p in all_products if p.get('availability') == 'in_stock')
        coming_soon = sum(1 for p in all_products if p.get('availability') == 'coming_soon')
        print(f"[INSTOCK] В наличии: {in_stock}")
        print(f"[COMING] Скоро в продаже: {coming_soon}")
        print(f"[OUTOFSTOCK] Нет в наличии: {len(all_products) - in_stock - coming_soon}")

    return all_products


if __name__ == "__main__":
    print("="*80)
    print("ZARA API PARSER - Английский сайт с долларами")
    print("="*80)
    
    # Определяем режим работы
    mode = os.getenv('ZARA_MODE', 'full')
    resume = '--resume' in sys.argv or '-r' in sys.argv
    
    # Создаем парсер с загрузкой конфигурации
    parser = ZaraAPIParser()
    
    # Получаем категории для парсинга
    categories = get_zara_categories(parser.config, mode)
    
    if not categories:
        print("[ERROR] Нет категорий для парсинга")
        print("[INFO] Проверьте файл config.json или переменную ZARA_MODE")
        sys.exit(1)
    
    print(f"[MODE] Режим: {mode.upper()}")
    print(f"[SITE] Сайт: {parser.base_url}")
    print(f"[CURRENCY] Валюта: {parser.currency}")
    print(f"[CATEGORIES] Найдено {len(categories)} категорий для парсинга")
    print(f"[ITEMS] Товаров на категорию: {parser.items_limit}")
    
    if mode == "test":
        print("\n" + "="*60)
        print("ТЕСТОВЫЙ РЕЖИМ")
        print("="*60)
        
        all_products = []
        for category in categories:
            print(f"\n[TEST] Тестируем категорию: {category['name']}")
            products = parser.parse_category(category['url'], category['name'])
            if products:
                all_products.extend(products)
                print(f"[OK] {len(products)} товаров получено")

        if all_products:
            filename = f"zara_test_{mode}.json"
            save_to_json(all_products, filename)
            print(f"\n[SUCCESS] Тест завершен! Получено {len(all_products)} товаров")
            print(f"[SAVE] Результаты сохранены в {filename}")
        else:
            print("\n[FAILED] Тест провален - товары не получены")
    else:
        print("\n" + "="*60)
        print("ПОЛНЫЙ ПАРСИНГ")
        print("="*60)
        
        if resume:
            print("[RESUME] Продолжаем с сохраненного прогресса")
            all_products = parse_multiple_categories(categories, products_per_category=parser.items_limit, resume=True)
        else:
            print("[NEW] Начинаем парсинг с начала")
            all_products = parse_multiple_categories(categories, products_per_category=parser.items_limit, resume=False)

    # Сохраняем результат (если не тестовый режим)
    if mode != "test" and all_products:
        # Определяем имя основного файла
        main_filename = f"zara_{mode}_{parser.currency.lower()}.json"
        save_to_json(all_products, main_filename)

        # Сохраняем по категориям в отдельные файлы
        data_dir = os.getenv('ZARA_DATA_DIR', './data')
        os.makedirs(data_dir, exist_ok=True)
        
        for category_name in set(p['category'] for p in all_products):
            category_products = [p for p in all_products if p['category'] == category_name]
            if category_products:
                filename = os.path.join(data_dir, f"zara_{category_name}_{parser.currency.lower()}.json")
                save_to_json(category_products, filename)

        print(f"""
[SAVE] Данные сохранены:
   [MAIN] Основной файл: {main_filename}
   [CATS] По категориям в папке: {data_dir}/
   [CURRENCY] Цены в валюте: {parser.currency}""")

        # Показываем примеры товаров
        print(f"\n[EXAMPLES] ПРИМЕРЫ ТОВАРОВ:")
        print("-"*70)
        for i, product in enumerate(all_products[:3], 1):
            print(f"\n{i}. {product['name']}")
            print(f"   [CAT] Категория: {product['category']}")
            print(f"   [PRICE] Цена: ${product['price']} {product['currency']}")
            print(f"   [COLOR] Цвет: {product['color']}")
            print(f"   [URL] URL: {product['url'][:60]}...")
    
    elif not all_products:
        print("\n[ERROR] Не удалось собрать товары ни из одной категории")
        print("[INFO] Возможные причины:")
        print("   - API Zara недоступен")
        print("   - Изменились URL категорий")
        print("   - Проблемы с интернет-соединением")
        print("   - Сайт блокирует запросы")
        print(f"   - Проверьте конфигурацию для {parser.base_url}")

