-- Schema for EduMarket (baseline)

CREATE TABLE IF NOT EXISTS roles (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,
    description     VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role_id         INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS courses (
    id                  BIGSERIAL PRIMARY KEY,
    title               VARCHAR(200) NOT NULL,
    description         TEXT,
    price               NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    status              VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    author_id           INTEGER REFERENCES users(id) ON DELETE SET NULL,
    avg_rating          NUMERIC(3,2) NOT NULL DEFAULT 0,
    reviews_count       INTEGER NOT NULL DEFAULT 0,
    enrollments_count   INTEGER NOT NULL DEFAULT 0,
    total_revenue       NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS course_modules (
    id          BIGSERIAL PRIMARY KEY,
    course_id   BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    position    INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT uq_course_modules_position UNIQUE (course_id, position)
);

CREATE TABLE IF NOT EXISTS lessons (
    id               BIGSERIAL PRIMARY KEY,
    course_id        BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    module_id        BIGINT NOT NULL REFERENCES course_modules(id) ON DELETE CASCADE,
    title            VARCHAR(200) NOT NULL,
    content          TEXT,
    position         INTEGER NOT NULL DEFAULT 1,
    duration_minutes INTEGER,
    CONSTRAINT uq_lessons_position UNIQUE (module_id, position)
);

CREATE INDEX IF NOT EXISTS ix_lessons_course_module ON lessons (course_id, module_id);

CREATE TABLE IF NOT EXISTS enrollments (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id    BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    status       VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','cancelled')),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_enrollments_user_course UNIQUE (user_id, course_id)
);

CREATE INDEX IF NOT EXISTS ix_enrollments_user_course ON enrollments (user_id, course_id);

CREATE TABLE IF NOT EXISTS progresses (
    id            BIGSERIAL PRIMARY KEY,
    enrollment_id BIGINT NOT NULL REFERENCES enrollments(id) ON DELETE CASCADE,
    lesson_id     BIGINT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    status        VARCHAR(20) NOT NULL DEFAULT 'not_started' CHECK (status IN ('not_started','in_progress','completed')),
    score         INTEGER,
    completed_at  TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_progresses_enrollment_lesson UNIQUE (enrollment_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status       VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','cancelled','refunded')),
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_orders_user_created ON orders (user_id, created_at);

CREATE TABLE IF NOT EXISTS order_items (
    id         BIGSERIAL PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    course_id  BIGINT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT,
    quantity   INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    price      NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (price >= 0),
    CONSTRAINT uq_order_items_order_course_unique UNIQUE (order_id, course_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id             BIGSERIAL PRIMARY KEY,
    order_id       BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    amount         NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    status         VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','failed','refunded')),
    provider       VARCHAR(50),
    transaction_id VARCHAR(100),
    paid_at        TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_payments_order_status ON payments (order_id, status);

CREATE TABLE IF NOT EXISTS reviews (
    id         BIGSERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id  BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_reviews_user_course UNIQUE (user_id, course_id)
);

CREATE INDEX IF NOT EXISTS ix_reviews_course_rating ON reviews (course_id, rating);

CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGSERIAL PRIMARY KEY,
    table_name   VARCHAR(100) NOT NULL,
    record_id    VARCHAR(100) NOT NULL,
    action       VARCHAR(10) NOT NULL,
    old_data     JSONB,
    new_data     JSONB,
    performed_by INTEGER,
    source       VARCHAR(50),
    performed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_table_action ON audit_log (table_name, action);
CREATE INDEX IF NOT EXISTS ix_audit_log_performed_at ON audit_log (performed_at);

CREATE TABLE IF NOT EXISTS import_jobs (
    id                BIGSERIAL PRIMARY KEY,
    job_type          VARCHAR(50) NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','completed','failed')),
    params            JSONB,
    total_records     INTEGER,
    processed_records INTEGER,
    errors_count      INTEGER,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS import_job_errors (
    id           BIGSERIAL PRIMARY KEY,
    job_id       BIGINT NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_number   INTEGER,
    error_message TEXT NOT NULL,
    payload      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
