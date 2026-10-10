import io
import os
from pathlib import Path
import subprocess
import uuid
import imageio_ffmpeg
from sqlalchemy import select, text
from tests.test_api import app, client, login, report, upload, promote, decision
from api.models import Media, now, Outbox
from api.worker import cleanup, run_once


def test_upload_idempotency(client):
    login(client)
    key = str(uuid.uuid4())
    a, b = upload(client, key), upload(client, key)
    assert a['id'] == b['id']
    response = client.post('/api/media', headers={'x-upload-id': key}, files={'file': ('bad.jpg', b'different', 'image/jpeg')})
    assert response.status_code == 409


def test_cleanup_preserves_linked_evidence(client, app):
    login(client)
    row = report(client)
    staged = upload(client)
    with app.state.sessions() as db:
        for m in db.scalars(select(Media)):
            m.created_at = now() - 8 * 86400
        db.commit()
    assert cleanup(app.state.settings, app.state.sessions) == 1
    assert client.get(row['media'][0]['url']).status_code == 200
    assert client.get(staged['url']).status_code == 404


def test_short_video_is_transcoded_and_private(client, tmp_path):
    login(client)
    binary = imageio_ffmpeg.get_ffmpeg_exe()
    movie = tmp_path / 'sample.mp4'
    subprocess.run([binary, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=320x240:d=1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(movie)], check=True)
    response = client.post('/api/media', headers={'x-upload-id': str(uuid.uuid4())}, files={'file': ('sample.mp4', movie.read_bytes(), 'video/mp4')})
    assert response.status_code == 200, response.text
    assert response.json()['kind'] == 'video'
    url = response.json()['url']
    assert client.get(url).headers['content-type'] == 'video/mp4'
    login(client, '+77010000002')
    assert client.get(url).status_code == 404


def test_bad_and_long_video_rejected(client, tmp_path):
    login(client)
    response = client.post('/api/media', headers={'x-upload-id': str(uuid.uuid4())}, files={'file': ('bad.mp4', b'not-video', 'video/mp4')})
    assert response.status_code == 422
    movie = tmp_path / 'long.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=32x32:d=32', '-c:v', 'libx264', str(movie)], check=True)
    response = client.post('/api/media', headers={'x-upload-id': str(uuid.uuid4())}, files={'file': ('long.mp4', movie.read_bytes(), 'video/mp4')})
    assert response.status_code == 422


def test_inspector_can_correct_geo_without_new_incident(client, app):
    user = login(client)
    row = report(client, False)
    promote(app, user['id'])
    row = decision(client, row, latitude=None, longitude=None, location_verified=False).json()
    payload = {'version': row['incident']['version'], 'latitude': 50.41, 'longitude': 80.25, 'location_verified': True, 'note': 'Уточнено после осмотра'}
    url = '/api/inspector/incidents/' + row['incident_id'] + '/location'
    assert client.post(url, json=payload).status_code == 200
    assert client.post(url, json=payload).status_code == 409
    metrics = client.get('/api/inspector/metrics').json()
    assert (metrics['incidents'], metrics['geolocation_percent']) == (1, 100)


def test_outbox_retry_failure_is_not_delivery(client, app):
    user = login(client)
    row = report(client)
    promote(app, user['id'])
    decision(client, row)
    app.state.settings.integration_mode = 'disabled'
    for _ in range(5):
        with app.state.sessions() as db:
            db.scalar(select(Outbox)).available_at = 0
            db.commit()
        assert run_once(app.state.settings, app.state.sessions)
    result = client.get('/api/reports/' + row['id']).json()['integration']
    assert result['status'] == 'failed'
    assert result['external_id'] is None


def test_postgis_distance_when_available(client, app):
    import pytest
    if app.state.engine.dialect.name != 'postgresql':
        pytest.skip('Requires real PostgreSQL/PostGIS; SQLite does not verify spatial queries')
    user = login(client)
    row = report(client)
    promote(app, user['id'])
    decision(client, row)
    nearby = client.get('/api/inspector/incidents?latitude=50.411&longitude=80.249').json()
    far = client.get('/api/inspector/incidents?latitude=43.25&longitude=76.95').json()
    assert len(nearby) == 1 and far == []
    with app.state.sessions() as db:
        assert db.scalar(text('SELECT PostGIS_Version()'))
