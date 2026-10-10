from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from .models import Base


def connect(settings):
    sqlite = settings.database_url.startswith('sqlite')
    engine = create_engine(settings.database_url, connect_args={'check_same_thread': False, 'timeout': 30} if sqlite else {}, pool_pre_ping=True)
    if sqlite:
        @event.listens_for(engine, 'connect')
        def setup(dbapi, _):
            dbapi.execute('PRAGMA foreign_keys=ON')
            dbapi.execute('PRAGMA journal_mode=WAL')
    return engine, sessionmaker(engine, expire_on_commit=False)


def initialize(engine):
    Base.metadata.create_all(engine)
    if engine.dialect.name == 'postgresql':
        with engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
            conn.execute(text('''ALTER TABLE incidents ADD COLUMN IF NOT EXISTS location geography(Point,4326)
              GENERATED ALWAYS AS (CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL
              THEN ST_SetSRID(ST_MakePoint(longitude,latitude),4326)::geography ELSE NULL END) STORED'''))
            conn.execute(text('CREATE INDEX IF NOT EXISTS incident_location_gist ON incidents USING GIST(location)'))


def lock_key(db, key):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))'), {'key': key})
