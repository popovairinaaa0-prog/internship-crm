# Развёртывание Internship CRM на VPS

Минимальная инструкция для развёртывания на чистом сервере (Ubuntu 22.04+).

---

## 1. Подготовка сервера

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER   # перелогиньтесь
```

## 2. Код

```bash
git clone <repo-url> /opt/crm
cd /opt/crm/code
```

## 3. Конфиг

Создайте `.env.prod` на базе `.env.example`. **Обязательно поменяйте**:

- `SECRET_KEY` — длинная случайная строка (`openssl rand -hex 32`)
- `DEBUG=False`
- `ALLOWED_HOSTS=crm.example.com,123.45.67.89`
- `POSTGRES_PASSWORD` — надёжный пароль
- `BOT_API_TOKEN` — длинная случайная строка
- `STUDENT_BOT_TOKEN` и `STUDENT_BOT_USERNAME` (см. этап 6)
- `MANAGERS_BOT_TOKEN` и `MANAGERS_BOT_USERNAME`
- `MANAGERS_CHAT_ID` — id группового чата менеджеров

## 4. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Первичная настройка

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml exec web python manage.py register_push_tick_schedule
```

## 6. Проверка

- HTTP: `curl http://<host>/healthz/` → должен вернуть `{"ok": true, "db": "ok"}`.
- Админка: `http://<host>/admin/` — заходим суперюзером, открывается главная с дашбордом.
- Боты:
  - `docker compose -f docker-compose.prod.yml logs bot` — должно быть `Студенческий бот стартует`.
  - В Telegram — отправьте боту `/start`, должен ответить.

## 7. SSL (заглушка — добавить позже)

В `docker-compose.prod.yml` и `nginx/prod.conf` сейчас только HTTP. Для боевой
работы добавьте SSL одним из способов:

**Вариант А: certbot вручную**
```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d crm.example.com
```
Затем добавьте в `nginx/prod.conf` server-блок на 443 с этими сертификатами,
смонтировав `/etc/letsencrypt` в nginx-контейнер.

**Вариант Б: Traefik** перед nginx — автообновление, проще на новых серверах.

## 8. Бэкапы

Сервис `backup` в docker-compose.prod.yml сам по себе запускает `pg_dump`
каждые сутки в 04:00 по UTC и хранит 7 последних снимков в volume `backups_data`.

Ручной запуск:
```bash
docker compose -f docker-compose.prod.yml exec backup /scripts/backup_db.sh
```

Восстановление из дампа:
```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U crm -d crm < <(docker run --rm -i -v crm_backups_data:/b alpine \
                            sh -c "gunzip -c /b/crm-2026-06-12-0400.sql.gz")
```

## 9. Обновление кода

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

## 10. Мониторинг

- Логи: `docker compose -f docker-compose.prod.yml logs -f web qcluster bot`
- Бот-heartbeat: `docker ps` — все контейнеры должны быть `Up`. Если бот упал,
  Docker сам перезапустит (`restart: always`).
- Метрики в дашборде главной страницы — кешируются 60 секунд.

## Что не вошло в MVP (на следующий этап)

- Опросники студентам (`audience=STUDENT` шаблоны + `STUDENT_STATUS_PERIODIC`).
- Утренний дайджест менеджерам.
- Аналитика по конверсии и времени принятия решений.
- Кастомные двух-колоночные карточки студента/компании из UX_SPEC.
