import os
import time
import json
import redis
import re
import requests
import feedparser
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

def fetch_rss_feed(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            feed = feedparser.parse(response.content)
            return feed
        else:
            print(f"Ошибка запроса: {response.status_code}")
            return None
    except Exception as e:
        print("Ошибка запроса:", e)
        return None

def get_structured_feed(feed):
    if not feed or not feed.entries:
        return {}
    
    channel = {
        "title": feed.feed.get("title", ""),
        "link": feed.feed.get("link", ""),
        "description": feed.feed.get("description", ""),
        "language": feed.feed.get("language", ""),
        "pubDate": feed.feed.get("pubDate", ""),
        "lastBuildDate": feed.feed.get("lastBuildDate", "")
    }
    
    items = []
    for entry in feed.entries:
        item = {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "description": entry.get("description", ""),
            "pubDate": entry.get("published", ""),
            "guid": entry.get("guid", ""),
            "category": entry.get("category", "")
        }
        items.append(item)
    
    return {
        "channel": channel,
        "items": items
    }

def filter_recent_items(data, minutes=5):
    recent_items = []
    now = datetime.now(timezone.utc)
    
    for item in data.get("items", []):
        pub_date_str = item.get("pubDate")
        if not pub_date_str:
            continue
        try:
            pub_dt = parsedate_to_datetime(pub_date_str)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            else:
                pub_dt = pub_dt.astimezone(timezone.utc)
        except Exception as e:
            print(f"Ошибка преобразования даты '{pub_date_str}':", e)
            continue
        
        if now - pub_dt <= timedelta(minutes=minutes):
            recent_items.append(item)
    
    data["items"] = recent_items
    return data

def parse_budget(text):
    """
    Ищет в переданном тексте фразу "бюджет:" (без учета регистра) и число,
    после которого может следовать знак рубля (₽). Возвращает словарь вида:
         {"minimum": <value>, "maximum": <value>, "currency": "₽"}
    Если данные не найдены, возвращает значения по умолчанию.
    """
    # Пример: "Бюджет: 1000 ₽" или "бюджет:1000" (возможно, с пробелами)
    match = re.search(r'[бБ]юджет\s*:\s*([\d\s,.]+)\s*(₽)?', text)
    if match:
        num_str = match.group(1)
        try:
            # Убираем пробелы и заменяем запятые на точки, затем приводим к float
            value = float(num_str.replace(" ", "").replace(",", "."))
            return {"minimum": value, "maximum": value, "currency": match.group(2) if match.group(2) else "₽"}
        except Exception as e:
            print(f"Ошибка преобразования бюджета '{num_str}':", e)
    # Если бюджет не найден, возвращаем значения по умолчанию
    return {"minimum": None, "maximum": None, "currency": None}

def publish_to_redis(message: dict, channel: str = "fl_projects"):
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.publish(channel, json.dumps(message))

def process_rss_projects():
    load_dotenv()
    rss_url = os.getenv('FL_URL')  # Например, URL RSS-ленты FL.ru
    feed = fetch_rss_feed(rss_url)
    if not feed:
        print("RSS лента не получена.")
        return
    structured_data = get_structured_feed(feed)
    recent_data = filter_recent_items(structured_data, minutes=500)
    
    r = redis.Redis(host='localhost', port=6379, db=0)
    if recent_data and recent_data.get("items"):
        print("Найдены новые элементы за последние 5 минут:")
        for item in recent_data["items"]:
            # Используем guid (или если его нет, берем link) как уникальный идентификатор
            project_id = item.get("guid") or item.get("link")
            if not project_id:
                continue

            redis_key = f"fl:{project_id}"
            if r.exists(redis_key):
                continue

            title = item.get("title")
            description = item.get("description")
            url = item.get("link")
            # Пытаемся извлечь бюджет из заголовка. Если нет – пробуем из описания.
            budget = parse_budget(title)
            if budget["minimum"] is None:
                budget = parse_budget(description)
            
            message = {
                "id": project_id,
                "title": title,
                "description": description,
                "url": url,
                "budget": budget
            }
            print(message)
            publish_to_redis(message, channel="fl_projects")
            print(f"Опубликовано сообщение для проекта {project_id}: {title}")
            r.set(redis_key, "1", ex=360)
    else:
        print("Новых элементов за последние 5 минут не найдено.")

def main():
    while True:
        process_rss_projects()
        time.sleep(300)

if __name__ == '__main__':
    main()
