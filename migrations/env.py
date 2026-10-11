from alembic import context
from api.config import Settings
from api.db import connect
from api.models import Base


def run_online(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    settings = Settings().prepare()
    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = context.config.attributes.get('connection')
    if supplied_connection is not None:
        run_online(supplied_connection)
    else:
        engine, _ = connect(Settings().prepare())
        try:
            with engine.connect() as connection:
                run_online(connection)
        finally:
            engine.dispose()
