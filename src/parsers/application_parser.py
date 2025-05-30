import time
from multiprocessing import Process
import redis

from .fl_parser import FlParser
from .kwork_parser import KworkParser
from .freelancer_parser import FreelancerParser


class ApplicationParser:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def run_parsers(self):
        processes = [
            Process(target=self.run_fl_parser, args=(self.redis_client,), name="fl_parser"),
            Process(target=self.run_kwork_parser, args=(self.redis_client,), name="kwork_parser"),
            Process(target=self.run_freelancer_parser, args=(self.redis_client,), name="freelancer_parser")
        ]

        for proc in processes:
            proc.start()
            print(f"Запущен процесс: {proc.name} (PID: {proc.pid})")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Получен сигнал завершения. Останавливаем процессы...")
            for proc in processes:
                proc.terminate()
            for proc in processes:
                proc.join()
            print("Все процессы завершены.")

    @staticmethod
    def run_fl_parser(redis_client):
        parser = FlParser(redis_client)
        parser.run()

    @staticmethod
    def run_kwork_parser(redis_client):
        parser = KworkParser(redis_client)
        parser.run()

    @staticmethod
    def run_freelancer_parser(redis_client):
        parser = FreelancerParser(redis_client)
        parser.run()


if __name__ == "__main__":
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    app_parser = ApplicationParser(redis_client)
    app_parser.run_parsers()
