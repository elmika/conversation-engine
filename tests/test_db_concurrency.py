"""Regression test: concurrent writers against the real (file-based) SQLite
engine must not raise "database is locked".

The rest of the suite runs against DATABASE_URL=sqlite:///:memory:, which uses
StaticPool (a single shared connection) — that setup can't reproduce lock
contention at all, since there's only ever one connection. Production uses a
real file with NullPool (a fresh connection per checkout, per db.py), which is
exactly the configuration where two genuinely concurrent connections can
collide. This test drives db.init_engine() against a temp file directly to
exercise that real code path.

Regression, 2026-09-29: 10 concurrent PATCH /conversations/{id} (rename)
requests against the running dev stack reproduced sqlite3.OperationalError:
database is locked on 8/10 of them, in under half a second — nowhere near
pysqlite's default 5s busy timeout, meaning contention wasn't being retried
out at all. Fixed by enabling WAL journal mode (readers no longer block a
writer or vice versa) plus an explicit longer busy_timeout, in db.py.
"""

import threading

import app.infra.persistence.db as db
from app.infra.persistence.unit_of_work import SQLAlchemyUnitOfWork


def test_concurrent_writers_do_not_raise_database_is_locked(tmp_path) -> None:
    saved_engine, saved_session_local = db._engine, db.SessionLocal
    db._engine = None
    db.SessionLocal = None
    try:
        db.init_engine(f"sqlite:///{tmp_path}/concurrency.db")
        db.Base.metadata.create_all(bind=db.get_engine())

        with SQLAlchemyUnitOfWork(db.SessionLocal()) as uow:
            uow.repo.create_conversation_with_id("conv-1", user_id="u1")
            uow.commit()

        errors: list[Exception] = []

        def rename(i: int) -> None:
            try:
                with SQLAlchemyUnitOfWork(db.SessionLocal()) as uow:
                    uow.repo.rename_conversation("conv-1", f"Renamed {i}", "u1")
                    uow.commit()
            except Exception as exc:  # noqa: BLE001 - recording for the assertion below
                errors.append(exc)

        threads = [threading.Thread(target=rename, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"concurrent writers raised: {errors}"
    finally:
        db._engine, db.SessionLocal = saved_engine, saved_session_local
