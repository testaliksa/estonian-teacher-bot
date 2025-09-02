from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os, tempfile, subprocess

# --- Whisper (STT) ---
from faster_whisper import WhisperModel
whisper = WhisperModel("tiny", device="cpu", compute_type="int8")

def stt_ogg_to_text(ogg_path: str) -> str:
    wav_path = ogg_path.replace(".ogg", ".wav")
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path], check=True)
    segments, _ = whisper.transcribe(wav_path, language="et")
    return " ".join(s.text for s in segments).strip()

# --- Piper (TTS) ---
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/app/voices/et_EE-aru-medium.onnx")
PIPER_CFG   = os.environ.get("PIPER_CFG",   "/app/voices/et_EE-aru-medium.onnx.json")

def tts_piper(text: str, out_wav: str):
    cmd = ["piper", "-m", PIPER_MODEL, "-c", PIPER_CFG, "-f", out_wav]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True)

# --- GPT (мозг) ---
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Ты — дружелюбный преподаватель разговорного эстонского языка.
Правила:
- Диалог на эстонском.
- После каждой фразы ученика дай 1 строку обратной связи:
  если всё правильно → "Хорошо."
  если ошибка → "Правильно сказать: …"
"""

def ask_gpt(user_text: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":user_text}
        ],
        max_tokens=200
    )
    return resp.choices[0].message.content.strip()

# --- Telegram token ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tere! Olen sinu eesti keele õpetaja. Räägi mulle midagi (saada hääl).")

# текстовые сообщения
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    bot_reply = ask_gpt(user_text)
    await send_voice(update, bot_reply)

# голосовые сообщения
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        user_text = stt_ogg_to_text(tmp.name)

    bot_reply = ask_gpt(user_text)
    await send_voice(update, f"Sa ütlesid: {user_text}\n{bot_reply}")

# утилита: озвучка + ответ
async def send_voice(update, text: str):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav:
        tts_piper(text, wav.name)
        ogg = wav.name.replace(".wav", ".ogg")
        subprocess.run(["ffmpeg","-y","-i",wav.name,"-c:a","libopus","-b:a","32k",ogg], check=True)
    await update.message.reply_voice(voice=open(ogg,"rb"), caption=text[:1024])

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()
