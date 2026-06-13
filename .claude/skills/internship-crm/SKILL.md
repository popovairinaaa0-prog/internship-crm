---
name: internship-crm
description: Помогает Claude Code работать с CRM-проектом стажировок. Используй при запуске проекта, навигации по коду, миграциях, тестах, правках моделей/админки, обновлении README и подготовке репо к публикации. Триггеры — упоминания "CRM стажёры", "internship-crm", "Django-админка проекта", файлы из students/companies/placements/notifications/accounts.
---

# Internship CRM — рабочий гид для Claude Code

Это внутренняя Django-CRM карьерного центра. MVP закрыт (этапы 1–10), идёт визуальная переделка через django-unfold. Telegram-боты и рассылки запланированы во второй итерации.

## 0. Первое, что делать в новой сессии

1. Прочитать `README.md` — общая картина MVP и стек.
2. При работе с моделями/БД — прочитать `../SCHEMA.md` (если есть рядом с папкой) или модели прямо в `students/`, `companies/`, `placements/`.
3. При работе с UI — прочитать `../UX_SPEC.md` (если есть) или текущие шаблоны в `templates/admin/`.
4. Посмотреть `git log --oneline | head -20`, чтобы понять, на каком коммите остановились.
5. Спросить Иру, с чего продолжаем — не угадывать.

## 1. Карта проекта

```
code/                       ← корень репо
├── crm/                    Django settings, urls, wsgi
├── students/               студенты, направления, импорт CSV
├── companies/              компании-партнёры
├── placements/             связки студент↔компания со статусами
├── notifications/          комментарии, шаблоны (под рассылки 2-й итерации)
├── accounts/               User, роли (admins, vip_managers)
├── common/                 утилиты, GenericForeignKey
├── bot/                    каркас aiogram (НЕ трогать в MVP — 2-я итерация)
├── templates/admin/        кастомные шаблоны админки и дашборда
├── static/                 CSS/JS поверх unfold
├── data/sample/            CSV для импорта (тест-данные)
├── nginx/                  конфиг прода
├── scripts/                бэкапы pg_dump
├── tests/                  pytest
├── manage.py
├── pyproject.toml          зависимости через uv
├── docker-compose.yml
├── docker-compose.prod.yml
└── .env.example
```

**Где лежит бизнес-логика:** в `<app>/services.py`, НЕ в моделях и НЕ во вьюхах. Модели — только данные и базовая валидация.

**Полиморфные комментарии/файлы:** через `GenericForeignKey` из `contenttypes` (см. `common/`), не плодить `StudentComment` / `CompanyComment`.

## 2. Запуск сервиса

### Быстрый старт без Docker (SQLite)

