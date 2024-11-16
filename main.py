#!/usr/bin/env python3
import argparse
import os
from datetime import datetime, timedelta
import subprocess
from pathlib import Path
import threading
import time
import re

class Task:
    def __init__(self, title: str, due_date: str = None, priority: str = "medium", category: str = "personal"):
        self.title = title
        self.due_date = due_date
        self.priority = priority
        self.category = category
        self.completed = False
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def to_string(self) -> str:
        """Преобразует задачу в строку для хранения"""
        completed_mark = "+" if self.completed else "-"
        due_str = f" due:{self.due_date}" if self.due_date else ""
        return f"{completed_mark}|{self.created_at}|{self.priority}|{self.category}|{self.title}{due_str}"

    @classmethod
    def from_string(cls, line: str) -> 'Task':
        """Создает задачу из строки"""
        try:
            # Основные поля разделены символом |
            completed_mark, created_at, priority, category, *title_parts = line.strip().split('|')
            title_full = '|'.join(title_parts)  # Восстанавливаем title, если в нем были |
            
            # Извлекаем срок выполнения, если есть
            due_match = re.search(r'due:(\S+)', title_full)
            if due_match:
                title = title_full[:due_match.start()].strip()
                due_date = due_match.group(1)
            else:
                title = title_full.strip()
                due_date = None

            task = cls(title)
            task.due_date = due_date
            task.priority = priority
            task.category = category
            task.completed = completed_mark == "+"
            task.created_at = created_at
            return task
        except Exception as e:
            print(f"Ошибка при чтении задачи: {line}")
            print(f"Причина: {e}")
            return None

class QuickDo:
    def __init__(self):
        self.config_dir = Path.home() / ".quickdo"
        self.tasks_file = self.config_dir / "tasks.txt"
        self.reminders_file = self.config_dir / "reminders.txt"
        self.setup_files()
        self.tasks = self.load_tasks()

    def setup_files(self):
        """Создает необходимые директории и файлы"""
        self.config_dir.mkdir(exist_ok=True)
        self.tasks_file.touch(exist_ok=True)
        self.reminders_file.touch(exist_ok=True)

    def load_tasks(self) -> list:
        """Загружает задачи из файла"""
        tasks = []
        if self.tasks_file.exists():
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        task = Task.from_string(line)
                        if task:
                            tasks.append(task)
        return tasks

    def save_tasks(self):
        """Сохраняет задачи в файл"""
        with open(self.tasks_file, 'w', encoding='utf-8') as f:
            for task in self.tasks:
                f.write(task.to_string() + '\n')

    def add_task(self, title: str, due_date: str = None, priority: str = "medium", category: str = "personal"):
        """Добавляет новую задачу"""
        task = Task(title, due_date, priority, category)
        self.tasks.append(task)
        self.save_tasks()
        print(f"[✔] Задача добавлена: \"{title}\" [срок: {due_date or 'не указан'}, приоритет: {priority}]")

    def list_tasks(self, show_completed: bool = False):
        """Выводит список задач"""
        if not self.tasks:
            print("Нет активных задач")
            return

        print("🕒 Текущие задачи:")
        for i, task in enumerate(self.tasks, 1):
            if task.completed and not show_completed:
                continue
            
            priority_symbols = {"high": "❗", "medium": "▪", "low": "·"}
            priority_symbol = priority_symbols.get(task.priority, "▪")
            status = "✓" if task.completed else "-"
            due_str = f" [{task.due_date}]" if task.due_date else ""
            category_str = f"[{task.category}]"
            
            print(f"{i}. [{status}] {priority_symbol} {task.title} {category_str}{due_str}")

    def complete_task(self, task_id: int):
        """Отмечает задачу как выполненную"""
        if 1 <= task_id <= len(self.tasks):
            task = self.tasks[task_id - 1]
            task.completed = True
            self.save_tasks()
            print(f"[✔] Задача \"{task.title}\" помечена как выполненная")
        else:
            print("Неверный номер задачи")

    def format_reminder(self, message: str, time_str: str) -> str:
        """Форматирует напоминание для сохранения"""
        return f"{time_str}|{message}"

    def save_reminder(self, message: str, time_str: str):
        """Сохраняет напоминание в файл"""
        with open(self.reminders_file, 'a', encoding='utf-8') as f:
            f.write(self.format_reminder(message, time_str) + '\n')

    def notify(self, message: str):
        """Отправляет уведомление"""
        try:
            subprocess.run(["notify-send", "QuickDo", message])
        except FileNotFoundError:
            print(f"🔔 {message}")

    def remind(self, message: str, delay: str):
        """Устанавливает напоминание"""
        def parse_delay(delay_str: str) -> int:
            unit = delay_str[-1].lower()
            value = int(delay_str[:-1])
            units = {'m': 60, 'h': 3600, 'd': 86400}
            return value * units.get(unit, 60)

        seconds = parse_delay(delay)
        reminder_time = datetime.now() + timedelta(seconds=seconds)
        time_str = reminder_time.strftime("%Y-%m-%d %H:%M")
        
        def reminder_task():
            time.sleep(seconds)
            self.notify(message)

        threading.Thread(target=reminder_task, daemon=True).start()
        self.save_reminder(message, time_str)
        print(f"[✔] Напоминание установлено: \"{message}\" (через {delay})")

    def report(self, period: str = "week"):
        """Генерирует отчет по задачам"""
        now = datetime.now()
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "day":
            start_date = now - timedelta(days=1)
        else:
            print("Неподдерживаемый период отчёта")
            return

        completed = 0
        remaining = 0
        categories = {}

        for task in self.tasks:
            task_date = datetime.strptime(task.created_at, "%Y-%m-%d %H:%M")
            if task_date >= start_date:
                if task.completed:
                    completed += 1
                else:
                    remaining += 1
                
                categories[task.category] = categories.get(task.category, 0) + 1

        print(f"📊 Отчёт за {period}:")
        print(f"Завершено: {completed} задач")
        print(f"Осталось: {remaining} задач")
        print("\nПо категориям:")
        for category, count in categories.items():
            print(f"- {category}: {count} задач")

