FROM python:3.12-slim

# Чтобы FAISS и Torch нормально ставились — нужны системные пакеты
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем requirements заранее (для кеша)
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Открываем порт Flask
EXPOSE 5000

# Запуск приложения
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
