-- Functions, triggers, and views for EduMarket

-- =========================
-- Audit logging
-- =========================

CREATE OR REPLACE FUNCTION fn_log_audit() RETURNS trigger AS $$
DECLARE
    v_old JSONB;
    v_new JSONB;
    v_user_id INT;
    v_source TEXT;
BEGIN
    v_user_id := NULLIF(current_setting('app.current_user', true), '')::INT;
    v_source := current_setting('app.source', true);

    IF (TG_OP = 'DELETE') THEN
        v_old := to_jsonb(OLD);
        v_new := NULL;
    ELSIF (TG_OP = 'INSERT') THEN
        v_old := NULL;
        v_new := to_jsonb(NEW);
    ELSE
        v_old := to_jsonb(OLD);
        v_new := to_jsonb(NEW);
    END IF;

    INSERT INTO audit_log(table_name, record_id, action, old_data, new_data, performed_by, source, performed_at)
    VALUES (TG_TABLE_NAME, COALESCE(NEW.id, OLD.id)::TEXT, TG_OP, v_old, v_new, v_user_id, v_source, now());

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION attach_audit_trigger(table_name TEXT) RETURNS void AS $$
BEGIN
    EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON %I', table_name, table_name);
    EXECUTE format('CREATE TRIGGER trg_audit_%I AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION fn_log_audit();', table_name, table_name);
END;
$$ LANGUAGE plpgsql;

SELECT attach_audit_trigger(t) FROM (VALUES
    ('users'),
    ('courses'),
    ('course_modules'),
    ('lessons'),
    ('enrollments'),
    ('progresses'),
    ('orders'),
    ('order_items'),
    ('payments'),
    ('reviews')
) AS tbl(t);

-- =========================
-- Aggregate maintenance triggers
-- =========================

CREATE OR REPLACE FUNCTION fn_update_course_rating() RETURNS trigger AS $$
BEGIN
    UPDATE courses c
    SET avg_rating = COALESCE(sub.avg_rating, 0),
        reviews_count = COALESCE(sub.cnt, 0),
        updated_at = now()
    FROM (
        SELECT course_id, AVG(rating)::NUMERIC(3,2) AS avg_rating, COUNT(*) AS cnt
        FROM reviews
        WHERE course_id = COALESCE(NEW.course_id, OLD.course_id)
        GROUP BY course_id
    ) sub
    WHERE c.id = sub.course_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_reviews_agg ON reviews;
CREATE TRIGGER trg_reviews_agg
AFTER INSERT OR UPDATE OR DELETE ON reviews
FOR EACH ROW
EXECUTE FUNCTION fn_update_course_rating();


CREATE OR REPLACE FUNCTION fn_update_course_enrollments() RETURNS trigger AS $$
BEGIN
    UPDATE courses c
    SET enrollments_count = COALESCE(sub.cnt, 0),
        updated_at = now()
    FROM (
        SELECT course_id, COUNT(*) AS cnt
        FROM enrollments
        WHERE course_id = COALESCE(NEW.course_id, OLD.course_id)
          AND status IN ('active','completed')
        GROUP BY course_id
    ) sub
    WHERE c.id = sub.course_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enrollments_agg ON enrollments;
CREATE TRIGGER trg_enrollments_agg
AFTER INSERT OR UPDATE OR DELETE ON enrollments
FOR EACH ROW
EXECUTE FUNCTION fn_update_course_enrollments();


CREATE OR REPLACE FUNCTION fn_update_course_revenue() RETURNS trigger AS $$
BEGIN
    UPDATE courses c
    SET total_revenue = COALESCE(sub.total, 0),
        updated_at = now()
    FROM (
        SELECT oi.course_id,
               SUM(CASE WHEN p.status = 'refunded' THEN -p.amount ELSE p.amount END) AS total
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        JOIN order_items oi ON oi.order_id = o.id
        WHERE p.order_id = COALESCE(NEW.order_id, OLD.order_id)
          AND p.status IN ('paid','refunded')
        GROUP BY oi.course_id
    ) sub
    WHERE c.id = sub.course_id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payments_revenue ON payments;
CREATE TRIGGER trg_payments_revenue
AFTER INSERT OR UPDATE OR DELETE ON payments
FOR EACH ROW
EXECUTE FUNCTION fn_update_course_revenue();

-- =========================
-- Scalar functions
-- =========================

CREATE OR REPLACE FUNCTION fn_course_revenue(p_course_id BIGINT) RETURNS NUMERIC(12,2) AS $$
DECLARE
    v_total NUMERIC(12,2);
BEGIN
    SELECT COALESCE(SUM(CASE WHEN p.status = 'refunded' THEN -p.amount ELSE p.amount END), 0)
    INTO v_total
    FROM payments p
    JOIN orders o ON o.id = p.order_id
    JOIN order_items oi ON oi.order_id = o.id
    WHERE oi.course_id = p_course_id
      AND p.status IN ('paid','refunded');
    RETURN v_total;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_course_rating(p_course_id BIGINT) RETURNS NUMERIC(3,2) AS $$
DECLARE
    v_rating NUMERIC(3,2);
BEGIN
    SELECT COALESCE(AVG(rating), 0)::NUMERIC(3,2) INTO v_rating
    FROM reviews
    WHERE course_id = p_course_id;
    RETURN v_rating;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_course_completion_percent(p_course_id BIGINT) RETURNS NUMERIC(5,2) AS $$
DECLARE
    v_completed NUMERIC;
    v_total NUMERIC;
