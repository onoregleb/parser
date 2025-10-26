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
from typing import List, Dict, Optional


class ZaraAPIParser:
    """Парсер Zara через API"""
    
    def __init__(self, request_delay: tuple = (0.5, 1.5), items_limit: int = 15):
        """
        Args:
            request_delay: задержка между запросами (min, max) в секундах
            items_limit: сколько товаров парсить (None = все)
        """
        self.request_delay = request_delay
        self.items_limit = items_limit
        self.session = requests.Session()
        
        # User-Agent для имитации браузера
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.zara.com/',
            'X-Requested-With': 'XMLHttpRequest',
        })
        
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
                'currency': 'KZT',  # Для Казахстана
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

def get_zara_categories():
    """Список из 30 реальных категорий Zara (получены с сайта)"""
    return [
        # ЖЕНСКИЕ КАТЕГОРИИ
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-kurtki-l1114.html", "name": "woman-jackets"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-verhnyaya-odezhda-l1184.html", "name": "woman-outerwear"},
        {"url": "https://www.zara.com/kz/ru/woman-outerwear-winter-l4445.html", "name": "woman-winter"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-blejzery-l1055.html", "name": "woman-blazers"},
        {"url": "https://www.zara.com/kz/ru/woman-cardigans-sweaters-l8322.html", "name": "woman-sweaters"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-platya-l1066.html", "name": "woman-dresses"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-topy-l1322.html", "name": "woman-tops"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-bodi-l1057.html", "name": "woman-bodysuits"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-dzhinsy-l1119.html", "name": "woman-jeans"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-bryuki-l1335.html", "name": "woman-trousers"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-futbolki-l1362.html", "name": "woman-t-shirts"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-rubashki-l1217.html", "name": "woman-shirts"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-trikotazh-l1152.html", "name": "woman-knitwear"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-kozha-l1174.html", "name": "woman-leather"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-tolstovki-l1320.html", "name": "woman-sweatshirts"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-yubki-l1299.html", "name": "woman-skirts-shorts"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-obuv-l1251.html", "name": "woman-shoes"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-sumki-l1024.html", "name": "woman-bags"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-aksessuary-l1003.html", "name": "woman-accessories"},
        {"url": "https://www.zara.com/kz/ru/woman-lingerie-l4021.html", "name": "woman-lingerie"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-kosmetika-aromaty-l1415.html", "name": "woman-perfumes"},
        {"url": "https://www.zara.com/kz/ru/zhenshchiny-specialnye-ceny-l1314.html", "name": "woman-sale"},

        # МУЖСКИЕ КАТЕГОРИИ
        {"url": "https://www.zara.com/kz/ru/muzhchiny-kurtki-l640.html", "name": "man-jackets"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-verhnyaya-odezhda-zhilety-l730.html", "name": "man-outerwear"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-verhnyaya-odezhda-l715.html", "name": "man-coats"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-kozha-l704.html", "name": "man-leather"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-bryuki-l838.html", "name": "man-trousers"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-dzhinsy-l659.html", "name": "man-jeans"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-futbolki-l855.html", "name": "man-t-shirts"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-rubashki-l737.html", "name": "man-shirts"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-tolstovki-l821.html", "name": "man-sweatshirts"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-trikotazh-l681.html", "name": "man-knitwear"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-sportivnaya-odezhda-l679.html", "name": "man-sportswear"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-kostyumy-l808.html", "name": "man-suits"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-polo-l733.html", "name": "man-polo"},
        {"url": "https://www.zara.com/kz/ru/man-overshirts-l3174.html", "name": "man-overshirts"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-blejzery-l608.html", "name": "man-blazers"},
        {"url": "https://www.zara.com/kz/ru/man-sneakers-l7460.html", "name": "man-sneakers"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-obuv-l769.html", "name": "man-shoes"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-sumki-l563.html", "name": "man-bags"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-aksessuary-l537.html", "name": "man-accessories"},
        {"url": "https://www.zara.com/kz/ru/muzhchiny-specialnye-ceny-l806.html", "name": "man-sale"},

        # ДЕТСКИЕ КАТЕГОРИИ
        {"url": "https://www.zara.com/kz/ru/kids-preteen-l16492.html", "name": "kids-preteen"},
        {"url": "https://www.zara.com/kz/ru/kids-halloween-l2316.html", "name": "kids-halloween"},
        {"url": "https://www.zara.com/kz/ru/kids-accessories-perfumes-l5951.html", "name": "kids-accessories"},
        {"url": "https://www.zara.com/kz/ru/zara-50-anniversary-collection-l15655.html", "name": "50th-anniversary"}
    ]


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
    print("ZARA MULTI-CATEGORY PARSER - Парсер 45 категорий")
    print("="*80)

    # Создаем парсер с ограничением товаров
    parser = ZaraAPIParser(
        request_delay=(1.0, 2.0),   # Увеличенная задержка для множества категорий
        items_limit=products_per_category  # 10 товаров на категорию
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
    # Проверяем аргументы командной строки
    resume = '--resume' in sys.argv or '-r' in sys.argv
    test_mode = '--test' in sys.argv or '-t' in sys.argv

    # Получаем список всех категорий
    categories = get_zara_categories()

    if test_mode:
        print("ТЕСТОВЫЙ РЕЖИМ: Парсинг первых 3 категорий")
        print("="*60)
        test_categories = categories[:3]  # Берем только первые 3 категории

        # Тестовый парсер
        test_parser = ZaraAPIParser(request_delay=(0.5, 1.0), items_limit=3)
        all_products = []

        for category in test_categories:
            print(f"\n[TEST] Тестируем категорию: {category['name']}")
            products = test_parser.parse_category(category['url'], category['name'])
            if products:
                all_products.extend(products)
                print(f"[OK] {len(products)} товаров получено")

        if all_products:
            save_to_json(all_products, "zara_test.json")
            print(f"\n[SUCCESS] Тест завершен! Получено {len(all_products)} товаров")
            print("[SAVE] Результаты сохранены в zara_test.json")
        else:
            print("\n[FAILED] Тест провален - товары не получены")

    elif resume:
        print("[INFO] Найдено 45 категорий для парсинга")
        print("[RESUME] Режим возобновления: продолжаем с сохраненного прогресса")
        # Парсим все категории по 10 товаров каждая с возобновлением
        all_products = parse_multiple_categories(categories, products_per_category=10, resume=True)
    else:
        print("[INFO] Найдено 45 категорий для парсинга")
        print("[NEW] Режим с нуля: начинаем парсинг с первой категории")
        # Парсим все категории по 10 товаров каждая с начала
        all_products = parse_multiple_categories(categories, products_per_category=10, resume=False)

    # Сохраняем результат
    if all_products:
        # Сохраняем все товары в один файл
        save_to_json(all_products, "zara_all_categories.json")

        # Сохраняем по категориям в отдельные файлы
        for category_name in set(p['category'] for p in all_products):
            category_products = [p for p in all_products if p['category'] == category_name]
            if category_products:
                filename = f"zara_{category_name}.json"
                save_to_json(category_products, filename)

        print("""
[SAVE] Данные сохранены:
   [FILE] Общий файл: zara_all_categories.json
   [FOLDER] По категориям: zara_[название_категории].json""")

        # Показываем примеры товаров
        print(f"\n[EXAMPLES] ПРИМЕРЫ ТОВАРОВ:")
        print("-"*70)
        for i, product in enumerate(all_products[:3], 1):
            print(f"\n{i}. {product['name']}")
            print(f"   [CAT] Категория: {product['category']}")
            print(f"   [PRICE] Цена: {product['price']} {product['currency']}")
            print(f"   [COLOR] Цвет: {product['color']}")
            print(f"   [URL] URL: {product['url'][:60]}...")
    else:
        print("\n[ERROR] Не удалось собрать товары ни из одной категории")
        print("[INFO] Возможные причины:")
        print("   - API Zara недоступен")
        print("   - Изменились URL категорий")
        print("   - Проблемы с интернет-соединением")
        print("   - Сайт блокирует запросы")

