import os
import time
import json
import redis
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta, timezone

def fetch_page_html(page=1):
    url = f"https://kwork.ru/projects?a=1&view=0&page={page}"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    
    # Прокручиваем страницу до конца для подгрузки всех данных
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    
    html = driver.page_source
    driver.quit()
    return html

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

def extract_projects_from_json(html):
    key = '"wantsListData":'
    index = html.find(key)
    if index == -1:
        print("Не найден раздел wantsListData в HTML.")
        return []
    
    start_index = html.find('{', index)
    if start_index == -1:
        print("Не найдено начало JSON объекта после wantsListData.")
        return []
    
    json_text = extract_json_object(html, start_index)
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

def filter_recent_projects(projects, minutes=5):
    recent_projects = []
    now = datetime.now(timezone.utc)
    
    # Предполагается, что поле "date_create" имеет формат "YYYY-MM-DD HH:MM:SS"
    # и время указано в часовом поясе UTC+3 для Kwork.
    for pr in projects:
        date_str = pr.get("date_create")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            dt = dt.replace(tzinfo=timezone(timedelta(hours=3)))  # время Kwork: UTC+3
        except Exception as e:
            print(f"Ошибка преобразования даты '{date_str}':", e)
            continue
        
        if now - dt <= timedelta(minutes=minutes):
            recent_projects.append(pr)
    return recent_projects

def publish_to_redis(message: dict, channel: str = "kwork_projects"):
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.publish(channel, json.dumps(message))

def process_kwork_projects():
    r = redis.Redis(host='localhost', port=6379, db=0)
    page = 1
    html = fetch_page_html(page)
    projects = extract_projects_from_json(html)
    
    if projects:
        print(f"Найдено проектов на странице {page}: {len(projects)}")
        recent_projects = filter_recent_projects(projects, minutes=500)
        if recent_projects:
            print(f"\nНайдено новых проектов за последние 5 минут: {len(recent_projects)}")
            for proj in recent_projects:
                # Используем поле "id" как уникальный идентификатор
                project_id = proj.get("id")
                if not project_id:
                    continue
                
                redis_key = f"kwork:{project_id}"
                if r.exists(redis_key):
                    continue
                
                # Формируем бюджет на основе объекта "budget" и "currency"
                # Объект "budget" содержит минимум и максимум
                budget = {
                    "minimum": proj.get("priceLimit"),
                    "maximum": proj.get("possiblePriceLimit"),
                    "currency": "₽"
                }

                message = {
                    "id": project_id,
                    "title": proj.get("name"),
                    "description": proj.get("description"),
                    "url": f"https://kwork.ru/projects/{project_id}",
                    "budget": budget
                }
                
                print(message)
                publish_to_redis(message, channel="kwork_projects")
                print(f"Опубликован проект {project_id}: {proj.get('name')}")
                r.set(redis_key, "1", ex=360)
        else:
            print("Новых проектов за последние 5 минут не найдено.")
    else:
        print("Проекты не найдены.")

def main():
    while True:
        process_kwork_projects()
        time.sleep(300)

if __name__ == '__main__':
    main()
