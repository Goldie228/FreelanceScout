import asyncio
import redis.asyncio as redis


class NotificationService:
    def __init__(self, redis_client, db, dp):
        self.redis_client = redis_client
        self.db = db
        self.dp = dp
        self.channels = ['fl_projects', 'kwork_projects', 'freelancer_projects']

    async def listen(self):
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(*self.channels)
        print(f"Подписались на каналы: {', '.join(self.channels)}")
        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    if isinstance(channel, bytes):
                        channel = channel.decode('utf-8')
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    print(f"Получено сообщение на канале {channel}: {data}")

                    if channel == "fl_projects":
                        users = self.db.get_users_for_fl()
                    elif channel == "kwork_projects":
                        users = self.db.get_users_for_kwork()
                    elif channel == "freelancer_projects":
                        users = self.db.get_users_for_freelancer()
                    else:
                        users = []

                    eligible_users = []

                    for user in users:
                        chat_id = user[1]
                        keywords = user[2]

                        if keywords and keywords.strip():
                            keyword_list = [kw.strip().lower() for kw in keywords.split(",") if kw.strip()]
                            msg_text = data.lower()
                            if any(kw in msg_text for kw in keyword_list):
                                eligible_users.append(user)
                                print(f"Пользователь {chat_id} подходит по ключевым словам и добавлен в список для уведомлений.")
                            else:
                                print(f"Ключевые слова не найдены у пользователя {chat_id} – уведомление не отправлено.")
                        else:
                            eligible_users.append(user)
                            print(f"Пользователь {chat_id} без ключевых слов добавлен в список уведомлений.")

                    for user in eligible_users:
                        chat_id = user[1]
                        print(f"Отправка уведомления пользователю {chat_id} с данными: {data}")

        except asyncio.CancelledError:
            print("Служба уведомлений прервана.")
        finally:
            await pubsub.unsubscribe(*self.channels)
            await pubsub.close()

    async def run(self):
        await self.listen()


if __name__ == '__main__':
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    service = NotificationService(redis_client)
    try:
        asyncio.run(service.run())
    except KeyboardInterrupt:
        print('Прерывание службы уведомлений.')
