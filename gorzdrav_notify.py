\#!/usr/bin/env python3
"""
Проверяет портал gorzdrav.spb.ru («Здоровье петербуржца») на появление
свободных талонов к врачу и шлёт уведомление в Telegram, если находит.
 
Настройка — через переменные окружения (см. .env.example) или напрямую
в блоке DEFAULTS ниже. Скрипт работает вечным циклом: раз в
POLL_INTERVAL_SECONDS секунд опрашивает API поликлиники, и если у кого-то
из врачей freeParticipantCount > 0 — шлёт сообщение в Telegram. Чтобы не
спамить одним и тем же уведомлением, запоминает последнее состояние в
файле state.json рядом со скриптом и пишет повторно только при изменении.
 
Быстрый старт — см. README.md.
"""
 
import json
import logging
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
 
BASE_DIR = Path(__file__).parent
 
# --------------------------------------------------------------------------
# .env поддержка (без внешних зависимостей): если рядом со скриптом лежит
# файл .env, подгружаем из него KEY=VALUE в os.environ (не перезаписывая
# уже заданные переменные окружения — они в приоритете).
# --------------------------------------------------------------------------
 
 
def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
 
 
load_dotenv(BASE_DIR / ".env")
 
# --------------------------------------------------------------------------
# Настройки
# --------------------------------------------------------------------------
 
DEFAULTS = {
    "LPU_ID": "180",                 # id поликлиники
    "SPECIALITY_ID": "49",           # id специальности (49 = офтальмолог)
    "POLL_INTERVAL_SECONDS": "300",  # как часто проверять (300 = раз в 5 минут)
}
 
LPU_ID = os.environ.get("LPU_ID", DEFAULTS["LPU_ID"])
SPECIALITY_ID = os.environ.get("SPECIALITY_ID", DEFAULTS["SPECIALITY_ID"])
POLL_INTERVAL_SECONDS = int(
    os.environ.get("POLL_INTERVAL_SECONDS", DEFAULTS["POLL_INTERVAL_SECONDS"])
)
 
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
 
API_URL = (
    f"https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/{LPU_ID}"
    f"/speciality/{SPECIALITY_ID}/doctors"
)
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
 
STATE_FILE = BASE_DIR / "state.json"
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gorzdrav_notify")
 
 
def fetch_doctors():
    """Возвращает список врачей [{id, name, freeParticipantCount}, ...]."""
    req = urllib.request.Request(
        API_URL,
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    # API отдаёт либо список, либо объект result -> список — подстрахуемся
    if isinstance(data, dict) and "result" in data:
        data = data["result"]
    if isinstance(data, dict):
        data = [data]
    return data or []
 
 
def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}
 
 
def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
 
 
def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не заданы — некому слать")
        return
    payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        TELEGRAM_API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        log.info("Сообщение в Telegram отправлено")
    except urllib.error.URLError as e:
        log.error("Не удалось отправить сообщение в Telegram: %s", e)
 
 
def check_once():
    try:
        doctors = fetch_doctors()
    except Exception as e:  # сетевые сбои — не фатальны, просто пробуем в след. раз
        log.warning("Не удалось получить данные с gorzdrav: %s", e)
        return
 
    available = [
        d for d in doctors if int(d.get("freeParticipantCount") or 0) > 0
    ]
 
    state = load_state()
    prev_signature = state.get("signature")
 
    if not available:
        if prev_signature is not None:
            log.info("Талонов больше нет, сбрасываю состояние")
            save_state({})
        else:
            log.info("Талонов нет")
        return
 
    # "подпись" текущего найденного состояния — чтобы не слать одно и то же
    # уведомление повторно, но переслать, если числа изменились
    signature = "|".join(
        f"{d.get('id')}:{d.get('freeParticipantCount')}" for d in available
    )
 
    if signature == prev_signature:
        log.info("Талоны есть, но уведомление уже отправлялось (без изменений)")
        return
 
    lines = [
        f"— {d.get('name')}: {d.get('freeParticipantCount')} мест"
        for d in available
    ]
    message = (
        "Появились талоны к врачу (поликлиника "
        f"{LPU_ID}, специальность {SPECIALITY_ID}):\n"
        + "\n".join(lines)
        + "\n\nЗаписывайся: https://gorzdrav.spb.ru/service-free-schedule"
    )
    log.info("Найдены свободные талоны, отправляю уведомление")
    send_telegram_message(message)
    save_state({"signature": signature})
 
 
def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error(
            "Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
            "(переменные окружения или файл .env рядом со скриптом)"
        )
        return
 
    # Внутри GitHub Actions каждый запуск — отдельная свежая машина без
    # памяти о предыдущем запуске: делаем одну проверку и выходим,
    # расписание (cron) само вызовет скрипт заново.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        log.info(
            "Режим GitHub Actions: разовая проверка (lpu=%s speciality=%s)",
            LPU_ID,
            SPECIALITY_ID,
        )
        check_once()
        return
 
    log.info(
        "Старт: lpu=%s speciality=%s интервал=%sс",
        LPU_ID,
        SPECIALITY_ID,
        POLL_INTERVAL_SECONDS,
    )
    while True:
        check_once()
        time.sleep(POLL_INTERVAL_SECONDS)
 
 
if __name__ == "__main__":
    main()
 