BEGIN
    SELECT COUNT(*)::NUMERIC
    INTO v_completed
    FROM progresses pr
    JOIN enrollments e ON e.id = pr.enrollment_id
    WHERE pr.status = 'completed' AND e.course_id = p_course_id;

    SELECT COUNT(*)::NUMERIC
    INTO v_total
    FROM progresses pr
    JOIN enrollments e ON e.id = pr.enrollment_id
    WHERE e.course_id = p_course_id;

    IF v_total = 0 THEN
        RETURN 0;
    END IF;
    RETURN ROUND((v_completed / v_total) * 100, 2);
END;
$$ LANGUAGE plpgsql STABLE;

-- =========================
-- Table functions (reports)
-- =========================

CREATE OR REPLACE FUNCTION fn_top_courses_by_revenue(p_start TIMESTAMPTZ, p_end TIMESTAMPTZ, p_limit INT DEFAULT 10)
RETURNS TABLE (
    course_id BIGINT,
    title TEXT,
    revenue NUMERIC(12,2),
    orders_count INT,
    payments_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.title::TEXT,
        COALESCE(SUM(CASE WHEN p.status = 'refunded' THEN -p.amount ELSE p.amount END), 0) AS revenue,
        COUNT(DISTINCT o.id)::INT AS orders_count,
        COUNT(p.id)::INT AS payments_count
    FROM courses c
    JOIN order_items oi ON oi.course_id = c.id
    JOIN orders o ON o.id = oi.order_id
    JOIN payments p ON p.order_id = o.id
    WHERE p.paid_at BETWEEN p_start AND p_end
      AND p.status IN ('paid','refunded')
    GROUP BY c.id, c.title
    ORDER BY revenue DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_user_activity(p_start TIMESTAMPTZ, p_end TIMESTAMPTZ)
RETURNS TABLE (
    user_id INT,
    email TEXT,
    enrollments_count INT,
    lessons_completed INT,
    payments_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.id AS user_id,
        u.email::TEXT AS email,
        COALESCE(enr.enrollments_count, 0)::INT AS enrollments_count,
        COALESCE(pr.lessons_completed, 0)::INT AS lessons_completed,
        COALESCE(pay.payments_count, 0)::INT AS payments_count
    FROM users u
    LEFT JOIN (
        SELECT e.user_id, COUNT(*)::INT AS enrollments_count
        FROM enrollments e
        WHERE e.created_at BETWEEN p_start AND p_end
        GROUP BY e.user_id
    ) enr ON enr.user_id = u.id
    LEFT JOIN (
        SELECT e.user_id, COUNT(*)::INT AS lessons_completed
        FROM progresses pr
        JOIN enrollments e ON e.id = pr.enrollment_id
        WHERE pr.status = 'completed'
          AND pr.completed_at BETWEEN p_start AND p_end
        GROUP BY e.user_id
    ) pr ON pr.user_id = u.id
    LEFT JOIN (
        SELECT o.user_id, COUNT(*)::INT AS payments_count
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE p.paid_at BETWEEN p_start AND p_end
          AND p.status IN ('paid','refunded')
        GROUP BY o.user_id
    ) pay ON pay.user_id = u.id
    WHERE u.role_id IS NOT NULL;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_sales_dynamics(p_start TIMESTAMPTZ, p_end TIMESTAMPTZ)
RETURNS TABLE (
    period_start DATE,
    revenue NUMERIC(12,2),
    orders_count INT,
    payments_count INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        date_trunc('month', p.paid_at)::DATE AS period_start,
        COALESCE(SUM(CASE WHEN p.status = 'refunded' THEN -p.amount ELSE p.amount END), 0) AS revenue,
        COUNT(DISTINCT o.id)::INT AS orders_count,
        COUNT(p.id)::INT AS payments_count
    FROM payments p
    JOIN orders o ON o.id = p.order_id
    WHERE p.paid_at BETWEEN p_start AND p_end
      AND p.status IN ('paid','refunded')
    GROUP BY date_trunc('month', p.paid_at)
    ORDER BY period_start;
END;
$$ LANGUAGE plpgsql STABLE;

-- =========================
-- Views
-- =========================

CREATE OR REPLACE VIEW vw_course_sales AS
SELECT
    c.id AS course_id,
    c.title,
    COALESCE(SUM(CASE WHEN p.status = 'refunded' THEN -p.amount ELSE p.amount END), 0) AS revenue,
    COUNT(DISTINCT o.id) AS orders_count,
    COUNT(p.id) AS payments_count,
    COUNT(DISTINCT e.id) AS enrollments_total
FROM courses c
LEFT JOIN order_items oi ON oi.course_id = c.id
LEFT JOIN orders o ON o.id = oi.order_id
LEFT JOIN payments p ON p.order_id = o.id AND p.status IN ('paid','refunded')
LEFT JOIN enrollments e ON e.course_id = c.id
GROUP BY c.id, c.title;

CREATE OR REPLACE VIEW vw_course_ratings AS
SELECT
    c.id AS course_id,
    c.title,
    COALESCE(AVG(r.rating), 0)::NUMERIC(3,2) AS avg_rating,
    COUNT(r.id) AS reviews_count
FROM courses c
LEFT JOIN reviews r ON r.course_id = c.id
GROUP BY c.id, c.title;

CREATE OR REPLACE VIEW vw_user_progress AS
SELECT
    u.id AS user_id,
    u.email,
    COUNT(DISTINCT e.id) AS enrollments_count,
    COUNT(DISTINCT pr.id) FILTER (WHERE pr.status = 'completed') AS lessons_completed,
    COUNT(DISTINCT pr.id) FILTER (WHERE pr.status IN ('in_progress','completed')) AS lessons_started
FROM users u
LEFT JOIN enrollments e ON e.user_id = u.id
LEFT JOIN progresses pr ON pr.enrollment_id = e.id
GROUP BY u.id, u.email;
