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
        })
        
    def _delay(self):
        """Случайная задержка между запросами"""
        delay = random.uniform(self.request_delay[0], self.request_delay[1])
        time.sleep(delay)
    
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
        print(f"\n🔍 Получение товаров из категории {category_id}...")
        
        # API эндпоинт для получения товаров категории
        api_url = f"https://www.zara.com/{country}/{lang}/category/{category_id}/products"
        
        try:
            response = self.session.get(api_url, params={'ajax': 'true'})
            response.raise_for_status()
            data = response.json()
            
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
            
            print(f"✅ Найдено {len(all_products)} товаров")
            
            # Ограничиваем количество если нужно
            if self.items_limit:
                all_products = all_products[:self.items_limit]
                print(f"📊 Ограничено до {len(all_products)} товаров")
            
            return all_products
            
        except Exception as e:
            print(f"❌ Ошибка получения товаров: {e}")
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
            print(f"⚠️ Ошибка парсинга товара: {e}")
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
        print(f"🛍️  ПАРСИНГ КАТЕГОРИИ: {category_name}")
        print(f"🔗 URL: {category_url}")
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
            
            print(f"📍 Страна: {country}, Язык: {lang}, ID категории: {category_id}")
            
        except Exception as e:
            print(f"❌ Не удалось распарсить URL: {e}")
            return []
        
        # Получаем список товаров
        products = self.get_category_products(country, lang, category_id)
        
        if not products:
            print("\n⚠️ Товары не найдены")
            return []
        
        # Парсим каждый товар
        print(f"\n📦 Парсинг {len(products)} товаров...")
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
                print(f"✅ {parsed['name']}")
                print(f"   💰 Цена: {parsed['price']} {parsed['currency']}")
                print(f"   🎨 Цвет: {parsed['color']}")
                print(f"   🔗 URL: {parsed['url'][:80]}...")
            else:
                print(f"⚠️ Ошибка парсинга")
        
        print(f"\n{'='*70}")
        print(f"✅ ЗАВЕРШЕНО: Спарсено {len(parsed_products)} товаров")
        print(f"{'='*70}")
        
        return parsed_products


def save_to_json(data: List[Dict], filename: str = "zara_products_api.json"):
    """Сохранение данных в JSON"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Данные сохранены в файл: {filename}")
    print(f"📊 Всего товаров: {len(data)}")


# ==============================================================================
# MAIN - Пример использования
# ==============================================================================

if __name__ == "__main__":
    # URL категории
    CATEGORY_URL = "https://www.zara.com/kz/en/man-jackets-l640.html?v1=2536906"
    CATEGORY_NAME = "man-jackets"
    
    print("="*70)
    print("🚀 ZARA API PARSER - Быстрый парсер через API")
    print("="*70)
    
    # Создаем парсер
    parser = ZaraAPIParser(
        request_delay=(0.5, 1.0),   # Маленькая задержка (API быстрый)
        items_limit=10              # Парсим 10 товаров для теста
    )
    
    # Парсим категорию
    products = parser.parse_category(CATEGORY_URL, CATEGORY_NAME)
    
    # Сохраняем результат
    if products:
        save_to_json(products, "zara_products_api.json")
        
        # Показываем статистику
        print(f"\n📈 СТАТИСТИКА:")
        print(f"   • Товаров спарсено: {len(products)}")
        print(f"   • Доступно: {sum(1 for p in products if p.get('availability') == 'in_stock')}")
        print(f"   • Скоро в продаже: {sum(1 for p in products if p.get('availability') == 'coming_soon')}")
        
        # Показываем первый товар
        print(f"\n📦 ПРИМЕР ТОВАРА:")
        print("-"*70)
        if products:
            first = products[0]
            print(f"Название: {first['name']}")
            print(f"Цена: {first['price']} {first['currency']}")
            print(f"Цвет: {first['color']}")
            print(f"Артикул: {first['display_reference']}")
            print(f"Наличие: {first['availability']}")
            print(f"URL: {first['url']}")
            print(f"Изображений: {len(first['images'])}")
    else:
        print("\n❌ Не удалось спарсить товары")
        print("💡 Проверьте:")
        print("   - Доступность API Zara")
        print("   - Правильность URL категории")
        print("   - Подключение к интернету")

