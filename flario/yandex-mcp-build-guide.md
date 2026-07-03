# Yandex MCP — как собрать (промт + инструкция)

Готовый рецепт, как сделать MCP-сервер для **Яндекс Почты, Календаря и Диска**,
работающий в трёх режимах: локально в Claude Code (stdio), удалённо в Claude
Cowork (Streamable HTTP + OAuth) и как REST-API для n8n. Все личные данные
заменены плейсхолдерами — подставьте свои.

---

## Часть 1. Промт для Claude Code

Скопируйте в Claude Code в пустой папке — он соберёт проект. Промт уже учитывает
все грабли (см. Часть 3), поэтому сразу указывает рабочие библиотеки.

````text
Сделай MCP-сервер на Node.js + TypeScript для Яндекс Почты, Календаря и Диска.

СТЕК (важно — именно эти библиотеки, проверено):
- @modelcontextprotocol/sdk — MCP
- imapflow — IMAP (НЕ node-imap: он не отдаёт uid/flags на новых Node)
- mailparser — разбор писем; turndown — HTML→markdown в теле
- nodemailer — SMTP (порт 465 SSL с fallback на 587 STARTTLS)
- axios + xml2js — CalDAV (caldav.yandex.ru) и Яндекс Диск REST (cloud-api.yandex.net)
- rrule + luxon — разворачивание повторяющихся событий с таймзоной
- zod — валидация; vitest — тесты

АРХИТЕКТУРА:
- src/config.ts — чтение конфига из ~/.config/yandex-mcp/config.json ИЛИ из env
  (YANDEX_EMAIL/…); поддержка нескольких аккаунтов (accounts map) и выбора
  через --account / YANDEX_MCP_ACCOUNT; zod-валидация.
