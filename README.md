# gorzdrav-notify

Маленький скрипт без внешних зависимостей: опрашивает API портала
[gorzdrav.spb.ru](https://gorzdrav.spb.ru) («Здоровье петербуржца») и шлёт
сообщение в Telegram, как только у выбранного врача появляются свободные
талоны. По умолчанию настроен на офтальмолога в поликлинике №180, но
специальность и поликлинику легко поменять.

Не спамит: пока набор свободных врачей/количество мест не изменится,
повторные уведомления не шлются.

## Быстрый старт

```bash
git clone <адрес-твоего-репозитория>
cd gorzdrav-notify
cp .env.example .env
# впиши в .env свой TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID
python3 gorzdrav_notify.py
```

Зависимостей нет — только стандартная библиотека Python 3.

## Получить токен бота

1. В Telegram написать [@BotFather](https://t.me/botfather), команда `/newbot`.
2. Придумать имя и юзернейм бота.
3. BotFather пришлёт токен вида `123456:ABC-DEF...` — это `TELEGRAM_BOT_TOKEN`.

## Узнать свой chat_id

Проще всего — написать [@userinfobot](https://t.me/userinfobot), он сразу
пришлёт число. Это и есть `TELEGRAM_CHAT_ID`.

Либо вручную: написать что-нибудь своему боту, затем открыть в браузере
`https://api.telegram.org/bot<ТВОЙ_ТОКЕН>/getUpdates` и найти
`"chat":{"id":...}`.

## Проверка связи

```bash
curl -s "https://api.telegram.org/bot<ТВОЙ_ТОКЕН>/sendMessage" \
  -d "chat_id=<ТВОЙ_CHAT_ID>&text=Тест"
```

Если пришло сообщение в Telegram и в ответе `"ok":true` — всё настроено верно.

## Другая специальность / поликлиника

id можно посмотреть через тот же API:

```bash
# список специальностей и их id для конкретной поликлиники
curl -s "https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/<LPU_ID>/specialties"
```

Поменять в `.env`:

```
LPU_ID=180
SPECIALITY_ID=49
```

## Запуск как systemd-сервис (рекомендуется для VPS)

Создать `/etc/systemd/system/gorzdrav-notify.service`:

```ini
[Unit]
Description=gorzdrav.spb.ru ticket notifier
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/gorzdrav-notify
ExecStart=/usr/bin/python3 /path/to/gorzdrav-notify/gorzdrav_notify.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gorzdrav-notify
sudo systemctl status gorzdrav-notify   # проверить, что запустился
journalctl -u gorzdrav-notify -f        # смотреть логи в реальном времени
```

## Файлы

- `gorzdrav_notify.py` — сам скрипт
- `.env.example` — шаблон настроек, скопировать в `.env` (не коммитить!)
- `.gitignore` — исключает `.env` и `state.json` из репозитория
