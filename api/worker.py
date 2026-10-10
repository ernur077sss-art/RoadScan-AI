"""Durable outbox worker. Simulator is deliberately unable to report a real 109 delivery."""
import argparse
import time
from sqlalchemy import select, text, delete
from .config import Settings
from .db import connect
from .models import Incident, Outbox, Media, Challenge, Session, RateBucket, now
from .storage import Storage


def run_once(settings, sessions):
    with sessions() as db:
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        job = db.scalar(select(Outbox).where(Outbox.status == 'queued', Outbox.available_at <= now()).order_by(Outbox.available_at).with_for_update(skip_locked=True).limit(1))
        if not job:
            return False
        incident = db.get(Incident, job.incident_id)
        if not incident or not incident.active:
            job.status = 'cancelled'
        elif settings.integration_mode == 'simulator' and settings.environment != 'production':
            job.attempts += 1
            # Deterministic idempotency key: rerunning cannot create a second simulated delivery.
            job.external_id = 'DEMO-109-' + job.id[:8].upper()
            job.status, job.last_error = 'simulated', None
        else:
            job.attempts += 1
            job.last_error = 'Интеграция 109 не подключена. Реальная отправка не выполнялась.'
            job.available_at = now() + min(3600, 30 * 2 ** min(job.attempts, 7))
            if job.attempts >= 5:
                job.status = 'failed'
        db.commit()
        return True


def cleanup(settings, sessions):
    """Only remove unlinked staged uploads older than 7 days; never delete report evidence."""
    storage = Storage(settings)
    with sessions() as db:
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        rows = db.scalars(select(Media).where(Media.report_id.is_(None), Media.created_at < now() - 7 * 86400).with_for_update(skip_locked=True)).all()
        for row in rows:
            storage.delete(row.id)
            db.delete(row)
        db.execute(delete(Challenge).where(Challenge.expires_at < now() - 86400))
        db.execute(delete(Session).where(Session.expires_at < now()))
        db.execute(delete(RateBucket).where(RateBucket.expires_at < now() - 86400))
        db.commit()
        return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    settings = Settings().prepare()
    engine, sessions = connect(settings)
    if args.cleanup:
        print({'removed_unlinked_uploads': cleanup(settings, sessions)})
        return
    while True:
        run_once(settings, sessions)
        if args.once:
            return
        time.sleep(5)


if __name__ == '__main__':
    main()
