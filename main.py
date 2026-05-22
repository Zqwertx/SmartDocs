import os
import shutil
import time
from datetime import datetime
import pdfplumber
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# --- НАСТРОЙКИ ПУТЕЙ ---
WATCH_DIR = "./watch_folder"
TARGET_DIR = "./sorted_docs"
DB_PATH = "sqlite:///database/smartdocs.db"

# --- БАЗА ДАННЫХ (SQLAlchemy) ---
Base = declarative_base()
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)


class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    original_name = Column(String(255))
    new_path = Column(String(255))
    content_text = Column(Text)
    processed_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


# --- ЛОГИКА ОБРАБОТКИ ФАЙЛОВ ---
class DocumentProcessor:
    @staticmethod
    def extract_text(file_path):
        """Извлекает текст из PDF-файла."""
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "".join([page.extract_text() or "" for page in pdf.pages])
                return text.strip()
        except Exception as e:
            print(f"❌ Ошибка чтения PDF {file_path}: {e}")
            return ""

    @staticmethod
    def organize_file(file_path, text):
        """Определяет категорию и перемещает файл."""
        # Простейший классификатор по ключевым словам
        content_lower = text.lower()
        if "инвойс" in content_lower or "invoice" in content_lower or "счет" in content_lower:
            category = "Invoices"
        elif "договор" in content_lower or "contract" in content_lower:
            category = "Contracts"
        elif "паспорт" in content_lower or "passport" in content_lower:
            category = "Personal_ID"
        else:
            category = "Unsorted"

        # Создаем папку категории
        dest_dir = os.path.join(TARGET_DIR, category)
        os.makedirs(dest_dir, exist_ok=True)

        # Перемещаем файл
        file_name = os.path.basename(file_path)
        dest_path = os.path.join(dest_dir, file_name)
        shutil.move(file_path, dest_path)
        return dest_path

    @classmethod
    def process(cls, file_path):
        """Главный конвейер обработки."""
        print(f"📦 Обнаружен новый файл: {file_path}")
        time.sleep(1)  # Ждем секунду, чтобы файл успел полностью записаться на диск

        # 1. Извлекаем текст
        text = cls.extract_text(file_path)

        # 2. Перемещаем и сортируем
        new_path = cls.organize_file(file_path, text)

        # 3. Сохраняем в БД
        session = Session()
        doc = Document(
            original_name=os.path.basename(file_path),
            new_path=new_path,
            content_text=text
        )
        session.add(doc)
        session.commit()
        session.close()
        print(f"✅ Файл успешно обработан и перемещен в: {new_path}")


# --- МОНИТОРИНГ ПАПКИ (Watchdog) ---
class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            DocumentProcessor.process(event.src_path)


if __name__ == "__main__":
    # Создаем базовые папки, если их нет
    os.makedirs(WATCH_DIR, exist_ok=True)
    os.makedirs(TARGET_DIR, exist_ok=True)
    os.makedirs("./database", exist_ok=True)

    print(f"🤖 SmartDocs запущен. Положите PDF-файл в папку '{WATCH_DIR}'...")

    event_handler = Handler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIR, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Мониторинг остановлен.")
    observer.join()
