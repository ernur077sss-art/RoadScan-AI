from urllib.parse import urlparse, parse_qs
from pathlib import Path
from alembic import command
from alembic.config import Config
import pytest

from sqlalchemy import create_engine, text

from api.config import Settings
from api.migrate import upgrade
from api.storage import Storage


def test_separate_database_password_reaches_driver_unchanged(tmp_path, monkeypatch):
    password = '  test:@/%?#&+ пароль  '
    monkeypatch.setenv('ROADSCAN_DATABASE_URL', 'postgresql+psycopg://postgres.project@pooler.test:5432/postgres?sslmode=require')
    monkeypatch.setenv('ROADSCAN_DATABASE_PASSWORD', password)
    settings = Settings(environment='test', data_dir=tmp_path).prepare()
    # prepare runs both on API startup and before release migrations.
    settings.prepare()
    engine = create_engine(settings.database_url)
    _, args = engine.dialect.create_connect_args(engine.url)
    assert args['password'] == password
    assert args['host'] == 'pooler.test'
    assert args['user'] == 'postgres.project'
    assert args['sslmode'] == 'require'
    assert password not in repr(settings)
    assert settings.database_url not in repr(settings)
    engine.dispose()


def test_separate_password_does_not_silently_change_sqlite_config(tmp_path):
    with pytest.raises(ValueError, match='requires PostgreSQL'):
        Settings(environment='test', data_dir=tmp_path, database_password='test-only').prepare()


def test_release_migration_is_repeatable_and_preserves_existing_rows(tmp_path):
    settings = Settings(environment='test', database_url='sqlite:///' + str(tmp_path / 'release.db'), data_dir=tmp_path)
    upgrade(settings)
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO rate_buckets (id, count, expires_at) VALUES ('kept', 1, 9999999999)"))
    upgrade(settings)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count FROM rate_buckets WHERE id = 'kept'")).scalar_one() == 1
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    engine.dispose()


def test_password_migration_preserves_legacy_account_without_claiming_phone(tmp_path):
    settings = Settings(environment='test', database_url='sqlite:///' + str(tmp_path / 'old.db'), data_dir=tmp_path)
    engine = create_engine(settings.database_url)
    config = Config(str(Path(__file__).resolve().parent.parent / 'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0001')
        connection.execute(text("INSERT INTO users (id, phone_key, phone_encrypted, role, created_at, consent_version, consent_at) VALUES ('legacy', 'key', 'encrypted', 'inspector', 1, 'pilot-v1', 1)"))
    upgrade(settings)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT role, password_hash, phone_verified FROM users WHERE id = 'legacy'")).one()
        assert row == ('inspector', None, False)
    engine.dispose()


def test_custom_s3_preserves_supabase_prefix_and_uses_private_signed_access(tmp_path, monkeypatch):
    # No network or real credentials: inspect the actual botocore signer result.
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test-only-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test-only-secret')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'eu-central-1')
    settings = Settings(environment='test', data_dir=tmp_path, storage='s3', s3_endpoint='https://test-ref.storage.supabase.co/storage/v1/s3', s3_bucket='evidence')
    storage = Storage(settings)
    url = urlparse(storage.presigned('private-object'))
    assert url.netloc == 'test-ref.storage.supabase.co'
    assert url.path == '/storage/v1/s3/evidence/private-object'
    params = parse_qs(url.query)
    assert params['X-Amz-Algorithm'] == ['AWS4-HMAC-SHA256']
    assert params['X-Amz-Expires'] == ['60']
