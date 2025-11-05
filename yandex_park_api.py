import aiohttp
import asyncio
import logging
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
            async with aiohttp.ClientSession() as session:
                url = f"{self.BASE_URL}/v1/parks/orders/list"
                
                payload = {
                    "query": {
                        "park": {
                            "id": self.park_id,
                            "driver_profile": {
                                "id": driver_id
                            }
                        }
                    },
                    "limit": 1000
                }
                
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return len(data.get("orders", []))
                    else:
                        logging.warning(f"Не удалось получить заказы: {response.status}")
                        return None
                        
        except Exception as e:
            logging.error(f"Ошибка при получении заказов: {e}")
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

