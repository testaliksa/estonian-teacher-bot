FROM python:3.11-slim

# чтобы логи сразу печатались
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ставим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# копируем код
COPY . .

# старт
CMD ["python", "bot.py"]
