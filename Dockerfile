FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ffmpeg для работы со звуком + curl для скачивания Piper
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*

# зависимости python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Piper (офлайн TTS) + эстонский голос ---
RUN curl -L -o /usr/local/bin/piper https://github.com/rhasspy/piper/releases/download/2023.11.14/piper_linux_x86_64 \
 && chmod +x /usr/local/bin/piper

RUN mkdir -p /app/voices \
 && curl -L -o /app/voices/et_EE-aru-medium.onnx https://github.com/rhasspy/piper/releases/download/2023.11.14/et_EE-aru-medium.onnx \
 && curl -L -o /app/voices/et_EE-aru-medium.onnx.json https://github.com/rhasspy/piper/releases/download/2023.11.14/et_EE-aru-medium.onnx.json

ENV PIPER_MODEL=/app/voices/et_EE-aru-medium.onnx
ENV PIPER_CFG=/app/voices/et_EE-aru-medium.onnx.json

COPY . .

CMD ["python", "bot.py"]
