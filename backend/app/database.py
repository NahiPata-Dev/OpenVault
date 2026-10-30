from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.schema import CreateTable
from starlette.requests import Request


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def migrate_legacy_resource_schema(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        _migrate_legacy_postgresql_resources(engine)
        return
    if engine.dialect.name != "sqlite":
        return
    from app.models import Resource

    inspector = inspect(engine)
    if "resources" not in inspector.get_table_names():
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns("resources")
    }
    with engine.connect() as connection:
        resource_sql = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'resources'"
        ).scalar_one()
    required_columns = {column.name for column in Resource.__table__.columns}
    if required_columns <= existing_columns and "'retired'" in resource_sql:
        return

    defaults = {
        "short_summary": "''",
        "description": "''",
        "building": "''",
        "room": "''",
        "address_note": "''",
        "hold_reason": "NULL",
        "capacity": "NULL",
        "quantity": "NULL",
        "allowed_uses": "'[]'",
        "who_can_use": "'[]'",
        "required_training": "'[]'",
        "supervision_required": "0",
        "supervised_windows": "'[]'",
        "usage_rules": "'[]'",
        "safety_notes": "'[]'",
        "max_session_hours": (
            "max_duration_minutes / 60.0"
            if "max_duration_minutes" in existing_columns
            else "NULL"
        ),
        "advance_booking_window": "NULL",
        "cancellation_cutoff": "2",
        "accessories_included": "'[]'",
        "condition_notes": "''",
    }
    upgrade_table = "resources__schema_upgrade"
    raw_connection = engine.raw_connection()
    cursor = raw_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("BEGIN")
        cursor.execute(
            str(CreateTable(Resource.__table__).compile(dialect=engine.dialect))
            .replace("CREATE TABLE resources (", f"CREATE TABLE {upgrade_table} (", 1)
        )
        columns = list(Resource.__table__.columns)
        destinations = ", ".join(f'"{column.name}"' for column in columns)
        expressions = []
        for column in columns:
            if column.name in existing_columns:
                expressions.append(f'"{column.name}"')
            elif column.name in defaults:
                expressions.append(defaults[column.name])
            else:
                raise RuntimeError(
                    f"No migration value is defined for resource column {column.name}."
                )
        cursor.execute(
            f"INSERT INTO {upgrade_table} ({destinations}) "
            f"SELECT {', '.join(expressions)} FROM resources"
        )
        cursor.execute("DROP TABLE resources")
        cursor.execute(f"ALTER TABLE {upgrade_table} RENAME TO resources")
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        raw_connection.close()
    with engine.begin() as connection:
        for index in Resource.__table__.indexes:
            index.create(bind=connection, checkfirst=True)


def _migrate_legacy_postgresql_resources(engine: Engine) -> None:
    from app.models import Resource

    inspector = inspect(engine)
    if "resources" not in inspector.get_table_names():
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns("resources")
    }
    checks = inspector.get_check_constraints("resources")
    status_check = next(
        (
            check.get("sqltext", "")
            for check in checks
            if check.get("name") == "ck_resources_status"
        ),
        "",
    )
    required_columns = {column.name for column in Resource.__table__.columns}
    if required_columns <= existing_columns and "'retired'" in status_check:
        return
    defaults = {
        "short_summary": "''",
        "description": "''",
        "building": "''",
        "room": "''",
        "address_note": "''",
        "hold_reason": "NULL",
        "capacity": "NULL",
        "quantity": "NULL",
        "allowed_uses": "'[]'::json",
        "who_can_use": "'[]'::json",
        "required_training": "'[]'::json",
        "supervision_required": "FALSE",
        "supervised_windows": "'[]'::json",
        "usage_rules": "'[]'::json",
        "safety_notes": "'[]'::json",
        "max_session_hours": (
            '"max_duration_minutes" / 60.0'
            if "max_duration_minutes" in existing_columns
            else "NULL"
        ),
        "advance_booking_window": "NULL",
        "cancellation_cutoff": "2",
        "accessories_included": "'[]'::json",
        "condition_notes": "''",
    }
    missing_columns = [
        column
        for column in Resource.__table__.columns
        if column.name not in existing_columns
    ]
    for column in missing_columns:
        if column.name not in defaults:
            raise RuntimeError(
                f"No migration value is defined for resource column {column.name}."
            )
    with engine.begin() as connection:
        for column in missing_columns:
            sql_type = column.type.compile(dialect=engine.dialect)
            connection.exec_driver_sql(
                f'ALTER TABLE resources ADD COLUMN "{column.name}" {sql_type}'
            )
            connection.exec_driver_sql(
                f'UPDATE resources SET "{column.name}" = {defaults[column.name]}'
            )
            if not column.nullable:
                connection.exec_driver_sql(
                    f'ALTER TABLE resources ALTER COLUMN "{column.name}" SET NOT NULL'
                )
        for constraint_name in (
            "ck_resources_status",
            "ck_resources_hold_review_date",
            "ck_resources_positive_max_duration",
        ):
            connection.exec_driver_sql(
                f"ALTER TABLE resources DROP CONSTRAINT IF EXISTS {constraint_name}"
            )
        connection.exec_driver_sql(
            "ALTER TABLE resources ADD CONSTRAINT ck_resources_status "
            "CHECK (status IN ('active', 'maintenance_hold', 'retired'))"
        )
        connection.exec_driver_sql(
            "ALTER TABLE resources ADD CONSTRAINT ck_resources_hold_review_date "
            "CHECK (status != 'maintenance_hold' OR hold_review_date IS NOT NULL)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE resources ADD CONSTRAINT ck_resources_positive_max_duration "
            "CHECK (max_duration_minutes IS NULL OR max_duration_minutes > 0)"
        )
        for index in Resource.__table__.indexes:
            index.create(bind=connection, checkfirst=True)


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
