import aiohttp
import asyncio
import logging
import json
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
        Получает количество выполненных заказов водителя
        
        Args:
            driver_id: ID водителя
        
        Returns:
            Количество заказов или None при ошибке
        """
        try:
            if not driver_id:
                logging.warning("get_driver_orders_count: driver_id пустой или None")
                return None
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v1/parks/orders/list"
                
                # Получаем все заказы водителя
                payload = {
                    "query": {
                        "park": {
                            "id": self.park_id,
                            "driver_profile": {
                                "id": driver_id
                            }
                        }
                    },
                    "limit": 10000  # Увеличиваем лимит для получения всех заказов
                }
                
                logging.info(f"Запрос заказов для driver_id={driver_id}, park_id={self.park_id}, url={url}")
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            # Парсим JSON из текста ответа
                            data = json.loads(response_text)
                            orders = data.get("orders", [])
                            
                            # Логируем структуру ответа для отладки
                            logging.info(f"Driver {driver_id}: API ответ статус 200, получено заказов в массиве: {len(orders)}")
                            
                            # Проверяем структуру ответа
                            if "orders" not in data:
                                logging.warning(f"Driver {driver_id}: в ответе нет ключа 'orders'. Структура ответа: {list(data.keys())[:10]}")
                                logging.warning(f"Driver {driver_id}: полный ответ API (первые 1000 символов): {response_text[:1000]}")
                            
                            if len(orders) == 0:
                                logging.warning(f"Driver {driver_id}: массив заказов пустой. Полный ответ API: {response_text[:1000]}")
                                # Возвращаем 0, а не None, если массив пустой (это валидный результат)
                                return 0
                            
                            # Считаем все заказы (API возвращает только выполненные/активные)
                            # Если нужны только завершенные, фильтруем по статусу
                            completed_orders = [o for o in orders if o.get("status") in ["complete", "finished"]]
                            # Если нет завершенных, считаем все (возможно API уже возвращает только завершенные)
                            count = len(completed_orders) if completed_orders else len(orders)
                            logging.info(f"Driver {driver_id}: всего заказов в ответе {len(orders)}, завершенных {len(completed_orders)}, итого: {count}")
                            return count
                        except Exception as parse_error:
                            logging.error(f"Driver {driver_id}: ошибка парсинга ответа API: {parse_error}, ответ: {response_text[:500]}")
                            return None
                    else:
                        logging.warning(f"Не удалось получить заказы для {driver_id}: статус {response.status}, ошибка: {response_text[:500]}")
                        return None
                        
        except Exception as e:
            logging.error(f"Ошибка при получении заказов для {driver_id}: {e}", exc_info=True)
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

