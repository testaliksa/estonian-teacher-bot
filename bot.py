from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os, tempfile, subprocess, pathlib

# --- Безоп. проверка токена ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан в Railway → Variables")

# --- Whisper (STT) — ЛЕНИВАЯ загрузка ---
from faster_whisper import WhisperModel
_whisper_model = None
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        # tiny = минимум памяти, достаточно для et
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model

def stt_ogg_to_text(ogg_path: str) -> str:
    wav_path = ogg_path.replace(".ogg", ".wav")
    subprocess.run(["ffmpeg","-y","-i",ogg_path,"-ar","16000","-ac","1",wav_path], check=True)
    model = get_whisper()
    segments, _ = model.transcribe(wav_path, language="et")
    return " ".join(s.text for s in segments).strip()

# --- Piper (TTS) — с fallback на текст ---
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/app/voices/et_EE-aru-medium.onnx")
PIPER_CFG   = os.environ.get("PIPER_CFG",   "/app/voices/et_EE-aru-medium.onnx.json")

def tts_piper(text: str) -> str | None:
    """Возвращает путь к .ogg или None, если пипер недоступен."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav:
            cmd = ["piper","-m",PIPER_MODEL,"-c",PIPER_CFG,"-f",wav.name]
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            ogg = wav.name.replace(".wav",".ogg")
            subprocess.run(["ffmpeg","-y","-i",wav.name,"-c:a","libopus","-b:a","32k",ogg], check=True)
            return ogg
    except Exception as e:
        print("Piper error:", e)
        return None

# --- Простой «мозг» без GPT (для теста стабильности) ---
def teacher_reply(user_text: str) -> str:
    # пока просто подтверждение; GPT добавим после успешного деплоя
    return f"Ma sain aru. Sa ütlesid: {user_text}"

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tere! Saada mulle hääl ja proovin vastata häälega.")

# текст
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    reply = teacher_reply(user_text)
    ogg = tts_piper(reply)
    if ogg and pathlib.Path(ogg).exists():
        await update.message.reply_voice(voice=open(ogg,"rb"), caption=reply[:1024])
    else:
        await update.message.reply_text(reply)

# голос
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        user_text = stt_ogg_to_text(tmp.name)

    reply = teacher_reply(user_text)
    ogg = tts_piper(reply)
    if ogg and pathlib.Path(ogg).exists():
        await update.message.reply_voice(voice=open(ogg,"rb"), caption=reply[:1024])
    else:
        await update.message.reply_text(reply)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()
