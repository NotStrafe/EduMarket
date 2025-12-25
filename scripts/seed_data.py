"""Seed the database with realistic demo data.

Usage: python scripts/seed_data.py

Creates:
- roles, users (admins/teachers/students with hashed passwords)
- courses with modules/lessons
- enrollments and progress
- orders, order_items (~6000+), payments
- reviews, import jobs/errors samples

Idempotent for dev: truncates tables before insert (CASCADE).
"""

import asyncio
import random
from datetime import datetime, timedelta
from decimal import Decimal

from passlib.hash import bcrypt
from sqlalchemy import text

from app import models
from app.db.base import Base
from app.db.session import SessionLocal, engine

random.seed(42)

PASSWORD = "password123"
HASHED_PASSWORD = bcrypt.hash(PASSWORD)

NUM_ADMINS = 2
NUM_TEACHERS = 15
NUM_STUDENTS = 250
NUM_COURSES = 50
# 1700 orders * min 3 items ≈ 5100+ order_items to satisfy 5000+ transactional rows
ORDERS_COUNT = 1700


async def reset_db() -> None:
    async with SessionLocal() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE "
                "audit_log, import_job_errors, import_jobs, payments, order_items, orders,"
                " progresses, enrollments, reviews, lessons, course_modules, courses, users, roles"
                " RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()


async def seed_roles(session) -> dict[str, models.Role]:
    roles = [
        models.Role(name="admin", description="Administrator"),
        models.Role(name="teacher", description="Teacher"),
        models.Role(name="student", description="Student"),
    ]
    session.add_all(roles)
    await session.commit()
    return {r.name: r for r in roles}


async def seed_users(session, roles: dict[str, models.Role]):
    users: list[models.User] = []

    def build_user(email: str, full_name: str, role: models.Role) -> models.User:
        return models.User(
            email=email,
            full_name=full_name,
            hashed_password=HASHED_PASSWORD,
            role_id=role.id,
        )

    # Admins
    for idx in range(NUM_ADMINS):
        users.append(build_user(
            f"admin{idx+1}@example.com", f"Admin {idx+1}", roles["admin"]))

    # Teachers
    for idx in range(NUM_TEACHERS):
        users.append(
            build_user(
                f"teacher{idx+1}@example.com",
                f"Teacher {idx+1}",
                roles["teacher"],
            )
        )

    # Students
    for idx in range(NUM_STUDENTS):
        users.append(
            build_user(
                f"student{idx+1}@example.com",
                f"Student {idx+1}",
                roles["student"],
            )
        )

    session.add_all(users)
    await session.commit()
    return users


async def seed_courses(session, teachers: list[models.User]):
    courses: list[models.Course] = []
    modules: list[models.CourseModule] = []
    lessons: list[models.Lesson] = []
    course_lessons: dict[int, list[models.Lesson]] = {}

    for idx in range(NUM_COURSES):
        author = random.choice(teachers)
        course = models.Course(
            title=f"Course {idx+1}",
            description="Comprehensive course on topic #{idx+1}",
            price=Decimal(random.randint(0, 150)) + Decimal("0.99"),
            status="published",
            author_id=author.id,
        )
        courses.append(course)
    session.add_all(courses)
    await session.flush()

    for course in courses:
        module_count = random.randint(3, 5)
        for m_idx in range(module_count):
            module = models.CourseModule(
                course_id=course.id,
                title=f"Module {m_idx+1} of {course.title}",
                description="Module description",
                position=m_idx + 1,
            )
            modules.append(module)
    session.add_all(modules)
    await session.flush()

    module_groups: dict[int, list[models.CourseModule]] = {}
    for module in modules:
        module_groups.setdefault(module.course_id, []).append(module)

    for course in courses:
        course_lessons[course.id] = []
        for module in module_groups.get(course.id, []):
            lesson_count = random.randint(3, 6)
            for l_idx in range(lesson_count):
                lesson = models.Lesson(
                    course_id=course.id,
                    module_id=module.id,
                    title=f"Lesson {l_idx+1} in {module.title}",
                    content="Lesson content",
                    position=l_idx + 1,
                    duration_minutes=random.randint(5, 25),
                )
                lessons.append(lesson)
                course_lessons[course.id].append(lesson)
    session.add_all(lessons)
    await session.commit()
    return courses, course_lessons


