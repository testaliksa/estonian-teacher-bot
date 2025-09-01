from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os, tempfile, subprocess

# --- Whisper (распознавание речи) ---
from faster_whisper import WhisperModel
whisper = WhisperModel("small", device="cpu", compute_type="int8")

def stt_ogg_to_text(ogg_path: str) -> str:
    """Конвертирует .ogg (opus) -> .wav и распознаёт эстонский текст."""
    wav_path = ogg_path.replace(".ogg", ".wav")
    # ffmpeg конвертирует в 16 кГц mono (нужно для Whisper)
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path], check=True)
    segments, _ = whisper.transcribe(wav_path, language="et")
    return " ".join(s.text for s in segments).strip()

# --- Токен Телеграма ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tere! Olen sinu eesti keele õpetaja. Räägi mulle midagi (saada hääl).")

# Текст -> эхо (пока)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Sa ütlesid (tekst): {update.message.text}")

# ГОЛОС -> распознаём и возвращаем текст
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        user_text = stt_ogg_to_text(tmp.name)

    # Пока просто подтверждаем распознавание. На следующем шаге добавим «учителя».
    await update.message.reply_text(f"Sa ütlesid (hääl): {user_text}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))                 # <- новый обработчик
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))       # текст как раньше
    app.run_polling()

if __name__ == "__main__":
    main()
