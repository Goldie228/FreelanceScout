from .fl_parser import FlParser
from .kwork_parser import KworkParser
from .freelancer_parser import FreelancerParser

import time
from multiprocessing import Process, Event
import redis
import signal
import os
import psutil

class ApplicationParser:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.shutdown_event = Event()
        self.processes = []
        self._is_running = False

    def run_parsers(self):
        if self._is_running:
            return
            
        self._is_running = True
        try:
            self.processes = [
                Process(target=self._run_parser, args=(FlParser, self.redis_client)),
                Process(target=self._run_parser, args=(KworkParser, self.redis_client)),
                Process(target=self._run_parser, args=(FreelancerParser, self.redis_client))
            ]
            
            for i, proc in enumerate(self.processes):
                proc.start()
                names = ["fl_parser", "kwork_parser", "freelancer_parser"]
                print(f"Запущен процесс: {names[i]} (PID: {proc.pid})")
            
            for proc in self.processes:
                proc.join()
                
        except Exception as e:
            print(f"Ошибка в парсерах: {e}")
        finally:
            self._is_running = False

    def _run_parser(self, parser_class, redis_client):
        """Внутренний метод для запуска парсера"""
        parser = parser_class(redis_client)
        while not self.shutdown_event.is_set():
            try:
                parser.run()
                time.sleep(1)
            except Exception as e:
                print(f"Ошибка в парсере: {e}")

    def kill_processes(self):
        """Завершение всех процессов"""
        print("Завершение процессов парсеров...")
        self.shutdown_event.set()
        
        # Даем время на корректное завершение
        time.sleep(1)
        
        # Принудительно завершаем оставшиеся процессы
        for proc in self.processes:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=1)
                
                if proc.is_alive():
                    print(f"Принудительное завершение процесса {proc.pid}")
                    try:
                        parent = psutil.Process(proc.pid)
                        for child in parent.children(recursive=True):
                            child.kill()
                        parent.kill()
                    except Exception as e:
                        print(f"Ошибка при завершении: {e}")