async def seed_enrollments(session, students: list[models.User], courses: list[models.Course]):
    enrollments: list[models.Enrollment] = []
    for student in students:
        for course in random.sample(courses, k=random.randint(5, 10)):
            started_at = datetime.utcnow() - timedelta(days=random.randint(1, 120))
            status = random.choices(
                population=["active", "completed", "cancelled"],
                weights=[0.6, 0.3, 0.1],
                k=1,
            )[0]
            completed_at = started_at + \
                timedelta(days=random.randint(5, 40)
                          ) if status == "completed" else None
            enrollments.append(
                models.Enrollment(
                    user_id=student.id,
                    course_id=course.id,
                    status=status,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            )
    session.add_all(enrollments)
    await session.commit()
    return enrollments


async def seed_progresses(session, enrollments, course_lessons):
    progresses: list[models.Progress] = []
    for enrollment in enrollments:
        lessons = course_lessons.get(enrollment.course_id, [])
        if not lessons:
            continue
        sampled_lessons = random.sample(
            lessons, k=min(len(lessons), random.randint(3, 10)))
        for lesson in sampled_lessons:
            status = random.choices(
                population=["not_started", "in_progress", "completed"],
                weights=[0.2, 0.3, 0.5],
                k=1,
            )[0]
            completed_at = datetime.utcnow() - timedelta(days=random.randint(0, 30)
                                                         ) if status == "completed" else None
            score = random.randint(60, 100) if status == "completed" else None
            progresses.append(
                models.Progress(
                    enrollment_id=enrollment.id,
                    lesson_id=lesson.id,
                    status=status,
                    score=score,
                    completed_at=completed_at,
                )
            )
    session.add_all(progresses)
    await session.commit()
    return progresses


async def seed_orders_payments(session, students, courses):
    orders: list[models.Order] = []
    order_items: list[models.OrderItem] = []
    payments: list[models.Payment] = []

    for _ in range(ORDERS_COUNT):
        user = random.choice(students)
        order = models.Order(
            user_id=user.id, status="pending", total_amount=Decimal("0"))
        orders.append(order)
    session.add_all(orders)
    await session.flush()

    for order in orders:
        chosen_courses = random.sample(courses, k=random.randint(3, 5))
        total = Decimal("0")
        for course in chosen_courses:
            quantity = 1
            price = course.price
            total += price * quantity
            order_items.append(
                models.OrderItem(
                    order_id=order.id,
                    course_id=course.id,
                    quantity=quantity,
                    price=price,
                )
            )
        order.total_amount = total
        order_status = random.choices(
            population=["paid", "pending", "cancelled", "refunded"],
            weights=[0.75, 0.1, 0.1, 0.05],
            k=1,
        )[0]
        order.status = order_status

        if order_status == "paid":
            payment_status = "paid"
        elif order_status == "refunded":
            payment_status = "refunded"
        elif order_status == "pending":
            payment_status = "pending"
        else:  # cancelled
            payment_status = "failed"

        paid_at = datetime.utcnow() if payment_status in {"paid", "refunded"} else None
        payments.append(
            models.Payment(
                order_id=order.id,
                amount=total,
                status=payment_status,
                provider=random.choice(["stripe", "paypal", "yookassa", None]),
                transaction_id=f"txn_{order.id}",
                paid_at=paid_at,
            )
        )

    session.add_all(order_items)
    session.add_all(payments)
    await session.commit()
    return orders, order_items, payments


async def seed_reviews(session, enrollments):
    reviews: list[models.Review] = []
    for enrollment in enrollments:
        if random.random() < 0.35:
            reviews.append(
                models.Review(
                    user_id=enrollment.user_id,
                    course_id=enrollment.course_id,
                    rating=random.randint(3, 5),
                    comment="Great course!",
                )
            )
    session.add_all(reviews)
    await session.commit()
    return reviews


async def seed_import_jobs(session):
    jobs = [
        models.ImportJob(
            job_type="courses",
            status="completed",
            params={"source": "csv"},
            total_records=200,
            processed_records=200,
            errors_count=0,
            started_at=datetime.utcnow() - timedelta(days=2),
            finished_at=datetime.utcnow() - timedelta(days=2, minutes=-5),
        ),
        models.ImportJob(
            job_type="users",
            status="failed",
            params={"source": "csv"},
            total_records=300,
            processed_records=180,
            errors_count=5,
            started_at=datetime.utcnow() - timedelta(days=1),
            finished_at=datetime.utcnow() - timedelta(days=1, minutes=-3),
        ),
    ]
    session.add_all(jobs)
    await session.flush()

    errors = [
        models.ImportJobError(
            job_id=jobs[1].id,
            row_number=42,
            error_message="Invalid email format",
            payload={"email": "bad@"},
        ),
        models.ImportJobError(
            job_id=jobs[1].id,
            row_number=128,
            error_message="Missing required field full_name",
            payload={"email": "user128@example.com"},
        ),
    ]
    session.add_all(errors)
    await session.commit()


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await reset_db()

    async with SessionLocal() as session:
        roles = await seed_roles(session)
        users = await seed_users(session, roles)

        teachers = [u for u in users if u.role_id == roles["teacher"].id]
        students = [u for u in users if u.role_id == roles["student"].id]

        courses, course_lessons = await seed_courses(session, teachers)
        enrollments = await seed_enrollments(session, students, courses)
        await seed_progresses(session, enrollments, course_lessons)
        await seed_orders_payments(session, students, courses)
        await seed_reviews(session, enrollments)
        await seed_import_jobs(session)

    print(
        "Seed completed: roles/users/courses/modules/lessons/enrollments/"
        "progresses/orders/order_items/payments/reviews/import jobs"
    )


if __name__ == "__main__":
    asyncio.run(main())
