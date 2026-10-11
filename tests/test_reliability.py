from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import shutil
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from api.backup import backup, verify
from api.main import create_app
from api.models import Session, Observation
from tests.test_api import app, client, login, body, report, decision, promote, HEADERS


def test_simultaneous_submission_creates_one_report(client, app):
    login(client)
    payload = body(client)
    cookie = dict(client.cookies)
    def send():
        with TestClient(app, headers=HEADERS, cookies=cookie) as parallel:
            response = parallel.post('/api/reports', json=payload)
            assert response.status_code == 201, response.text
            return response.json()['id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: send(), range(2)))
    assert ids[0] == ids[1]
    assert len(client.get('/api/reports').json()) == 1


def test_expired_session_and_required_consent(client, app):
    assert client.post('/api/auth/request', json={'phone': '+77010000001', 'consent': False}).status_code == 422
    login(client)
    with app.state.sessions() as db:
        for session in db.scalars(select(Session)):
            session.expires_at = 1
        db.commit()
    assert client.get('/api/reports').status_code == 401


def test_incident_evidence_only_visible_to_inspector(client, app):
    user = login(client)
    row = report(client)
    promote(app, user['id'])
    row = decision(client, row).json()
    url = '/api/inspector/incidents/' + row['incident_id'] + '/observations'
    result = client.get(url)
    assert result.status_code == 200
    assert result.json()[0]['media'][0]['url'] == row['media'][0]['url']
    login(client, '+77010000002')
    assert client.get(url).status_code == 403


def test_backup_can_restore_database_key_media_and_authenticated_read(client, app, tmp_path):
    if app.state.engine.dialect.name != 'sqlite':
        pytest.skip('Local backup helper is SQLite-only; PostgreSQL needs pg_dump rehearsal')
    login(client)
    row = report(client)
    destination = tmp_path / 'backup'
    result = backup(app.state.settings, destination)
    assert result['verified'] and result['observations'] == 1
    restored = tmp_path / 'restored'
    shutil.copytree(destination, restored)
    settings = replace(app.state.settings, data_dir=restored, database_url='sqlite:///' + str(restored / 'database.sqlite3'), secret=(restored / 'session-key').read_text())
    second = create_app(settings)
    with TestClient(second, headers=HEADERS, cookies=dict(client.cookies)) as test:
        assert test.get('/api/auth/me').status_code == 200
        assert test.get('/api/reports/' + row['id']).json()['id'] == row['id']
        assert test.get(row['media'][0]['url']).status_code == 200
    media = next((destination / 'media').iterdir())
    media.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='checksum'):
        verify(destination)


def test_stream_body_limit_counts_bytes_even_with_false_content_length(client, app):
    # Isolated middleware contract: no 26 MB allocation needed in the test.
    import asyncio
    from api.body_limit import BodyLimitMiddleware
    delivered = []
    async def consumer(scope, receive, send):
        await receive()
        await receive()
        raise AssertionError('Oversized second chunk must not reach the parser')
    chunks = iter([{'type': 'http.request', 'body': b'123456', 'more_body': True}, {'type': 'http.request', 'body': b'789012', 'more_body': False}])
    async def receive():
        return next(chunks)
    async def send(message):
        delivered.append(message)
    asyncio.run(BodyLimitMiddleware(consumer, 10)({'type': 'http', 'method': 'POST'}, receive, send))
    assert delivered[0]['status'] == 413


def test_private_s3_response_range_and_authorization(client, app):
    from io import BytesIO
    from botocore.response import StreamingBody
    login(client)
    row = report(client)
    class PrivateBucket:
        def get_object(self, **kwargs):
            assert kwargs['Key'] == row['media'][0]['id']
            assert kwargs['Range'] == 'bytes=2-4'
            return {'ContentLength': 3, 'ContentRange': 'bytes 2-4/9', 'Body': StreamingBody(BytesIO(b'234'), 3)}
    app.state.settings.storage = 's3'
    app.state.storage.client = PrivateBucket()
    result = client.get(row['media'][0]['url'], headers={'Range': 'bytes=2-4'})
    assert result.status_code == 206 and result.content == b'234'
    assert result.headers['content-range'] == 'bytes 2-4/9'
    assert result.headers['cache-control'] == 'no-store'
    login(client, '+77010000002')
    assert client.get(row['media'][0]['url'], headers={'Range': 'bytes=2-4'}).status_code == 404


def test_frozen_initial_migration_can_start_application(tmp_path):
    import os
    import subprocess
    import sys
    from api.config import Settings
    database_url = 'sqlite:///' + str(tmp_path / 'migrated.db')
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env={**os.environ, 'ROADSCAN_DATABASE_URL': database_url, 'ROADSCAN_DATA_DIR': str(tmp_path), 'ROADSCAN_ENV': 'test'}, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    settings = Settings(auth_mode='otp', environment='test', database_url=database_url, data_dir=tmp_path)
    with TestClient(create_app(settings), headers=HEADERS) as migrated:
        login(migrated)
        assert report(migrated)['status'] == 'pending'


def test_failed_sms_bridge_invalidates_challenge_and_never_exposes_code(client, app, monkeypatch):
    import httpx
    from api.models import Challenge
    app.state.settings.sms_mode = 'bridge'
    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: httpx.Response(200, json={'accepted': False}, request=httpx.Request('POST', 'https://sms.example/send')))
    result = client.post('/api/auth/request', json={'phone': '+77010000001', 'consent': True})
    assert result.status_code == 503
    assert 'development_code' not in result.text
    with app.state.sessions() as db:
        assert db.scalar(select(Challenge)).used


def test_successful_sms_bridge_uses_real_verification_without_development_code(client, app, monkeypatch):
    import httpx
    import re
    app.state.settings.sms_mode = 'bridge'
    sent = {}
    def send(*args, **kwargs):
        sent.update(kwargs['json'])
        return httpx.Response(200, json={'accepted': True}, request=httpx.Request('POST', 'https://sms.example/send'))
    monkeypatch.setattr(httpx, 'post', send)
    response = client.post('/api/auth/request', json={'phone': '+77010000001', 'consent': True})
    assert response.status_code == 200
    payload = response.json()
    assert 'development_code' not in payload
    code = re.search(r'код (\d{6})', sent['text']).group(1)
    assert client.post('/api/auth/verify', json={'challenge_id': payload['challenge_id'], 'code': code}).status_code == 200
