# EduMarket — курсовой проект (PostgreSQL + FastAPI)

Информационная система маркетплейса онлайн‑курсов: реляционная БД, аудит, триггеры агрегаций, аналитические функции/VIEW, REST API, батч‑импорт, Docker.

## Запуск

1) Скопировать `.env.example` → `.env` и при необходимости поменять порты/логины. Секреты в код не коммитить.
2) `docker-compose up --build` — поднимет PostgreSQL и API на `${APP_PORT:-8000}`.
3) Swagger: `http://localhost:8000/docs`, OpenAPI: `/openapi.json`.
4) Health: `GET /api/health`.

## Структура

- `app/models/*.py` — SQLAlchemy модели (users, roles, courses, modules, lessons, enrollments, progresses, orders, order_items, payments, reviews, audit_log, import_jobs, import_job_errors).
- `sql/001_schema.sql` — DDL, ограничения PK/FK/UNIQUE/CHECK, каскады.
- `sql/002_functions_triggers_views.sql` — аудит, триггеры агрегаций, скалярные/табличные функции, VIEW.
- `scripts/seed_data.py` — наполнение реалистичными данными (1500+ заказов, >5000 order_items).

## Аудит и триггеры

- Универсальный триггер `fn_log_audit` на INSERT/UPDATE/DELETE для ключевых таблиц.
- Агрегации: обновление рейтинга курсов, количества зачислений, выручки по платежам.
- Журнал `audit_log` хранит старые/новые данные, время, пользователя (через `app.current_user`, можно пробрасывать заголовок `X-User-Id`).

## Функции и VIEW (SQL)

- Скалярные: `fn_course_revenue`, `fn_course_rating`, `fn_course_completion_percent`.
- Табличные: `fn_top_courses_by_revenue`, `fn_user_activity`, `fn_sales_dynamics`.
- VIEW: `vw_course_sales`, `vw_course_ratings`, `vw_user_progress`.

## API (префикс `/api`)

- Users: `POST /users`, `GET /users`.
- Courses: `POST /courses`, `GET /courses`, `PATCH /courses/{id}`.
- Enrollments: `POST /enrollments`, `GET /enrollments`.
- Orders/Payments: `POST /orders` (создаёт order + items), `POST /orders/payments`, `GET /orders`.
- Reviews: `POST /reviews`, `GET /reviews`.
- Reports: `GET /reports/top-courses`, `/reports/user-activity`, `/reports/sales-dynamics`.
- Batch import: `POST /batch-import` (создаёт job), `GET /batch-import`, `GET /batch-import/{id}`, `GET /batch-import/{id}/errors`.
- Health: `GET /health`.
  Все запросы параметризованы, f-string/конкатенаций SQL нет.

## Данные и сиды

- Запуск сида: `docker-compose exec backend python scripts/seed_data.py`.
- Проверка объёмов: `SELECT COUNT(*) FROM orders;`, `SELECT COUNT(*) FROM order_items;` (>5000), `SELECT COUNT(*) FROM payments;`.

## Batch import (демо)

- `POST /api/batch-import` c телом, например: `{"job_type": "courses_csv", "params": {"source": "demo.csv"}, "total_records": 120}` — создаст задачу, фон обрабатывает, пишет ошибки в `import_job_errors`, статусы обновляются.
- `GET /api/batch-import` и `/api/batch-import/{id}` — статус; `/api/batch-import/{id}/errors` — ошибки.

## Безопасность и штрафы

- Секреты только в `.env`, не хранить в коде.
- SQL только параметризованно (asyncpg/SQLAlchemy), без f-string/конкатенаций.
