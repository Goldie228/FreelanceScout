import os
import time
import json
import redis
from dotenv import load_dotenv

from freelancersdk.session import Session
from freelancersdk.resources.projects.projects import search_projects
from freelancersdk.resources.projects.exceptions import ProjectsNotFoundException
from freelancersdk.resources.projects.helpers import create_search_projects_filter


class FreelancerParser:
    URL = None

    def __init__(self, redis_client):
        self.redis_client = redis_client

        load_dotenv()
        FreelancerParser.URL = os.getenv('FLN_URL')
        if not FreelancerParser.URL:
            raise ValueError("FLN_URL не задана в переменных окружения!")
        self.oauth_token = os.getenv('FLN_OAUTH_TOKEN')
        if not self.oauth_token:
            raise ValueError("FLN_OAUTH_TOKEN не задана в переменных окружения!")

        self.run()

    def get_projects(self):
        session = Session(oauth_token=self.oauth_token, url=self.URL)
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
            print(f'Error message: {e.message}')
            print(f'Server response: {e.error_code}')
            return None
        else:
            return p

    def get_recent_projects(self, interval_seconds=360):
        data = self.get_projects()
        if data is None:
            return []
        recent_projects = []
        now = time.time()

        projects = data.get('projects', [])
        for project in projects:
            project_time = project.get('submitdate', 0)
            if now - project_time <= interval_seconds:
                recent_projects.append(project)
        return recent_projects

    def publish_to_redis(self, message: dict, channel: str = 'freelancer_projects'):
        self.redis_client.publish(channel, json.dumps(message))

    def freelancer_parser_run(self):
        recent = self.get_recent_projects()
        if recent:
            for project in recent:
                project_id = project.get('id')
                if not project_id:
                    continue

                redis_key = f'freelancer:{project_id}'
                if self.redis_client.exists(redis_key):
                    continue

                title = project.get('title')
                description = project.get('description') or project.get('preview_description')
                seo_url = project.get('seo_url')
                if seo_url:
                    url = f'{self.URL}/projects/{seo_url}'
                else:
                    url = project.get('url', '')

                budget_obj = project.get('budget', {})
                budget = {
                    'minimum': budget_obj.get('minimum'),
                    'maximum': budget_obj.get('maximum')
                }
                currency = project.get('currency')
                if currency:
                    budget['currency'] = currency.get('sign')
                else:
                    budget['currency'] = None

                message = {
                    'id': project_id,
                    'title': title,
                    'description': description,
                    'url': url,
                    'budget': budget
                }

                self.publish_to_redis(message, channel='freelancer_projects')
                self.redis_client.set(redis_key, '1', ex=360)

    def run(self):
        while True:
            try:
                self.freelancer_parser_run()
            except Exception as e:
                print('Ошибка запроса:', e)

            time.sleep(300)
