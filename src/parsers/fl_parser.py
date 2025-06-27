import os
import time
import threading
import json
import redis
import re
import requests
import feedparser
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

class FlParser:
    URL = None

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.update_event = threading.Event()

        load_dotenv()
        FlParser.URL = os.getenv('FL_URL')
        if not FlParser.URL:
            raise ValueError("FL_URL не задан в переменных окружения!")

        listener = threading.Thread(
            target=self._listen_for_updates,
            name="RedisListener",
            daemon=True
        )
        listener.start()

        self.run()

    @classmethod
    def fetch_rss_feed(cls):
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/115.0.0.0 Safari/537.36'
            )
        }
        try:
            response = requests.get(cls.URL, headers=headers)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)
                return feed
            else:
                print(f'Ошибка запроса: {response.status_code}')
                return None
        except Exception as e:
            print('Ошибка запроса:', e)
            return None

    @staticmethod
    def get_structured_feed(feed):
        if not feed or not feed.entries:
            return {}
        
        channel = {
            'title': feed.feed.get('title', ''),
            'link': feed.feed.get('link', ''),
            'description': feed.feed.get('description', ''),
            'language': feed.feed.get('language', ''),
            'pubDate': feed.feed.get('pubDate', ''),
            'lastBuildDate': feed.feed.get('lastBuildDate', '')
        }
        
        items = []
        for entry in feed.entries:
            item = {
                'title': entry.get('title', ''),
                'link': entry.get('link', ''),
                'description': entry.get('description', ''),
                'pubDate': entry.get('published', ''),
                'guid': entry.get('guid', ''),
                'category': entry.get('category', '')
            }
            items.append(item)
        
        return {
            'channel': channel,
            'items': items
        }

    @staticmethod
    def filter_recent_items(data, minutes=5):
        recent_items = []
        now = datetime.now(timezone.utc)
        
        for item in data.get('items', []):
            pub_date_str = item.get('pubDate')
            if not pub_date_str:
                continue
            try:
                pub_dt = parsedate_to_datetime(pub_date_str)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                else:
                    pub_dt = pub_dt.astimezone(timezone.utc)
            except Exception as e:
                print(f'Ошибка преобразования даты {pub_date_str}:', e)
                continue
            
            if now - pub_dt <= timedelta(minutes=minutes):
                recent_items.append(item)
        
        data['items'] = recent_items
        return data

    @staticmethod
    def parse_budget(text):
        match = re.search(r'[бБ]юджет\s*:\s*([\d\s,.]+)\s*(₽)?', text)
        if match:
            num_str = match.group(1)
            try:
                value = float(num_str.replace(' ', '').replace(',', '.'))
                return {
                    'minimum': value, 
                    'maximum': value, 
                    'currency': match.group(2) if match.group(2) else '₽'
                }
            except Exception as e:
                print(f'Ошибка преобразования бюджета {num_str}:', e)
        return {'minimum': None, 'maximum': None, 'currency': None}

    def publish_to_redis(self, message: dict, channel: str = 'fl_projects'):
        self.redis_client.publish(channel, json.dumps(message))

    def fl_parser_run(self):
        feed = self.fetch_rss_feed()
        if not feed:
            print('RSS лента не получена.')
            return

        structured_data = self.get_structured_feed(feed)
        recent_data = self.filter_recent_items(structured_data, minutes=5)
        
        if recent_data and recent_data.get('items'):
            for item in recent_data['items']:
                project_id = item.get('guid') or item.get('link')
                if not project_id:
                    continue

                redis_key = f'fl:{project_id}'
                if self.redis_client.exists(redis_key):
                    continue

                title = item.get('title')
                description = item.get('description')
                url = item.get('link')

                budget = self.parse_budget(title)
                if budget['minimum'] is None:
                    budget = self.parse_budget(description)
                
                message = {
                    'id': project_id,
                    'title': title,
                    'description': description,
                    'url': url,
                    'budget': budget
                }
                self.publish_to_redis(message, channel='fl_projects')
                self.redis_client.set(redis_key, '1', ex=360)

    def _listen_for_updates(self):
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe('data_updates')
        for message in pubsub.listen():
            if message['type'] == 'message':
                print('Получено сообщение data_updates (FL)— сбрасываем таймер обновления')
                self.update_event.set()

    def run(self):
        while True:
            triggered = self.update_event.wait(timeout=300)
            if triggered:
                self.update_event.clear()

            try:
                self.fl_parser_run()
            except Exception as e:
                print('Ошибка запроса:', e)

