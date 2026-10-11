import argparse
from sqlalchemy import select
from .config import Settings
from .db import connect, initialize
from .models import User, Audit
from .security import normalize_phone, digest, cipher
from .passwords import validate_role_password


def main():
    parser = argparse.ArgumentParser(description='RoadScan operator CLI (host access required)')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    grant = sub.add_parser('grant-role')
    grant.add_argument('--phone', required=True)
    grant.add_argument('--role', choices=['citizen', 'inspector', 'admin'], required=True)
    args = parser.parse_args()
    settings = Settings().prepare()
    engine, sessions = connect(settings)
    if args.command == 'init':
        if settings.environment == 'production':
            parser.error('Use alembic upgrade head in production')
        initialize(engine)
        print('Database initialized. No demo reports created.')
        return
    with sessions() as db:
        key = digest(settings, 'phone:' + normalize_phone(args.phone))
        user = db.scalar(select(User).where(User.phone_key == key))
        if not user:
            parser.error('User must sign in and accept consent first')
        try:
            validate_role_password(user.password_hash, args.role)
        except ValueError as exc:
            parser.error(str(exc))
        old = user.role
        user.role = args.role
        db.add(Audit(action='operator_role_changed', note='Role updated by host operator', details='{"user_id":"' + user.id + '","before":"' + old + '","after":"' + args.role + '"}'))
        db.commit()
        print(f'Role updated: {args.role}. Phone not printed.')


if __name__ == '__main__':
    main()