def main():
    parser = argparse.ArgumentParser(description="QuickDo - простое управление задачами")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Add task
    add_parser = subparsers.add_parser("add", help="Добавить задачу")
    add_parser.add_argument("title", help="Название задачи")
    add_parser.add_argument("--due", help="Срок выполнения (YYYY-MM-DD)")
    add_parser.add_argument("--priority", choices=["low", "medium", "high"], default="medium", help="Приоритет")
    add_parser.add_argument("--category", default="personal", help="Категория")

    # List tasks
    list_parser = subparsers.add_parser("list", help="Показать задачи")
    list_parser.add_argument("--all", action="store_true", help="Показать завершённые задачи")

    # Complete task
    complete_parser = subparsers.add_parser("complete", help="Отметить задачу как выполненную")
    complete_parser.add_argument("task_id", type=int, help="Номер задачи")

    # Remind
    remind_parser = subparsers.add_parser("remind", help="Установить напоминание")
    remind_parser.add_argument("message", help="Текст напоминания")
    remind_parser.add_argument("--in", dest="delay", help="Через какое время (например: 2h, 30m, 1d)")

    # Report
    report_parser = subparsers.add_parser("report", help="Показать отчёт")
    report_parser.add_argument("period", choices=["day", "week"], default="week", help="Период отчёта")

    args = parser.parse_args()
    quickdo = QuickDo()

    if args.command == "add":
        quickdo.add_task(args.title, args.due, args.priority, args.category)
    elif args.command == "list":
        quickdo.list_tasks(args.all)
    elif args.command == "complete":
        quickdo.complete_task(args.task_id)
    elif args.command == "remind":
        quickdo.remind(args.message, args.delay)
    elif args.command == "report":
        quickdo.report(args.period)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
