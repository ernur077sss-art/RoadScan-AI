import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.config import Settings
from api.main import create_app
from api.models import User, RateBucket
from api.passwords import hash_password, verify_password
from tests.test_api import app, client, login, report, HEADERS

PASSWORD = 'Длинный тестовый пароль! '
PHONE = '+77010000001'


def register(client, phone=PHONE, **extra):
    return client.post('/api/auth/register', json={'phone': phone, 'password': PASSWORD, 'consent': True, **extra})


def test_password_registration_login_and_private_report_survive_restart(app, client):
    app.state.settings.auth_mode = 'password'
    result = register(client)
    assert result.status_code == 201, result.text
    user_id = result.json()['id']
    first_cookie = client.cookies.get('roadscan_session')
    assert 'httponly' in result.headers['set-cookie'].lower()
    assert client.get('/api/auth/me').json()['phone_verified'] is False
    row = report(client)
    with app.state.sessions() as db:
        user = db.get(User, user_id)
        assert PASSWORD not in user.password_hash
        assert PHONE not in user.phone_encrypted
        assert user.role == 'citizen'
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me').status_code == 401
    restarted = create_app(app.state.settings)
    with TestClient(restarted, headers=HEADERS) as restored:
        assert restored.post('/api/auth/login', json={'phone': PHONE, 'password': PASSWORD}).status_code == 200
        assert restored.cookies.get('roadscan_session') != first_cookie
        assert restored.get('/api/reports/' + row['id']).status_code == 200
        assert restored.get('/api/inspector/reports').status_code == 403


def test_invalid_passwords_unknown_accounts_and_durable_limits(app, client):
    app.state.settings.auth_mode = 'password'
    assert register(client).status_code == 201
    assert client.post('/api/auth/logout').status_code == 200
    wrong = client.post('/api/auth/login', json={'phone': PHONE, 'password': PASSWORD.strip()})
    unknown = client.post('/api/auth/login', json={'phone': '+77010000002', 'password': PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    for _ in range(3):
        assert client.post('/api/auth/login', json={'phone': PHONE, 'password': 'wrong'}).status_code == 401
    restarted = create_app(app.state.settings)
    with TestClient(restarted, headers=HEADERS) as restored:
        blocked = restored.post('/api/auth/login', json={'phone': PHONE, 'password': PASSWORD})
        assert blocked.status_code == 429
        assert 'retry-after' in blocked.headers


def test_no_otp_bypass_or_account_takeover(app, client):
    old_user = login(client)
    app.state.settings.auth_mode = 'password'
    assert register(client).status_code == 409
    assert client.post('/api/auth/login', json={'phone': PHONE, 'password': PASSWORD}).status_code == 401
    with app.state.sessions() as db:
        assert db.get(User, old_user['id']).password_hash is None
    assert client.post('/api/auth/request', json={'phone': PHONE, 'consent': True}).status_code == 404
    assert client.post('/api/auth/verify', json={'challenge_id': '00000000-0000-0000-0000-000000000000', 'code': '123456'}).status_code == 404
    assert client.get('/api/health').json()['sms'] == 'disabled'


def test_password_validation_csrf_and_duplicate_registration(app, client):
    # Password endpoints cannot silently activate in an OTP deployment.
    assert register(client).status_code == 404
    app.state.settings.auth_mode = 'password'
    assert register(client, consent=False).status_code == 422
    assert register(client, password='short').status_code == 422
    assert register(client, role='admin').status_code == 422
    assert client.post('/api/auth/register', json={'phone': PHONE, 'password': PASSWORD, 'consent': True}, headers={'origin': 'https://wrong.example'}).status_code == 403
    first = register(client)
    assert first.status_code == 201
    assert register(client, password='Another password with 15+').status_code == 409
    with app.state.sessions() as db:
        assert len(db.scalars(select(User)).all()) == 1
    assert client.post('/api/auth/login', json={'phone': PHONE, 'password': PASSWORD}).status_code == 200


def test_hashes_are_salted_and_preserve_unicode_and_whitespace():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert verify_password(PASSWORD, first)
    assert not verify_password(PASSWORD.strip(), first)
    assert not verify_password(PASSWORD, None)
    assert not verify_password(PASSWORD, 'broken')


def test_production_password_mode_does_not_require_sms_but_keeps_storage_guards(tmp_path):
    settings = Settings(environment='production', auth_mode='password', secret='x' * 48, data_dir=tmp_path, origin='https://roadscan.example', database_url='postgresql+psycopg://not-connected', storage='s3', s3_bucket='private')
    assert settings.prepare().sms_mode == 'development'
    settings.auth_mode = 'otp'
    with pytest.raises(ValueError, match='SMS bridge'):
        settings.prepare()
    settings.auth_mode, settings.storage = 'password', 'local'
    with pytest.raises(ValueError, match='private S3'):
        settings.prepare()


@pytest.mark.parametrize(('environment', 'origin'), [('production', 'http://localhost:3000'), ('development', 'https://phone-preview.example')])
def test_production_and_https_preview_password_cookies_are_secure(app, client, environment, origin):
    app.state.settings.auth_mode = 'password'
    app.state.settings.environment = environment
    app.state.settings.origin = origin
    with TestClient(app, base_url=origin, headers={'origin': origin, 'x-roadscan-request': '1'}) as preview:
        result = register(preview)
        if origin.startswith('https://'):
            assert preview.get('/api/auth/me').status_code == 200
            assert preview.post('/api/auth/logout', headers={'origin': 'https://wrong.example'}).status_code == 403
            assert preview.post('/api/auth/logout').status_code == 200
    assert result.status_code == 201
    cookie = result.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
