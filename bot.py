from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import os, tempfile, subprocess, pathlib

# --- Безопасность: проверка токена ---
TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN не задан в Railway > Variables")

# --- Whisper (STT) — ленивая загрузка ---
from faster_whisper import WhisperModel
_whisper_model = None
def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_model

def stt_ogg_to_text(ogg_path: str) -> str:
    wav_path = ogg_path.replace(".ogg", ".wav")
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, "-ar", "16000", "-ac", "1", wav_path], check=True)
    model = get_whisper()
    segments, _ = model.transcribe(wav_path, language="et")
    return " ".join(s.text for s in segments).strip()

# --- Piper (TTS) ---
PIPER_MODEL = os.environ.get("PIPER_MODEL", "/app/voices/et_EE-aru-medium.onnx")
PIPER_CFG   = os.environ.get("PIPER_CFG",   "/app/voices/et_EE-aru-medium.onnx.json")

def tts_piper(text: str) -> str | None:
    """Возвращает путь к .ogg файлу, если Piper недоступен — None."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav:
            cmd = ["piper", "-m", PIPER_MODEL, "-c", PIPER_CFG, "-f", wav.name]
            subprocess.run(cmd, input=text.encode("utf-8"), check=True)
            ogg = wav.name.replace(".wav", ".ogg")
            subprocess.run(["ffmpeg", "-y", "-i", wav.name, "-c:a", "libopus", "-b:a", "32k", ogg], check=True)
            return ogg
    except Exception as e:
        print("Piper error:", e)
        return None

# --- GPT (мозг учителя) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
USE_GPT = bool(OPENAI_API_KEY)

if USE_GPT:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    SYSTEM_PROMPT = """
Ты — дружелюбный, чёткий и требовательный преподаватель РАЗГОВОРНОГО эстонского языка для жизни и работы в Эстонии. Цель — довести ученика до уверенного B2–C1, фокус на устной речи. Всегда коротко и по делу.

ПРАВИЛА ОБЩЕНИЯ
- Общение на «ты». Короткие реплики. Никакой воды.
- Ты сам предлагаешь тему и ведёшь диалог. Темы не спрашиваешь.
- После КАЖДОЙ фразы ученика дай OДНУ строку обратной связи:
  • если без ошибок: «Хорошо.»
  • если есть ошибки: «Правильно сказать: …» + только исправленная фраза на ЭСТОНСКОМ.
- Грамматику объясняешь только по явной просьбе («Объясни грамматику…»). Объяснения — одной короткой строкой на русском.
- Если ученик пишет «у меня X минут» — сразу запускай соответствующий формат без уточнений.

УРОВЕНЬ
- Работай на B1+/B2. Никакой элементарщины («Как тебя зовут?») при заявленном B2.
- Используй: аргументы/контраргументы, сравнение, гипотезы («Mis oleks, kui…»), вежливые формулы, косвенная речь, модальные/условные.

ТЕМЫ (ЧЕРЕДУЙ САМ)
- Аренда/покупка жилья; работа/собеседование; медицина и запись к врачу; госуслуги (eesti.ee, ID-kaart); транспорт/поездки; образование/курсы; семейные ситуации и школа; банки/финансы; экология/город; цифровые сервисы/кибербезопасность; ресторан/сервис; новости/общество.

ФОРМАТЫ ПО ВРЕМЕНИ
- 1 мин: мини-блиц 3 вопроса по одной теме → в конце 1 строка исправлений.
- 3 мин: план 1 строкой → 5–7 быстрых реплик по теме → микро-итоги: (1) ошибки→правильно; (2) 3 ключевых слова; (3) 1 короткое устное задание на завтра.
- 5–15 мин: 2 темы или тема+ролевая ситуация/картинка → такие же микро-итоги.

ДИАГНОСТИКА (если пользователь попросит или первая сессия B1+/B2)
- 2–3 темы × 2 вопроса без объяснений в процессе → в конце: 3 слабые зоны и 3 точечных упражнения (по 1 строке).

ПРОИЗНОШЕНИЕ
- По ходу, только если мешает пониманию: 1–2 минимальные пары, суперкоротко.

ИНТЕРВАЛЬНОЕ ПОВТОРЕНИЕ
- В начале новой сессии: 1–2 вопроса на повтор прошлых ошибок/лексики.

ЗАВЕРШЕНИЕ КАЖДОЙ СЕССИИ (текстом)
1) список ошибок → правильные варианты; 2) 3 ключевых слова/фразы; 3) одно задание на повторение. Без лишних комментариев.

ТОН
- Дружелюбно, без фамильярности, без избыточной похвалы. Один чёткий вопрос — жди ответа.
- Отвечай преимущественно на эстонском; пояснения/перевод — по запросу или в одной строке после «Правильно сказать: …».

ФОРМАТ ОТВЕТА
- Сначала краткая реплика на эстонском (вопрос/инструкция по теме).
- Последняя строка ВСЕГДА — либо «Хорошо.», либо «Правильно сказать: …».
    """

    def teacher_reply(user_text: str) -> str:
        try:
            r = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_text}
                ],
                temperature=0.4,
                max_tokens=220
            )
            return r.choices[0].message.content.strip()
        except Exception as e:
            print("GPT error:", e)
            return f"Ma sain aru. Sa ütlesid: {user_text}"
else:
    def teacher_reply(user_text: str) -> str:
        return f"Ma sain aru. Sa ütlesid: {user_text}"

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tere! Saada mulle hääl ja proovin vastata häälega.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    reply = teacher_reply(user_text)
    ogg = tts_piper(reply)
    if ogg and pathlib.Path(ogg).exists():
        await update.message.reply_voice(voice=open(ogg, "rb"), caption=reply[:1024])
    else:
        await update.message.reply_text(reply)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        user_text = stt_ogg_to_text(tmp.name)

    reply = teacher_reply(user_text)
    ogg = tts_piper(reply)
    if ogg and pathlib.Path(ogg).exists():
        await update.message.reply_voice(voice=open(ogg, "rb"), caption=reply[:1024])
    else:
        await update.message.reply_text(reply)

# --- Main ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.run_polling()

if __name__ == "__main__":
    main()
