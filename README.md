# Urban Tickets Bot (aiogram v3, Postgres)

Телеграм‑бот для продажи билетов «Urban» 

---

## Возможности

* `/start` → приветствие + кнопка **«Купить билет — 2 500 ₽»**.
* Показ **активных реквизитов** в код‑блоке + кнопки **«Оплатил» / «Назад»**.
* «Оплатил» → запрос скриншота + отправка образца `assets/example_screenshot.png`.
* При фото/документе → запись в БД: `user_id`, `requisites_id`, `amount`, `file_id`, `file_type`, `batch_counter (1..20)`, `ticket_full_name` (ФИО для конкретного билета), `created_at`.
* Авто‑инкремент `usage_count` у активных реквизитов и **ротация каждые 20 оплат** (переключение — атомарно, по `order_idx`, циклически).
* (Опционально) уведомления в админ‑чат с инлайн‑кнопками **Подтвердить / Отклонить**.
* Админ‑команды: `/stats`, `/listreq`, `/rotate`, `/setactive <id>`, `/addreq bank;holder;account;comment;order_idx`, `/payments [N]`, `/clear_payments`, `/export_excel`.

> **Важно про ФИО:** у одного Telegram‑аккаунта может быть несколько билетов на разные имена, поэтому ФИО не «прибито» к пользователю. Поле **`ticket_full_name`** хранится **в платежах** и берётся в первую очередь из подписи к сообщению со скриншотом (caption). Если подпись пуста — подставляется `first_name + last_name` из профиля TG.

---

## Стек

* Python **3.11**
* **PostgreSQL** 14+ (рекомендуется 16)
* **Redis** 7+ (для FSM; можно без него — будет in‑memory)
* aiogram v3, SQLAlchemy 2.x, asyncpg, openpyxl

> Для aiogram ≥ 3.7 используем `DefaultBotProperties(parse_mode=ParseMode.HTML)` вместо `parse_mode=` в конструкторе `Bot`.

---

## Структура БД и ротация

### Таблицы (см. миграции)

* `users(id, tg_id, username, full_name, created_at)` — `full_name` здесь справочно (из TG), **не** билетное ФИО.
* `requisites(id, bank, holder, account, comment, active, usage_count, order_idx)`
* `payments(id, user_id, requisites_id, amount, file_id, file_type, batch_counter, status, ticket_full_name, created_at)`

  * `status ∈ {'pending','confirmed','rejected'}`
* (резерв) `fsm_states` — если захотите хранить FSM в БД.

### Логика ротации

* В каждый момент активен **один** набор (`requisites.active = true`).
* Каждая «оплата» (получен скрин) → `usage_count++` у активных реквизитов.
* При `usage_count = 20`:

  1. текущие — `active=false`;
  2. включаются **следующие** по `order_idx` (циклически);
  3. у новых `usage_count = 0`.
* Если набор один — переключения не будет (счётчик продолжит расти).

---

## Переменные окружения (`.env`)

```env
BOT_TOKEN=xxxxxxxxx:yyyyyyyyyyyyyyyyyyyyyyyyyyyyxxxxx
DATABASE_URL=postgresql+asyncpg://postgres:root@localhost:5432/urban_tickets
REDIS_URL=redis://localhost:6379/0        # можно закомментировать — FSM будет в памяти
ADMIN_CHAT_ID=487857413                    # чат для уведомлений (user_id или chat_id группы -100...)
ADMINS=487857413,123456789                 # список user_id админов через запятую
ASSETS_EXAMPLE_PATH=assets/example_screenshot.png
PRICE_RUB=2500
```

* `ADMIN_CHAT_ID` — **куда слать уведомления** (личка или группа).
* `ADMINS` — **кто может выполнять** админ‑команды.

---

## Установка

### 0) Python и виртуальное окружение

```bash
python -m venv .venv
source .venv/bin/activate
cd urban-tickets-bot
pip install -r requirements.txt
cp .env.example .env
# отредактируйте .env (BOT_TOKEN / DATABASE_URL / REDIS_URL и пр.)
```

### 1A) PostgreSQL и Redis (macOS / Homebrew)

```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis

# создать базу (если нет)
createuser -s postgres 2>/dev/null || true
createdb -O postgres urban_tickets 2>/dev/null || true
```

### 1B) Альтернатива: Docker

Создайте `docker-compose.yml` рядом с проектом:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: urban_pg
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: root
      POSTGRES_DB: urban_tickets
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
  redis:
    image: redis:7
    container_name: urban_redis
    ports:
      - "6379:6379"
volumes:
  pgdata:
```

Запуск:

```bash
docker compose up -d
```

> Если Redis с паролем — используйте `REDIS_URL=redis://:PASSWORD@localhost:6379/0`.

---

## Миграции

> В `psql`‑URL **не** используйте `+asyncpg`.

### Базовые миграции (через Homebrew libpq)

```bash
brew install libpq  # если не установлен
$(brew --prefix)/opt/libpq/bin/psql "postgresql://postgres:root@localhost:5432/urban_tickets" -f migrations/001_init.sql
$(brew --prefix)/opt/libpq/bin/psql "postgresql://postgres:root@localhost:5432/urban_tickets" -f migrations/002_indexes.sql
```

### Нормализация ФИО (если у вас были разные колонки в payments)

Мы стандартизировали колонку **`payments.ticket_full_name`** для ФИО в билете. Если раньше использовалась `payments.full_name`, выполните миграцию:

```bash
$(brew --prefix)/opt/libpq/bin/psql "postgresql://postgres:root@localhost:5432/urban_tickets" -f migrations/005_unify_full_name.sql
```

