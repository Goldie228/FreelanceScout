import os
import psycopg2
from psycopg2.extensions import connection as _connection
from dotenv import load_dotenv


class Database:
    def __init__(self):
        load_dotenv()

        dbname = os.getenv('POSTGRES_DB')
        user = os.getenv('POSTGRES_USER')
        password = os.getenv('POSTGRES_PASSWORD')
        host = os.getenv('POSTGRES_HOST')
        port = os.getenv('POSTGRES_PORT')
        dsn = f'dbname={dbname} user={user} password={password} host={host} port={port}'

        self.dsn = dsn
        self.conn: _connection = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(self.dsn)
            self.conn.autocommit = True
            self.create_tables()
            print('Подключение к базе данных успешно установлено.')
        except Exception as e:
            print('Ошибка подключения к базе данных:', e)
            raise e

    def disconnect(self):
        if self.conn:
            self.conn.close()
            print("Подключение к базе данных закрыто.")
            self.conn = None

    def create_tables(self):
        create_table_query = '''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                chat_id TEXT UNIQUE,
                keywords TEXT,
                mailing_kwork BOOLEAN DEFAULT TRUE,
                mailing_fl BOOLEAN DEFAULT TRUE,
                mailing_freelancer BOOLEAN DEFAULT TRUE
            );
        '''

        create_index_query = '''
            CREATE INDEX IF NOT EXISTS idx_users_keywords ON users(keywords);
        '''
        try:
            with self.conn.cursor() as cur:
                cur.execute(create_table_query)
                cur.execute(create_index_query)
                print('Таблица users и индекс успешно созданы (или уже существуют).')
        except Exception as e:
            print('Ошибка при создании таблицы или индекса:', e)
            raise e

    def update_user(self, chat_id: str, keywords: str = None, mailing_kwork: bool = None, mailing_fl: bool = None, mailing_freelancer: bool = None):
        fields = []
        values = []
        if keywords is not None:
            fields.append('keywords = %s')
            values.append(keywords)
        if mailing_kwork is not None:
            fields.append('mailing_kwork = %s')
            values.append(mailing_kwork)
        if mailing_fl is not None:
            fields.append('mailing_fl = %s')
            values.append(mailing_fl)
        if mailing_freelancer is not None:
            fields.append('mailing_freelancer = %s')
            values.append(mailing_freelancer)
        if not fields:
            print('Нет полей для обновления для пользователя', chat_id)
            return

        query = 'UPDATE users SET ' + ', '.join(fields) + ' WHERE chat_id = %s;'
        values.append(chat_id)
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, tuple(values))
                print(f'Данные пользователя {chat_id} успешно обновлены.')
        except Exception as e:
            print('Ошибка при обновлении пользователя:', e)
            raise e

    def get_user(self, chat_id: str):
        query = 'SELECT * FROM users WHERE chat_id = %s;'
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (chat_id,))
                user = cur.fetchone()
                return user
        except Exception as e:
            print('Ошибка при получении данных пользователя:', e)
            return None
    def add_user(self, chat_id: str, keywords: str = None, mailing_kwork: bool = True, mailing_fl: bool = True, mailing_freelancer: bool = True):
        query = """
            INSERT INTO users (chat_id, keywords, mailing_kwork, mailing_fl, mailing_freelancer)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (chat_id) DO NOTHING;
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, (chat_id, keywords, mailing_kwork, mailing_fl, mailing_freelancer))
                print(f"Пользователь {chat_id} добавлен (если его ранее не было).")
        except Exception as e:
            print("Ошибка при добавлении пользователя:", e)
            raise e

    def get_users_for_kwork(self):
        query = 'SELECT * FROM users WHERE mailing_kwork = TRUE;'
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                users = cur.fetchall()
                return users
        except Exception as e:
            print('Ошибка при выборке пользователей для Kwork:', e)
            return []

    def get_users_for_fl(self):
        query = 'SELECT * FROM users WHERE mailing_fl = TRUE;'
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                users = cur.fetchall()
                return users
        except Exception as e:
            print('Ошибка при выборке пользователей для FL:', e)
            return []

    def get_users_for_freelancer(self):
        query = 'SELECT * FROM users WHERE mailing_freelancer = TRUE;'
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                users = cur.fetchall()
                return users
        except Exception as e:
            print('Ошибка при выборке пользователей для Freelancer:', e)
            return []
