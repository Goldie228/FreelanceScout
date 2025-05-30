import os
import time
import json
import redis
from dotenv import load_dotenv

from freelancersdk.session import Session
from freelancersdk.resources.projects.projects import search_projects
from freelancersdk.resources.projects.exceptions import ProjectsNotFoundException
from freelancersdk.resources.projects.helpers import create_search_projects_filter

def get_projects():
    load_dotenv()
    # Здесь используется URL и OAuth-токен для сервиса Freelancer (а не FL.ru)
    url = os.getenv('FLN_URL')
    oauth_token = os.getenv("FLN_OAUTH_TOKEN")
    session = Session(oauth_token=oauth_token, url=url)

    query = ''
    search_filter = create_search_projects_filter(
        sort_field='time_updated',
        or_search_query=False,
    )

    try:
        p = search_projects(
            session,
            query=query,
            search_filter=search_filter
        )
    except ProjectsNotFoundException as e:
        print('Error message: {}'.format(e.message))
        print('Server response: {}'.format(e.error_code))
        return None
    else:
        return p

def get_recent_projects(interval_seconds=330):
    data = get_projects()
    if data is None:
        return []
    recent_projects = []
    now = time.time()

    # В данных Freelancer время публикации хранится в поле "submitdate" как UNIX‑timestamp
    projects = data.get('projects', [])
    for project in projects:
        project_time = project.get('submitdate', 0)
        if now - project_time <= interval_seconds:
            recent_projects.append(project)
    return recent_projects

def publish_to_redis(message: dict, channel: str = "freelancer_projects"):
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.publish(channel, json.dumps(message))

def process_projects():
    # Подключаемся к Redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    recent = get_recent_projects()
    if recent:
        print(f"\nНайдено {len(recent)} новых проектов за последние 5 минут:")
        for project in recent:
            project_id = project.get("id")
            # Формируем ключ для проверки, например: "freelancer:39459678"
            redis_key = f"freelancer:{project_id}"
            if r.exists(redis_key):
                # Если проект уже был обработан – пропускаем
                continue

            # Выбираем основные данные:
            title = project.get("title")
            # Если полнотекстовое описание отсутствует, то используем preview_description
            description = project.get("description") or project.get("preview_description")
            # Формируем URL проекта.
            # Если есть поле seo_url, то базовый URL будет "https://www.freelancer.com/" + seo_url
            seo_url = project.get("seo_url")
            if seo_url:
                url = "https://www.freelancer.com/projects/" + seo_url
            else:
                url = project.get("url", "")  # резервный вариант
            # Обрабатываем бюджет. В данных Freelancer бюджет – это объект с полями "minimum" и "maximum"
            budget_obj = project.get("budget", {})
            budget = {
                "minimum": budget_obj.get("minimum"),
                "maximum": budget_obj.get("maximum")
            }
            # Иногда полезно указать валютный знак из объекта "currency"
            currency = project.get("currency")
            if currency:
                budget["currency"] = currency.get("sign")  # например, '$'

            # Формируем сообщение для публикации
            message = {
                "id": project_id,
                "title": title,
                "description": description,
                "url": url,
                "budget": budget
            }

            print(message)

            # Публикуем сообщение в Redis на канал "freelancer_projects"
            publish_to_redis(message, channel="freelancer_projects")
            print(f"Опубликован проект {project_id}: {title}")
            # Записываем ключ в Redis с TTL 6 минут (360 секунд), чтобы не публиковать повторно
            r.set(redis_key, "1", ex=360)
    else:
        print("\nНовых проектов за последние 5 минут не найдено.")

def main():
    while True:
        process_projects()
        # Пауза 5 минут между проверками
        time.sleep(300)

if __name__ == '__main__':
    main()