Проверить схему:

```bash
$(brew --prefix)/opt/libpq/bin/psql "postgresql://postgres:root@localhost:5432/urban_tickets" -c "\d payments"
```

### Через Docker

```bash
docker exec -i urban_pg psql -U postgres -d urban_tickets -f - < migrations/001_init.sql
docker exec -i urban_pg psql -U postgres -d urban_tickets -f - < migrations/002_indexes.sql
docker exec -i urban_pg psql -U postgres -d urban_tickets -f - < migrations/005_unify_full_name.sql
```

---

## Запуск

```bash
cd urban-tickets-bot
source .venv/bin/activate
python -m app.bot
```

Первые команды в Telegram (от админа):

```text
/addreq Тинькофф;Иванов Иван;5536 xxxx xxxx 1234;Urban_2500;1
/setactive 1
```

---

## Команды администратора

* `/addreq bank;holder;account;comment;order_idx` — добавить реквизиты.
* `/listreq` — список реквизитов (активные помечены ✅).
* `/setactive <id>` — вручную сделать набор активным (сброс `usage_count` у него на 0).
* `/rotate` — принудительная ротация на следующий по `order_idx`.
* `/stats` — сводка: всего оплат, активные реквизиты и «осталось до ротации».
* `/payments [N]` — последние N платежей (по умолчанию 20, максимум 100), с колонкой **ФИО (билет)** из `ticket_full_name`.
* `/clear_payments` — `TRUNCATE payments RESTART IDENTITY CASCADE`.
* `/export_excel` — выгрузка всех платежей в Excel (`payments_export.xlsx`), включает колонку **ticket_full_name**.

> Для `/export_excel` даты записываются «наивными» в UTC (Excel не любит TZ‑aware). Если нужно, отформатируйте локально.

---

## Проверка БД

### Диагностика соединения

```bash
$(brew --prefix)/opt/libpq/bin/pg_isready -h localhost -p 5432
$(brew --prefix)/opt/libpq/bin/psql "postgresql://postgres:root@localhost:5432/urban_tickets" -c "SELECT 1;"
```

### Что пишет бот

* `users` — создаётся при первом «Купить билет…»; обновляется `username`/`full_name` при необходимости.
* `payments` — при получении скриншота: `user_id`, `requisites_id`, `amount=PRICE_RUB`, `file_id`, `file_type (photo|document)`, `batch_counter`, `status=pending`, `ticket_full_name`, `created_at`.
* `requisites` — растёт `usage_count`, **ротация каждые 20**.

### Полезные SQL‑запросы

```sql
-- последние платежи с деталями, включая ФИО билета
SELECT p.id, p.created_at, p.amount, p.file_type, p.batch_counter, p.status,
       p.ticket_full_name,
       u.tg_id, u.username, u.full_name AS user_full_name,
       r.id AS req_id, r.bank, r.holder, r.account, r.comment
FROM payments p
JOIN users u ON u.id = p.user_id
JOIN requisites r ON r.id = p.requisites_id
ORDER BY p.id DESC
LIMIT 20;

-- активные реквизиты и прогресс до ротации
SELECT id, bank, holder, account, comment, active, usage_count,
       (20 - usage_count) AS remain_to_rotate
FROM requisites
WHERE active = true;

-- разбивка оплат по requisites_id
SELECT requisites_id, COUNT(*) AS cnt
FROM payments
GROUP BY requisites_id
ORDER BY requisites_id;
```

---

## Частые проблемы

* **`psql: command not found`** → `brew install libpq`; используйте `$(brew --prefix)/opt/libpq/bin/psql`.
* **`connection refused`** → неверный порт/сервер не запущен; проверьте `pg_isready`.
* **`password authentication failed`** → пароль Postgres неверный; задайте в pgAdmin или `ALTER USER postgres WITH PASSWORD '...'`.
* **`redis.exceptions.AuthenticationError: Authentication required`** → Redis с паролем; укажите `REDIS_URL=redis://:PASSWORD@host:6379/0` или уберите `REDIS_URL` (FSM in‑memory).
* **Импорты `app.*` не находятся** → запускайте как модуль из корня: `python -m app.bot`; проверьте, что есть `__init__.py` в `app/*`.
* **Excel и часовые пояса** → Excel не поддерживает tz‑aware: перед записью даты делаются наивными в UTC.

---

## Структура проекта

```
urban-tickets-bot/
  app/
    bot.py
    config.py
    states.py
    keyboards.py
    handlers/
      start.py
      callbacks.py
      payments.py
      admin.py
    services/
      rotation.py
      notifications.py
    db/
      base.py
      models.py
      crud.py
    middlewares/
      throttling.py
  migrations/
    001_init.sql
    002_indexes.sql
    005_unify_full_name.sql
  assets/
    example_screenshot.png
  requirements.txt
  .env
  README.md
  ADMIN_GUIDE.md
```

---

## Быстрый сквозной тест

1. `/start` → «Купить билет — 2 500 ₽».
2. Нажмите «Купить…» → увидите активные реквизиты.
3. Нажмите «Оплатил» → бот попросит скрин + пришлёт образец. **В подписи к фото/файлу укажите ФИО для билета.**
4. Отправьте фото/файл → ответ:

   ```
   Оплата получена 🎉
   Спасибо! Ваш билет на Urban оформлен.
   ```
5. В БД появится запись в `payments` (с `ticket_full_name`), а в `requisites` увеличится `usage_count`. На 20‑й оплате — **авторотация**.
