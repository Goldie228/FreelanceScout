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
            print('Подключение к базе данных закрыто.')

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


if __name__ == '__main__':
    db = Database()
    db.connect()

    db.disconnect()
