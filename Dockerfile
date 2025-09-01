FROM python:3.11-slim

# чтобы логи сразу печатались
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем ffmpeg для работы с аудио
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# копируем код
COPY . .

# старт
CMD ["python", "bot.py"]
