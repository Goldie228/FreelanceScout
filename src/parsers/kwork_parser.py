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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


class KworkParser:
    URL = None

    def __init__(self, redis_client):
        self.redis_client = redis_client

        load_dotenv()
        KworkParser.URL = os.getenv('KWORK_URL')
        if not KworkParser.URL:
            raise ValueError("KWORK_URL не задана в переменных окружения!")

        self.run()

    def fetch_page_html(self, page=1):
        url = f"{self.URL}?a=1&view=0&page={page}"

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        html = driver.page_source
        driver.quit()
        return html

    @staticmethod
    def extract_json_object(text, start_index):
        counter = 0
        for i, char in enumerate(text[start_index:], start=start_index):
            if char == '{':
                counter += 1
            elif char == '}':
                counter -= 1
                if counter == 0:
                    return text[start_index:i+1]
        return ""

    def extract_projects_from_json(self, html):
        key = '"wantsListData":'
        index = html.find(key)
        if index == -1:
            print("Не найден раздел wantsListData в HTML.")
            return []
        
        start_index = html.find('{', index)
        if start_index == -1:
            print("Не найдено начало JSON объекта после wantsListData.")
            return []
        
        json_text = self.extract_json_object(html, start_index)
        if not json_text:
            print("Не удалось извлечь балансированный JSON.")
            return []
        
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            print("Ошибка при декодировании JSON:", e)
            return []
        
        pagination = data.get("pagination", {})
        projects = pagination.get("data", [])
        return projects

    @staticmethod
    def filter_recent_projects(projects, minutes=5):
        recent_projects = []
        now = datetime.now(timezone.utc)

        for pr in projects:
            date_str = pr.get("date_create")
            if not date_str:
                continue
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                dt = dt.replace(tzinfo=timezone(timedelta(hours=3)))
            except Exception as e:
                print(f"Ошибка преобразования даты '{date_str}':", e)
                continue
            
            if now - dt <= timedelta(minutes=minutes):
                recent_projects.append(pr)
        return recent_projects

    def publish_to_redis(self, message: dict, channel: str = "kwork_projects"):
        self.redis_client.publish(channel, json.dumps(message))

    def kwork_parser_run(self):
        page = 1
        html = self.fetch_page_html(page)
        projects = self.extract_projects_from_json(html)
        
        if projects:
            recent_projects = self.filter_recent_projects(projects, minutes=5)
            if recent_projects:
                for proj in recent_projects:
                    project_id = proj.get("id")
                    if not project_id:
                        continue
                    
                    redis_key = f"kwork:{project_id}"
                    if self.redis_client.exists(redis_key):
                        continue

                    budget = {
                        "minimum": proj.get("priceLimit"),
                        "maximum": proj.get("possiblePriceLimit"),
                        "currency": "₽"
                    }

                    message = {
                        "id": project_id,
                        "title": proj.get("name"),
                        "description": proj.get("description"),
                        "url": f"{self.URL}/{project_id}",
                        "budget": budget
                    }

                    self.publish_to_redis(message, channel="kwork_projects")
                    self.redis_client.set(redis_key, "1", ex=360)

    def run(self):
        while True:
            try:
                self.kwork_parser_run()
            except Exception as e:
                print('Ошибка запроса:', e)

            time.sleep(300)
