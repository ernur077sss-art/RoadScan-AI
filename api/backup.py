"""Consistent local SQLite backup and non-destructive restore verification.

PostgreSQL/S3 backup is an operator procedure documented in docs/OPERATIONS.md.
The output contains sensitive data and an encryption key; keep it private.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from sqlalchemy.engine import make_url
from .config import Settings


def checksum(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = directory / name
        if not path.is_file() or checksum(path) != expected:
            raise ValueError('Backup file missing or checksum mismatch: ' + name)
    with sqlite3.connect('file:' + str(directory / 'database.sqlite3') + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database foreign key check failed')
        for (media_id,) in db.execute('SELECT id FROM media WHERE report_id IS NOT NULL'):
            if not (directory / 'media' / media_id).is_file():
                raise ValueError('Missing report evidence')
        count = db.execute('SELECT count(*) FROM observations').fetchone()[0]
    return {'verified': True, 'observations': count, 'files': len(manifest['files'])}


def backup(settings, destination):
    url = make_url(settings.database_url)
    if url.drivername != 'sqlite' or settings.storage != 'local':
        raise ValueError('Use the PostgreSQL/S3 procedure for this deployment')
    source = Path(url.database).resolve()
    destination = Path(destination).resolve()
    if not source.is_file():
        raise ValueError('Source database does not exist')
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    db_file = destination / 'database.sqlite3'
    with sqlite3.connect('file:' + str(source) + '?mode=ro', uri=True) as live, sqlite3.connect(db_file) as copied:
        live.backup(copied)
        media_ids = [row[0] for row in copied.execute('SELECT id FROM media')]
    (destination / 'media').mkdir(mode=0o700)
    for media_id in media_ids:
        source_media = settings.data_dir / 'media' / media_id
        if source_media.is_file():
            shutil.copyfile(source_media, destination / 'media' / media_id)
    # Include the effective key even when it came from the environment, never print it.
    (destination / 'session-key').write_text(settings.secret)
    files = {}
    for path in destination.rglob('*'):
        if path.is_file():
            path.chmod(0o600)
            files[str(path.relative_to(destination))] = checksum(path)
    manifest = destination / 'manifest.json'
    manifest.write_text(json.dumps({'format': 1, 'files': files}, indent=2))
    manifest.chmod(0o600)
    return verify(destination)


def main():
    parser = argparse.ArgumentParser(description='Local backup: contains private media and encryption key')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--destination', type=Path, help='New, nonexistent private directory')
    group.add_argument('--verify', type=Path, help='Verify an existing backup without changing live data')
    args = parser.parse_args()
    result = verify(args.verify) if args.verify else backup(Settings().prepare(), args.destination)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
