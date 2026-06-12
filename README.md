# Internship CRM

Внутренняя CRM для ведения студентов, компаний-партнёров и стажировок. Заменяет работу в нескольких Google-таблицах.

Подробности в планирующих документах рядом с этой папкой:
- `../CLAUDE.md` — стек, архитектура, соглашения
- `../SCHEMA.md` — модели БД
- `../UX_SPEC.md` — описание всех экранов
- `../PROMPTS.md` — план разработки по этапам

## Локальный запуск

### 1. Установка инструментов (один раз)

**Python 3.12** — уже стоит, проверь: `python --version`

**uv** (менеджер пакетов):
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**Docker Desktop** — скачать с https://docker.com/products/docker-desktop, установить, перезагрузиться.

### 2. Установка зависимостей

```powershell
uv sync
```

### 3. Запуск базы

**С Docker (рекомендуется):**
```powershell
docker compose up -d postgres
```

**Без Docker (быстрый старт):**
Оставь `DATABASE_URL` пустым в `.env` — будет использоваться SQLite в `db.sqlite3`.

### 4. Миграции и админ

```powershell
copy .env.example .env
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### 5. Запуск

```powershell
uv run python manage.py runserver
```

Открыть http://127.0.0.1:8000/admin/ — это админка Django.

### Тема Admin

В Django 5 встроен переключатель темы (солнышко/луна/auto) в правом верхнем углу шапки админки. Выбор сохраняется в браузере.

## Тесты и линт

```powershell
uv run pytest
uv run ruff check .
uv run ruff format .
```

## Структура

```
code/
├── manage.py
├── pyproject.toml
├── docker-compose.yml
├── crm/                # настройки Django
├── students/           # студенты, направления
├── companies/          # компании
├── placements/         # связки студент↔компания
├── notifications/      # рассылки, автопуши, комментарии
├── accounts/           # User, роли
├── bot/                # отдельный сервис aiogram
└── tests/
```
