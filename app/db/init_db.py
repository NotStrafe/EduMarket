from pathlib import Path

from app.db.session import engine
from app.db.base import Base
# Import models so they are registered with metadata
from app import models  # noqa: F401


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_sql_file(
            conn, Path(__file__).resolve().parents[2] / "sql" / "002_functions_triggers_views.sql"
        )


async def _apply_sql_file(conn, path: Path) -> None:
    """Execute raw SQL from file to register functions, triggers, and views."""
    if not path.exists():
        return
    sql_text = path.read_text(encoding="utf-8")
    for statement in _split_sql(sql_text):
        await conn.exec_driver_sql(statement)


def _split_sql(sql_text: str) -> list[str]:
    """Split SQL script by semicolons while respecting $$ blocks (plpgsql)."""
    statements: list[str] = []
    buf: list[str] = []
    in_dollar = False
    i = 0
    while i < len(sql_text):
        if sql_text[i : i + 2] == "$$":
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        ch = sql_text[i]
        if ch == ";" and not in_dollar:
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements
