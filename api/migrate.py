"""Run release migrations with one PostgreSQL session lock across replicas."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from .config import Settings
from .db import connect


def upgrade(settings=None):
    settings = (settings or Settings()).prepare()
    engine, _ = connect(settings)
    config = Config(str(Path(__file__).resolve().parent.parent / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).resolve().parent.parent / 'migrations'))
    try:
        with engine.connect() as connection:
            postgres = engine.dialect.name == 'postgresql'
            if postgres:
                connection.execute(text("SELECT pg_advisory_lock(hashtextextended('roadscan:release-migrations', 0))"))
                connection.commit()
            try:
                # Alembic must use this connection, which holds the session lock.
                config.attributes['connection'] = connection
                command.upgrade(config, 'head')
                connection.commit()
            finally:
                connection.rollback()
                if postgres:
                    connection.execute(text("SELECT pg_advisory_unlock(hashtextextended('roadscan:release-migrations', 0))"))
                    connection.commit()
    finally:
        engine.dispose()


if __name__ == '__main__':
    upgrade()
