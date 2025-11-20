import aiohttp
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List

class YandexParkAPI:
    """Класс для работы с API Яндекс Парка"""
    
    BASE_URL = "https://fleet-api.taxi.yandex.net"
    
    def __init__(self, park_id: str, api_key: str, client_id: str):
        self.park_id = park_id
        self.api_key = api_key
        self.client_id = client_id
        self.headers = {
            "X-Park-ID": park_id,
            "X-Client-ID": client_id,
            "X-API-Key": api_key,
            "Accept-Language": "ru"
        }
    
    async def check_driver_by_phone(self, phone: str) -> Optional[Dict]:
        """
        Проверяет, существует ли водитель с указанным номером телефона, используя прямой запрос.
        
        Args:
            phone: Номер телефона в формате +79XXXXXXXXX
        
        Returns:
            Dict с информацией о водителе или None, если не найден
        """
        try:
            normalized_phone = self._normalize_phone(phone)
            
            timeout = aiohttp.ClientTimeout(total=10)  # Таймаут 10 секунд
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{self.BASE_URL}/v1/parks/driver-profiles/list"
                
                # Получаем список водителей и фильтруем по телефону локально
                payload = {
                    "fields": {
                        "driver_profile": ["id", "phones", "first_name", "last_name", "middle_name", "work_status"],
                        "account": ["balance", "balance_limit"],
                        "car": ["brand", "model", "normalized_number", "amenities", "year"]
                    },
                    "query": {
                        "park": {
                            "id": self.park_id
                        }
                    },
                    "limit": 1000  # Получаем до 1000 водителей для поиска
                }
                
                try:
                    async with session.post(url, json=payload, headers=self.headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Ищем водителя по номеру телефона в результатах
                            driver_profiles = data.get("driver_profiles", [])
                            
                            for driver in driver_profiles:
                                profile = driver.get("driver_profile", {})
                                driver_phones = profile.get("phones", [])
                                
                                # Проверяем все телефоны водителя
                                for phone_obj in driver_phones:
                                    # phone_obj может быть строкой или объектом с полем "number"
                                    phone_str = phone_obj if isinstance(phone_obj, str) else phone_obj.get("number", "")
                                    if self._normalize_phone(phone_str) == normalized_phone:
                                        # Нашли водителя с нужным номером
                                        account = driver.get("account", {})
                                        car = driver.get("car", {})
                                        
                                        return {
                                            "found": True,
                                            "driver_id": profile.get("id"),
                                            "first_name": profile.get("first_name"),
                                            "last_name": profile.get("last_name"),
                                            "middle_name": profile.get("middle_name"),
                                            "phones": driver_phones,
                                            "work_status": profile.get("work_status"),
                                            "balance": account.get("balance"),
                                            "balance_limit": account.get("balance_limit"),
                                            "car": {
                                                "brand": car.get("brand"),
                                                "model": car.get("model"),
                                                "year": car.get("year"),
                                                "number": car.get("normalized_number")
                                            }
                                        }
                            
                            # Не нашли водителя с таким номером
                            return {"found": False}
                        else:
                            error_text = await response.text()
                            logging.error(f"Ошибка API Яндекс: {response.status}, {error_text}")
                            return {"found": False, "error": f"API error {response.status}"}
                except asyncio.TimeoutError:
                    logging.error("Таймаут при запросе к API Яндекс")
                    return {"found": False, "error": "timeout"}
                except Exception as e:
                    logging.error(f"Ошибка запроса к API: {e}")
                    return {"found": False, "error": str(e)}
                        
        except Exception as e:
            logging.error(f"Ошибка при проверке водителя: {e}")
            return {"found": False, "error": str(e)}
    
    async def get_driver_info(self, driver_id: str) -> Optional[Dict]:
        """
        Получает подробную информацию о водителе
        
        Args:
            driver_id: ID водителя в системе парка
        
        Returns:
            Dict с информацией о водителе или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v1/parks/driver-profiles/retrieve"
                
                payload = {
                    "fields": {
                        "driver_profile": [
                            "id", "phones", "first_name", "last_name", "middle_name",
                            "driver_license", "work_status", "hiring_source"
                        ],
                        "account": ["balance", "balance_limit"]
                    },
                    "query": {
                        "park": {
                            "id": self.park_id,
                            "driver_profile": {
                                "id": driver_id
                            }
                        }
                    }
                }
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logging.error(f"Ошибка получения информации о водителе: {response.status}")
                        return None
                        
        except Exception as e:
            logging.error(f"Ошибка при получении информации: {e}")
            return None
    
    async def get_driver_orders_count(self, driver_id: str) -> Optional[int]:
        """
        Получает количество выполненных заказов водителя с пагинацией и fallback-стратегиями
        
        Args:
            driver_id: ID водителя
        
        Returns:
            Количество заказов или None при ошибке
        """
        try:
            if not driver_id:
                logging.warning("get_driver_orders_count: driver_id пустой или None")
                return None
            
            # Очищаем driver_id от пробелов
            driver_id = str(driver_id).strip()
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v1/parks/orders/list"
                
                # Указываем большой диапазон дат для получения ВСЕХ заказов (за 5 лет)
                from datetime import timezone
                now = datetime.now(timezone.utc)
                five_years_ago = now - timedelta(days=1825)  # 5 лет для гарантии
                
                from_str = five_years_ago.isoformat().replace('+00:00', 'Z')
                to_str = now.isoformat().replace('+00:00', 'Z')
                
                total_orders = 0
                cursor = None
                page = 1
                
                logging.info(f"[ORDERS_CHECK] Начинаем проверку заказов для driver_id={driver_id}, park_id={self.park_id}")
                logging.info(f"[ORDERS_CHECK] Диапазон дат: {from_str} - {to_str}")
                
                # Получаем все заказы с пагинацией
                while True:
                    payload = {
                        "query": {
                            "park": {
                                "id": self.park_id,
                                "order": {
                                    "ended_at": {
                                        "from": from_str,
                                        "to": to_str
                                    }
                                },
                                "driver_profile": {
                                    "id": driver_id
                                }
                            }
                        },
                        "limit": 500  # Максимальный лимит API - 500 заказов за запрос
                    }
                    
                    # Добавляем cursor для пагинации (если есть)
                    if cursor:
                        payload["cursor"] = cursor
                    
                    logging.info(f"[ORDERS_CHECK] Driver {driver_id}, страница {page}, payload: {json.dumps(payload, ensure_ascii=False)[:200]}")
                    
                    try:
                        async with session.post(url, json=payload, headers=self.headers) as response:
                            response_text = await response.text()
                            
                            logging.info(f"[ORDERS_CHECK] Driver {driver_id}, страница {page}: HTTP {response.status}, длина ответа {len(response_text)}")
                            
                            if response.status == 200:
                                try:
                                    data = json.loads(response_text)
                                    orders = data.get("orders", [])
                                    
                                    logging.info(f"[ORDERS_CHECK] Driver {driver_id}, страница {page}: получено {len(orders)} заказов из API")
                                    
                                    # Логируем структуру первого заказа для понимания формата
                                    if page == 1 and orders:
                                        first_order_keys = list(orders[0].keys()) if orders else []
                                        logging.info(f"[ORDERS_CHECK] Driver {driver_id}: структура заказа (ключи): {first_order_keys}")
                                        if orders:
                                            statuses = [o.get("status") for o in orders[:5]]
                                            logging.info(f"[ORDERS_CHECK] Driver {driver_id}: примеры статусов: {statuses}")
                                    
                                    if len(orders) == 0:
                                        if page == 1:
                                            logging.warning(f"[ORDERS_CHECK] Driver {driver_id}: API вернул пустой массив заказов на первой странице!")
                                            logging.warning(f"[ORDERS_CHECK] Полный ответ API: {response_text[:1000]}")
                                        break
                                    
                                    # Считаем ВСЕ заказы, так как API должен возвращать только завершенные
                                    # Но на всякий случай исключаем cancelled
                                    completed = [o for o in orders if o.get("status") != "cancelled"]
                                    
                                    page_count = len(completed)
                                    total_orders += page_count
                                    
                                    logging.info(f"[ORDERS_CHECK] Driver {driver_id}, страница {page}: учтено {page_count} заказов (всего {len(orders)}), общий счетчик: {total_orders}")
                                    
                                    # Проверяем, есть ли следующая страница
                                    cursor = data.get("cursor")
                                    if not cursor or len(orders) < 500:
                                        logging.info(f"[ORDERS_CHECK] Driver {driver_id}: это последняя страница (cursor={cursor}, orders={len(orders)})")
                                        break
                                    
                                    page += 1
                                    
                                    # Защита от бесконечного цикла
                                    if page > 50:
                                        logging.warning(f"[ORDERS_CHECK] Driver {driver_id}: достигнут лимит страниц (50), прерываем. Текущий счетчик: {total_orders}")
                                        break
                                    
                                    # Небольшая задержка между запросами
                                    await asyncio.sleep(0.3)
                                    
                                except json.JSONDecodeError as json_error:
                                    logging.error(f"[ORDERS_CHECK] Driver {driver_id}: ошибка парсинга JSON: {json_error}, ответ: {response_text[:500]}")
                                    return total_orders if total_orders > 0 else None
                            else:
                                logging.error(f"[ORDERS_CHECK] Driver {driver_id}, страница {page}: HTTP {response.status}, ошибка: {response_text[:1000]}")
                                # Если это не первая страница, возвращаем то что есть
                                if page > 1:
                                    return total_orders
                                # Если первая страница с ошибкой - пробуем fallback
                                return await self._get_orders_count_fallback(session, driver_id)
                    
                    except aiohttp.ClientError as client_error:
                        logging.error(f"[ORDERS_CHECK] Driver {driver_id}: ошибка HTTP клиента: {client_error}")
                        if page > 1:
                            return total_orders
                        return None
                
                logging.info(f"[ORDERS_CHECK] Driver {driver_id}: ИТОГО заказов = {total_orders}")
                return total_orders
                        
        except Exception as e:
            logging.error(f"[ORDERS_CHECK] Ошибка при получении заказов для {driver_id}: {e}", exc_info=True)
            return None
    
    async def _get_orders_count_fallback(self, session: aiohttp.ClientSession, driver_id: str) -> Optional[int]:
        """
        Fallback-метод: пытаемся получить заказы через booked_at вместо ended_at
        """
        try:
            logging.info(f"[ORDERS_FALLBACK] Пробуем fallback для driver_id={driver_id}")
            
            url = f"{self.BASE_URL}/v1/parks/orders/list"
            
            from datetime import timezone
            now = datetime.now(timezone.utc)
            five_years_ago = now - timedelta(days=1825)
            
            from_str = five_years_ago.isoformat().replace('+00:00', 'Z')
            to_str = now.isoformat().replace('+00:00', 'Z')
            
            payload = {
                "query": {
                    "park": {
                        "id": self.park_id,
                        "order": {
                            "booked_at": {  # Используем booked_at вместо ended_at
                                "from": from_str,
                                "to": to_str
                            }
                        },
                        "driver_profile": {
                            "id": driver_id
                        }
                    }
                },
                "limit": 500
            }
            
            async with session.post(url, json=payload, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    orders = data.get("orders", [])
                    completed = [o for o in orders if o.get("status") != "cancelled"]
                    count = len(completed)
                    logging.info(f"[ORDERS_FALLBACK] Driver {driver_id}: получено {count} заказов через fallback")
                    return count
                else:
                    logging.warning(f"[ORDERS_FALLBACK] Driver {driver_id}: fallback failed with status {response.status}")
                    return None
        except Exception as e:
            logging.error(f"[ORDERS_FALLBACK] Ошибка fallback для {driver_id}: {e}")
            return None
    
    async def get_driver_position(self, driver_id: str) -> Optional[str]:
        """
        Определяет позицию водителя в парке (грузовой/экспресс)
        
        Args:
            driver_id: ID водителя
        
        Returns:
            "cargo" для грузового, "express" для экспресс, или None
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v1/parks/driver-profiles/retrieve"
                
                payload = {
                    "fields": {
                        "driver_profile": ["id", "work_status"],
                        "car": ["brand", "model", "amenities", "cargo_type"]
                    },
                    "query": {
                        "park": {
                            "id": self.park_id,
                            "driver_profile": {
                                "id": driver_id
                            }
                        }
                    }
                }
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Пытаемся определить позицию по типу автомобиля или amenities
                        driver_profiles = data.get("driver_profiles", [])
                        if driver_profiles:
                            driver = driver_profiles[0]
                            car = driver.get("car", {})
                            
                            # Проверяем cargo_type (если есть)
                            cargo_type = car.get("cargo_type")
                            if cargo_type:
                                # Если cargo_type указывает на грузовой транспорт
                                if cargo_type in ["cargo", "van", "truck"]:
                                    return "cargo"
                                else:
                                    return "express"
                            
                            # Проверяем по марке/модели автомобиля (если есть типичные грузовые марки)
                            brand = car.get("brand", "").lower()
                            model = car.get("model", "").lower()
                            
                            # Список ключевых слов для грузовых авто
                            cargo_keywords = ["грузовой", "фургон", "газель", "фиат", "лада largus", "largus", "mercedes", "ford transit", "volkswagen crafter"]
                            
                            if any(keyword in brand or keyword in model for keyword in cargo_keywords):
                                return "cargo"
                            
                            # По умолчанию считаем экспрессом
                            return "express"
                        
                        return None
                    else:
                        logging.warning(f"Не удалось получить позицию водителя: {response.status}")
                        return None
                        
        except Exception as e:
            logging.error(f"Ошибка при получении позиции водителя: {e}")
            return None
    
    def _normalize_phone(self, phone: str) -> str:
        """
        Нормализует номер телефона, убирая все лишние символы
        
        Args:
            phone: Исходный номер телефона
        
        Returns:
            Нормализованный номер
        """
        # Убираем все символы кроме цифр и +
        cleaned = ''.join(c for c in phone if c.isdigit() or c == '+')
        
        # Если начинается с 8, заменяем на +7
        if cleaned.startswith('8'):
            cleaned = '+7' + cleaned[1:]
        
        # Если начинается с 7 без +, добавляем +
        if cleaned.startswith('7') and not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        # Если нет кода страны, добавляем +7
        if not cleaned.startswith('+'):
            cleaned = '+7' + cleaned
        
        return cleaned