- src/services/{mail,calendar,disk}.ts — чистая логика (без MCP).
- src/tools/*.tools.ts — регистрация MCP-инструментов (zod inputSchema + handler).
- src/server.ts — фабрика McpServer (tools + resources + prompts).
- src/index.ts — CLI: serve (stdio) | http | setup | install | doctor | ...

ИНСТРУМЕНТЫ (≈30):
- Почта: mail_folders, mail_list, mail_search (фильтры from/subject/unread/since),
  mail_read (вложения списком; тело: text, иначе HTML→markdown),
  mail_attachment_save, mail_mark, mail_mark_all_read, mail_move, mail_reply
  (правильные In-Reply-To/References), mail_send.
- Календарь (CalDAV, Basic auth email:app_password): calendar_list, calendar_events
  (period), calendar_today, calendar_next, calendar_create (поддержи all_day, rrule,
  attendees, reminder_minutes), calendar_update (в т.ч. правка ОДНОГО вхождения
  через RECURRENCE-ID), calendar_delete. Мультикалендарь: discovery всех календарей,
  параметр calendar (id/name), агрегация по всем.
- Диск (REST, заголовок Authorization: OAuth <token>): disk_list (с пагинацией),
  disk_info (квота), disk_mkdir, disk_delete (запрети удаление корня "/"),
  disk_share/unshare (публичная ссылка), disk_move, disk_copy (async-операции 202 —
  опрашивай статус), disk_upload, disk_download, disk_trash_list/restore/empty.

ФОРМАТ ОТВЕТОВ: всегда JSON. Успех { ok: true, ...data }; ошибка
{ ok: false, error, code }. Коды: AUTH_ERROR, NOT_FOUND, NETWORK_ERROR,
PARSE_ERROR, CONFIG_ERROR. Таймаут сетевых запросов 30 c; retry/backoff на 429/5xx.

CLI:
- setup — интерактивно спросить email + пароли приложений (почта, календарь) +
  OAuth-токен Диска, сохранить в ~/.config/yandex-mcp/config.json, проверить связь.
- install — claude mcp add yandex-mcp -- node <abs>/dist/index.js (найди claude.exe
  на Windows, если нет в PATH).
- doctor — read-only прогон по всем сервисам.
- secure/unsecure — перенести секреты в хранилище ОС (@napi-rs/keyring) и обратно.

БЕЗОПАСНОСТЬ: креды только локально; никакой телеметрии; в логи (stderr) — только
технические события без содержимого писем/файлов и без паролей/токенов.

ТЕСТЫ: vitest на чистые функции — парсер iCalendar, разворачивание RRULE/EXDATE
с таймзоной, классификацию ошибок, сборку ICS, reply-заголовки.
````

После базовой версии можно вторым промтом попросить **удалённый режим** (см. Часть 4).

---

## Часть 2. Что нужно от пользователя (его данные)

1. **Email Яндекса** и **2 пароля приложений** (Яндекс ID → Безопасность → Пароли
   приложений): один с доступом «Почта (IMAP/SMTP)», один «Календарь (CalDAV)».
   Это НЕ основной пароль.
2. **OAuth-токен Яндекс Диска** — проще всего через Полигон Диска
   (yandex.ru/dev/disk/poligon) или своё OAuth-приложение (oauth.yandex.ru) с правами
   `cloud_api:disk.read/write/info`.

Конфиг `~/.config/yandex-mcp/config.json`:
```json
{
  "email": "you@yandex.ru",
  "mail_password": "<app-password-mail>",
  "calendar_password": "<app-password-calendar>",
  "disk_token": "<disk-oauth-token>"
}
```

---

## Часть 3. Грабли, которые мы прошли (сэкономит дни)

1. **node-imap мёртв.** На современном Node он не эмитит события `attributes`/`end`
   у сообщений → чтение почты молча пустое. Бери **imapflow**.
2. **CalDAV у Яндекса:**
   - `calendar-home-set` на principal отдаёт 404 — используй конвенциональный путь
     `/calendars/<email>/` (PROPFIND Depth:1 перечисляет все календари).
   - **Игнорирует серверный `<C:expand>`** — повторяющиеся события разворачивай сам
     (rrule + luxon, таймзона Europe/Moscow по умолчанию).
   - **Игнорирует `<C:prop-filter name="UID">`** и возвращает ВСЕ события — поэтому
     для удаления/правки матчи UID на клиенте, иначе удалишь чужое событие.
   - Удаление одного вхождения серии = добавить в .ics VEVENT с `RECURRENCE-ID`.
3. **xml2js** не оборачивает корневой элемент в массив: `x.multistatus.response`,
   а не `x.multistatus[0].response`.
4. **Events с участниками** Яндекс реально рассылает приглашения (iMIP) — на
   несуществующий адрес прилетит отбойник. Тестируй на своём адресе.
5. **DELETE несуществующего ресурса** Диска/CalDAV Яндекс отвечает 2xx — проверяй
   существование (GET) перед удалением, чтобы корректно вернуть NOT_FOUND.
6. **SMTP** часто заблокирован сетью/VPS (порты 25/465/587). Сделай fallback
   465→587 и настраиваемый smtp_host; отдавай понятную ошибку.
7. **Большие файлы Диска:** не ставь таймаут 30 c на сам трансфер (timeout: 0),
   оборачивай upload/download в retry с пере-получением ссылки.

---

## Часть 4. Удалённый режим (Cowork) и REST (n8n)

**Cowork принимает только удалённые MCP по OAuth** (custom connector). Локальный
stdio там не виден. Поэтому для Cowork нужен HTTP-режим:

- `express` + `StreamableHTTPServerTransport` (stateful, сессии по Mcp-Session-Id),
  эндпоинт `POST /mcp`, `/health` без авторизации.
- **OAuth 2.1 + Dynamic Client Registration + PKCE** — бери из SDK `mcpAuthRouter`
  + `requireBearerAuth` + свой `OAuthServerProvider`.
  - Сделай провайдера **stateless**: client_id, authorization code и токены —
    подписанные JWT (HS256), секрет = HMAC от пароля владельца. Тогда перезапуски
    сервера НЕ рвут сессии (иначе in-memory токены теряются на каждом деплое).
  - Доступ к выдаче токена закрой **паролем владельца** на странице согласия
    (env OAUTH_OWNER_PASSWORD) — DCR открыт, но токен без пароля не выдаётся.
- **За прокси (Railway/Cloudflare) обязательно `app.set("trust proxy", 1)`** —
  иначе express-rate-limit в OAuth-роутере сыплет ошибками и режет запросы.
- В Cowork: Customize → Connectors → Add custom connector → URL `https://<host>/mcp`,
  OAuth Client ID/Secret — пусто (сработает DCR) → на согласии ввести OWNER_PASSWORD.

**REST-слой для n8n** (MCP по JSON-RPC/SSE неудобен для HTTP Request node):
- `POST /api/<tool>` — JSON-аргументы в теле, ответ `{ ok, ... }`. Тот же bearer
  (env MCP_AUTH_TOKEN), параллельно с OAuth. `GET /api/tools` — список.
- В n8n: HTTP Request node, POST, Header `Authorization: Bearer <token>`,
  Body JSON. Пример: `POST /api/calendar_events`
  `{"date_from":"2026-06-01","date_to":"2026-06-07","calendar":"<имя>"}`.

**Деплой (Railway):**
- `railway.json`: `startCommand: node dist/index.js http`, healthcheck `/health`.
- Креды и `OAUTH_OWNER_PASSWORD`/`MCP_AUTH_TOKEN` — env-переменные сервиса
  (задаёт владелец, не публикуй их). `railway up` → `railway domain`.
- Env для удалённого режима: `OAUTH_OWNER_PASSWORD`, `MCP_AUTH_TOKEN` (опц., для REST),
  `YANDEX_EMAIL`, `YANDEX_MAIL_PASSWORD`, `YANDEX_CALENDAR_PASSWORD`,
  `YANDEX_DISK_TOKEN`, `YANDEX_TIMEZONE`. PUBLIC_URL берётся из `RAILWAY_PUBLIC_DOMAIN`.

---

## Эндпоинты (итог)
- `POST /mcp` — MCP (Streamable HTTP, OAuth) → для Cowork/Claude.
- `POST /api/<tool>` — REST (Bearer) → для n8n/скриптов.
- `GET /health` — проверка живости.
- Локально: `node dist/index.js` (stdio) → для Claude Code.
