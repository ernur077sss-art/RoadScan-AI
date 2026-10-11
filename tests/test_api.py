import io
from pathlib import Path
import uuid
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import select
from api.config import Settings
from api.main import create_app
from api.models import User, Challenge, Incident, Observation, Outbox, Media
from api.worker import run_once

ORIGIN = 'http://localhost:3000'
HEADERS = {'origin': ORIGIN, 'x-roadscan-request': '1'}


@pytest.fixture
def app(tmp_path):
    import os
    database_url = os.getenv('ROADSCAN_TEST_DATABASE_URL', 'sqlite:///' + str(tmp_path / 'test.db'))
    settings = Settings(auth_mode='otp', environment='test', database_url=database_url, origin=ORIGIN, data_dir=tmp_path, secret='testing-secret-never-use-outside-tests-123456789', integration_mode='simulator')
    app = create_app(settings)
    if database_url.startswith('postgresql'):
        from api.models import Base
        Base.metadata.drop_all(app.state.engine)
    return app


@pytest.fixture
def client(app):
    with TestClient(app, headers=HEADERS) as client:
        yield client


def login(client, phone='+77010000001'):
    challenge = client.post('/api/auth/request', json={'phone': phone, 'consent': True})
    assert challenge.status_code == 200, challenge.text
    data = challenge.json()
    result = client.post('/api/auth/verify', json={'challenge_id': data['challenge_id'], 'code': data['development_code']})
    assert result.status_code == 200, result.text
    return result.json()


def promote(app, user_id, role='inspector'):
    with app.state.sessions() as db:
        db.get(User, user_id).role = role
        db.commit()


def upload(client, key=None):
    image = io.BytesIO()
    Image.new('RGB', (32, 32), 'gray').save(image, format='JPEG')
    result = client.post('/api/media', headers={'x-upload-id': key or str(uuid.uuid4())}, files={'file': ('road.jpg', image.getvalue(), 'image/jpeg')})
    assert result.status_code == 200, result.text
    return result.json()


def body(client, point=True):
    return {'event_id': str(uuid.uuid4()), 'category': 'pothole', 'description': 'Яма на проезжей части', 'address': 'Семей, улица Абая', 'latitude': 50.411 if point else None, 'longitude': 80.249 if point else None, 'location_source': 'manual' if point else 'unknown', 'media_ids': [upload(client)['id']]}


def report(client, point=True):
    response = client.post('/api/reports', json=body(client, point))
    assert response.status_code == 201, response.text
    return response.json()


def decision(client, row, **kwargs):
    payload = {'version': row['version'], 'status': 'confirmed', 'note': 'Дефект подтверждён инспектором', 'latitude': 50.411, 'longitude': 80.249, 'location_verified': True, **kwargs}
    return client.post('/api/inspector/reports/' + row['id'] + '/decision', json=payload)


def test_otp_replay_and_logout(client):
    data = client.post('/api/auth/request', json={'phone': '+77010000001', 'consent': True}).json()
    payload = {'challenge_id': data['challenge_id'], 'code': data['development_code']}
    assert client.post('/api/auth/verify', json=payload).status_code == 200
    assert client.post('/api/auth/verify', json=payload).status_code == 400
    assert client.get('/api/auth/me').status_code == 200
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me').status_code == 401


def test_expired_and_attempt_limited_otp(client, app):
    d = client.post('/api/auth/request', json={'phone': '+77010000001', 'consent': True}).json()
    wrong = '111111' if d['development_code'] != '111111' else '222222'
    for _ in range(5):
        assert client.post('/api/auth/verify', json={'challenge_id': d['challenge_id'], 'code': wrong}).status_code == 400
    assert client.post('/api/auth/verify', json={'challenge_id': d['challenge_id'], 'code': d['development_code']}).status_code == 400
    d = client.post('/api/auth/request', json={'phone': '+77010000002', 'consent': True}).json()
    with app.state.sessions() as db:
        db.get(Challenge, d['challenge_id']).expires_at = 1
        db.commit()
    assert client.post('/api/auth/verify', json={'challenge_id': d['challenge_id'], 'code': d['development_code']}).status_code == 400


def test_sms_rate_and_csrf(client):
    payload = {'phone': '+77010000001', 'consent': True}
    assert client.post('/api/auth/request', json=payload, headers={'origin': 'https://evil.example'}).status_code == 403
    assert client.post('/api/auth/request', json=payload).status_code == 200
    assert client.post('/api/auth/request', json=payload).status_code == 429


