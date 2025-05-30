import asyncio
import json
import redis.asyncio as redis

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message


class NotificationService:
    def __init__(self, redis_client, db, dp, bot):
        self.redis_client = redis_client
        self.db = db
        self.dp = dp
        self.bot = bot
        self.channels = ['fl_projects', 'kwork_projects', 'freelancer_projects']

    @staticmethod
    def format_project_message(data: str, channel: str):
        try:
            project = json.loads(data)
        except Exception as e:
            return data, '', ''
        
        project_title = project.get('title', 'Без названия')
        project_desc = project.get('description', '')
        project_url = project.get('url', '')
        project_budget = project.get('budget', {})

        max_desc_length = 200
        if len(project_desc) > max_desc_length:
            project_desc = project_desc[:max_desc_length].rstrip()
            project_desc += '...'

        if project_budget:
            min_budget = project_budget.get('minimum')
            max_budget = project_budget.get('maximum')
            currency = project_budget.get('currency', '')

            def format_value(value):
                try:
                    value_float = float(value)
                    if value_float.is_integer():
                        return int(value_float)
                    else:
                        return round(value_float, 2)
                except Exception:
                    return value

            if min_budget is not None:
                min_budget = format_value(min_budget)
            if max_budget is not None:
                max_budget = format_value(max_budget)

            if min_budget and max_budget:
                if min_budget == max_budget:
                    budget_str = f'Бюджет: {min_budget} {currency}'
                else:
                    budget_str = f'Бюджет: {min_budget} - {max_budget} {currency}'
            elif min_budget:
                budget_str = f'Бюджет: {min_budget} {currency}'
            elif max_budget:
                budget_str = f'Бюджет: {max_budget} {currency}'
            else:
                budget_str = 'Бюджет не указан'
        else:
            budget_str = 'Бюджет не указан'


        if channel == 'fl_projects':
            source_emoji = '🟢'
            source_text = 'FL'
        elif channel == 'kwork_projects':
            source_emoji = '🔘'
            source_text = 'Kwork'
        elif channel == 'freelancer_projects':
            source_emoji = '⚪'
            source_text = 'Freelancer'
        else:
            source_emoji = ''
            source_text = ''

        note_emoji = '📝'

        message_text = (
            f'{source_emoji} <b>{project_title}</b> ({source_text})\n\n'
            f'{note_emoji} {project_desc}\n\n'
            f'{budget_str}'
        )
        return message_text, project_url, project_title

    async def listen(self):
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(*self.channels)
        print(f'Подписались на каналы: {', '.join(self.channels)}', flush=True)
        try:
            async for message in pubsub.listen():
                if message.get('type') == 'message':
                    channel = message.get('channel')
                    data = message.get('data')
                    if isinstance(channel, bytes):
                        channel = channel.decode('utf-8')
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')

                    if channel == 'fl_projects':
                        users = self.db.get_users_for_fl()
                    elif channel == 'kwork_projects':
                        users = self.db.get_users_for_kwork()
                    elif channel == 'freelancer_projects':
                        users = self.db.get_users_for_freelancer()
                    else:
                        users = []

                    eligible_users = []
                    for user in users:
                        chat_id = user[1]
                        keywords = user[2]
                        msg_text = data.lower()
                        if keywords and keywords.strip():
                            keyword_list = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()]
                            if any(kw in msg_text for kw in keyword_list):
                                eligible_users.append(user)
                        else:
                            eligible_users.append(user)

                    for user in eligible_users:
                        chat_id = user[1]
                        try:
                            message_text, project_url, project_title = self.format_project_message(data, channel)

                            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text='Перейти к проекту', url=project_url)]
                            ])

                            await self.bot.send_message(
                                chat_id,
                                message_text,
                                reply_markup=keyboard,
                                parse_mode=ParseMode.HTML
                            )
                            print(f'Уведомление отправлено пользователю {chat_id} с данными проекта: {project_title}', flush=True)
                        except Exception as e:
                            print(f'Ошибка отправки уведомления пользователю {chat_id}: {e}', flush=True)

        except asyncio.CancelledError:
            print('Служба уведомлений прервана.', flush=True)
        finally:
            try:
                await pubsub.unsubscribe(*self.channels)
            except Exception as e:
                print(f'Ошибка отписки от каналов: {e}', flush=True)
            try:
                await pubsub.close()
            except Exception as e:
                print(f'Ошибка закрытия pubsub: {e}', flush=True)

    async def run(self):
        await self.listen()