```powershell
uv sync
copy .env.example .env
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Открыть http://127.0.0.1:8000/admin/

### С Postgres через Docker

```powershell
docker compose up -d postgres
# в .env: DATABASE_URL=postgres://crm:crm@postgres:5432/crm
uv run python manage.py migrate
uv run python manage.py runserver
```

### Загрузить демо-данные

```powershell
uv run python manage.py import_students data/sample/students.csv
uv run python manage.py import_companies data/sample/companies.csv
```

### Полный стек локально (web + bot + qcluster)

```powershell
docker compose up
```

## 3. Внесение изменений

### Стандартный цикл правки

1. **План** — короткий, в чате. Ира любит видеть план до старта.
2. **Изменения в коде** — следуй конвенциям из CLAUDE.md/README:
   - ruff, line length 100
   - типы на публичных функциях
   - `__str__` и `Meta.verbose_name` (русский) обязательны на моделях
   - индексы на полях для фильтров (`status`, `next_contact_at`)
   - имена в коде на английском, русский только в `verbose_name` и UI
   - НИКАКИХ сигналов Django (`post_save` и т.п.) для бизнес-логики
3. **Миграции** — если правил модели:
   ```powershell
   uv run python manage.py makemigrations
   uv run python manage.py migrate
   ```
   Правило: миграции, применённые в проде, **не редактируем**. Только новые сверху.
4. **Тесты** — обязательны на критичные места (Placement, импорт, права).
5. **Линт + формат**:
   ```powershell
   uv run ruff check .
   uv run ruff format .
   ```
6. **Прогон тестов**:
   ```powershell
   uv run pytest
   uv run pytest tests/test_placements.py -v   # точечно
   ```
7. **Коммит** только когда Ира попросит. Стиль сообщений — посмотри `git log --oneline`, там паттерн `stage N: …` / `visual: …` / `docs: …`.

### Правки админки (визуальная фаза)

- Все `ModelAdmin` наследуются от `unfold.admin.ModelAdmin`, не от `admin.ModelAdmin`.
- Цвета Telegram-индикатора и дат контакта — Tailwind `emerald/red/amber/violet` 400–500, должны быть видны и в light, и в dark.
- Фильтры в сайдбаре — стандартные Django, НЕ dropdown unfold (Ира их не приняла).
- Inline-смена статусов через `list_editable`. Для Placement — через `change_placement_status`.
- Дашборд — `templates/admin/index.html`, кастомный, без app_list. Карточки кликабельные.
- Подсветка строк по сроку контакта — JS навешивает классы `.row-overdue / .row-today / .row-soon`.

### Что НЕ трогать в MVP (вторая итерация)

- `bot/` — каркас aiogram, рассылки, обработчики callback'ов.
- Модели `BroadcastJob`, `BroadcastDelivery`, `ManualContact`, `PushRule`, `PushSent` — есть, но активно не используются.
- Шаблон `templates/admin/notifications/broadcast_new.html` — отложен.
- Опросники студентам, утренний дайджест, аналитика — задел в моделях есть, реализация позже.

## 4. Обновление README

README на главной странице репо описывает MVP по структуре:
- Название, Проблема, Пользователь
- Основная функция, Формат результата
- Минимальный функционал (✅ что сделано / ⏳ что во вторую итерацию)
- Технологии
- Локальный запуск, тесты, структура

**Когда обновлять:**
- Закрыли новый этап / добавили фичу → перенести из ⏳ в ✅.
- Поменялся стек (новая либа) → секция «Технологии».
- Появилась новая директория верхнего уровня → секция «Структура».
- Изменилась команда запуска → секция «Локальный запуск».

**Чего НЕ писать в README:**
- Внутренние решения по UI (это в `../UX_SPEC.md`).
- Историю — она в `git log` и коммитах.
- Маркетинговую воду — Ира не терпит.

## 5. Проверка ошибок

### Сервер не стартует

1. `uv sync` — синк зависимостей.
2. `.env` есть и валиден? Проверь `SECRET_KEY`, `DATABASE_URL`.
3. Миграции применены? `uv run python manage.py showmigrations` — должны быть `[X]` у всех.
4. Если Postgres — `docker compose ps`, контейнер `postgres` должен быть `running`.
5. Порт 8000 свободен? `netstat -an | findstr 8000`.

### Ошибки миграций

- `InconsistentMigrationHistory` → кто-то применил миграции в другом порядке. Безопасно: пересоздать БД локально (`docker compose down -v`, `docker compose up -d postgres`, заново `migrate`). НИКОГДА не делать это на проде без явного разрешения Иры.
- `relation does not exist` → миграция не применилась. `python manage.py migrate <app>`.

### Падают тесты

```powershell
uv run pytest -x -v                   # остановиться на первом фейле
uv run pytest tests/test_X.py -v -s   # точечно, с print
uv run pytest --lf                    # только провалившиеся в прошлый раз
```

98 тестов в MVP-состоянии должны быть зелёные. Если красные — прежде чем коммитить правку, разобраться, что сломали.

### Ошибки в админке

- `TemplateDoesNotExist` → проверь путь в `templates/admin/...`.
- Не подхватился стиль → проверь, что unfold-app идёт ДО `django.contrib.admin` в `INSTALLED_APPS`.
- Не видна колонка / фильтр → `list_display`, `list_filter`, `search_fields` в `<app>/admin.py`.

### Логи

```powershell
docker compose logs web --tail 100
docker compose logs postgres --tail 50
uv run python manage.py runserver --verbosity 2
```

## 6. Подготовка к публикации / релизу

Чеклист перед `git push` или новым релизом:

- [ ] `.env` НЕ в коммите (`git ls-files | findstr env` — должен показать только `.env.example`).
- [ ] `.env.example` без реальных токенов / паролей.
- [ ] Нет хардкода токенов / паролей в коде (`grep -rn "TOKEN\|PASSWORD\|SECRET" --include="*.py"`).
- [ ] `uv run ruff check .` — чисто.
- [ ] `uv run ruff format .` — отформатировано.
- [ ] `uv run pytest` — все зелёные.
- [ ] `uv run python manage.py makemigrations --dry-run` — нет необъявленных изменений моделей.
- [ ] `uv run python manage.py check --deploy` — для прод-релиза.
- [ ] README актуален: команды запуска работают «с нуля» на чистой машине.
- [ ] Sample-данные в `data/sample/` — без реальных ФИО, телефонов, email (только `.example` домены).

### Создать релиз на GitHub

```powershell
gh release create v0.X.0 --title "MVP v0.X" --notes "Что вошло в этот релиз: ..."
```

### Запушить на GitHub

```powershell
git push origin master
```

Force-push на `master` — НИКОГДА без явного «да» от Иры.

## 7. Что любит / не любит Ира

- **Короткий план до старта** — обязательно для нетривиальных задач.
- **Без воды и пересказа** — что сделал, видно из диффа.
- **Конкретика** — варианты с плюсами и минусами лучше, чем один «правильный» путь.
- **Без эмодзи** в коде и сообщениях — если не попросила.
- **Современный 2026-style UI** — ближе к UX_SPEC, не дефолтная Django-админка.
- Если действие необратимое (удаление, push, миграция на прод) — **спросить до**, а не отчитываться после.