def test_cannot_self_promote_or_access_others(client, app):
    first = login(client)
    row = report(client)
    media_id = row['media'][0]['id']
    login(client, '+77010000002')
    assert client.get('/api/reports/' + row['id']).status_code == 404
    assert client.get('/api/media/' + media_id).status_code == 404
    assert client.get('/api/inspector/reports').status_code == 403
    assert client.post('/api/admin/users/' + first['id'] + '/role', json={'role': 'admin'}).status_code == 403
    payload = {'phone': '+77010000003', 'consent': True, 'role': 'admin'}
    assert client.post('/api/auth/request', json=payload).status_code == 422


def test_idempotency_does_not_reset_received_at(client):
    login(client)
    payload = body(client)
    first = client.post('/api/reports', json=payload).json()
    second = client.post('/api/reports', json=payload).json()
    assert first['id'] == second['id']
    assert first['received_at'] == second['received_at']
    assert len(client.get('/api/reports').json()) == 1
    payload['description'] = 'Другой дефект'
    assert client.post('/api/reports', json=payload).status_code == 409


def test_media_must_be_owned_and_valid(client, app):
    login(client)
    existing = upload(client)
    login(client, '+77010000002')
    payload = body(client)
    payload['media_ids'] = [existing['id']]
    assert client.post('/api/reports', json=payload).status_code == 422
    assert client.post('/api/media', headers={'x-upload-id': str(uuid.uuid4())}, files={'file': ('bad.jpg', b'<script>bad</script>', 'image/jpeg')}).status_code == 422


def test_full_cycle_clarification_and_stale_decision(client, app):
    user = login(client)
    row = report(client)
    promote(app, user['id'])
    response = decision(client, row, status='needs_info', location_verified=False, note='Уточните ориентир')
    assert response.status_code == 200
    assert decision(client, row).status_code == 409
    updated = response.json()
    response = client.post('/api/reports/' + row['id'] + '/clarify', json={'version': updated['version'], 'note': 'Рядом с остановкой', 'address': 'Семей, Абая, остановка', 'latitude': 50.411, 'longitude': 80.249})
    assert response.status_code == 200
    assert response.json()['status'] == 'pending'
    response = decision(client, response.json())
    assert response.status_code == 200
    assert len(response.json()['history']) == 4


def test_kpi_unique_incidents_missing_geo_and_relink(client, app):
    user = login(client)
    a, b, c = report(client), report(client), report(client, False)
    promote(app, user['id'])
    assert client.get('/api/inspector/metrics').json()['geolocation_percent'] is None
    a = decision(client, a).json()
    b = decision(client, b, incident_id=a['incident_id']).json()
    c = decision(client, c, latitude=None, longitude=None, location_verified=False).json()
    kpi = client.get('/api/inspector/metrics').json()
    assert (kpi['incidents'], kpi['verified'], kpi['geolocation_percent']) == (2, 1, 50.0)
    b = decision(client, b, incident_id=None).json()
    assert client.get('/api/inspector/metrics').json()['incidents'] == 3
    b = decision(client, b, incident_id=a['incident_id']).json()
    assert client.get('/api/inspector/metrics').json()['incidents'] == 2
    assert client.get('/api/inspector/metrics?date_from=9999999999').json()['geolocation_percent'] is None


def test_invalid_coordinates(client):
    login(client)
    payload = body(client)
    payload['latitude'] = 100
    assert client.post('/api/reports', json=payload).status_code == 422
    payload['latitude'] = None
    assert client.post('/api/reports', json=payload).status_code == 422


def test_simulator_never_reports_real_delivery(client, app):
    user = login(client)
    row = report(client)
    promote(app, user['id'])
    row = decision(client, row).json()
    assert row['integration']['status'] == 'queued'
    assert run_once(app.state.settings, app.state.sessions)
    assert not run_once(app.state.settings, app.state.sessions)
    result = client.get('/api/reports/' + row['id']).json()
    assert result['integration']['status'] == 'simulated'
    assert result['integration']['external_id'].startswith('DEMO-109-')


def test_phone_is_encrypted(client, app):
    user = login(client)
    with app.state.sessions() as db:
        stored = db.get(User, user['id'])
        assert '+77010000001' not in stored.phone_encrypted


def test_production_cannot_use_test_auth(tmp_path):
    with pytest.raises(ValueError):
        Settings(auth_mode='otp', environment='production', secret='x' * 48, data_dir=tmp_path, origin='https://roadscan.example').prepare()


def test_persistence_after_restart(client, app):
    user = login(client)
    row = report(client)
    second = create_app(app.state.settings)
    with TestClient(second, headers=HEADERS) as restored:
        restored.cookies.update(client.cookies)
        assert restored.get('/api/reports/' + row['id']).json()['id'] == row['id']
