from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.database import Base
from app.models import db_models  # noqa: F401  (registers tables)

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Ignore PostGIS/Tiger internal tables
    if type_ == "table" and reflected and compare_to is None:
        return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def run_migrations_online() -> None:
    url = context.config.get_main_option("sqlalchemy.url") or get_settings().database_url
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_object=include_object,
                          process_revision_directives=alembic_helpers.writer,
                          render_item=alembic_helpers.render_item)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
