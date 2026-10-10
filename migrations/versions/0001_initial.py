"""Frozen initial schema; PostGIS geography and GiST index on PostgreSQL.
Revision ID: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('incidents',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('location_verified', sa.Boolean(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.Column('first_received_at', sa.Integer(), nullable=False),
    sa.CheckConstraint('(latitude IS NULL) = (longitude IS NULL)', name='paired_coordinates'),
    sa.CheckConstraint('NOT location_verified OR latitude IS NOT NULL', name='verified_has_point'),
    sa.CheckConstraint('latitude BETWEEN -90 AND 90', name='incident_lat_range'),
    sa.CheckConstraint('longitude BETWEEN -180 AND 180', name='incident_lon_range'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_incidents_active'), 'incidents', ['active'], unique=False)
    op.create_index(op.f('ix_incidents_created_at'), 'incidents', ['created_at'], unique=False)
    op.create_table('otp_challenges',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('phone_key', sa.String(length=64), nullable=False),
    sa.Column('phone_encrypted', sa.Text(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.Integer(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('used', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_otp_challenges_phone_key'), 'otp_challenges', ['phone_key'], unique=False)
    op.create_table('rate_buckets',
    sa.Column('id', sa.String(length=128), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('phone_key', sa.String(length=64), nullable=False),
    sa.Column('phone_encrypted', sa.Text(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.Column('consent_version', sa.String(length=40), nullable=False),
    sa.Column('consent_at', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('phone_key')
    )
    op.create_table('observations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=False),
    sa.Column('event_id', sa.String(length=36), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('location_source', sa.String(length=16), nullable=False),
    sa.Column('device_accuracy', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('incident_id', sa.String(length=36), nullable=True),
    sa.Column('response', sa.Text(), nullable=False),
    sa.Column('received_at', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('author_id', 'event_id')
    )
    op.create_index(op.f('ix_observations_author_id'), 'observations', ['author_id'], unique=False)
    op.create_index(op.f('ix_observations_incident_id'), 'observations', ['incident_id'], unique=False)
    op.create_index(op.f('ix_observations_received_at'), 'observations', ['received_at'], unique=False)
    op.create_index(op.f('ix_observations_status'), 'observations', ['status'], unique=False)
    op.create_table('outbox',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('incident_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.Integer(), nullable=False),
    sa.Column('external_id', sa.String(length=80), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('incident_id')
    )
    op.create_table('sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('expires_at', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('report_id', sa.String(length=36), nullable=True),
    sa.Column('actor_id', sa.String(length=36), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('details', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['observations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_report_id'), 'audit_events', ['report_id'], unique=False)
    op.create_table('media',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('owner_id', sa.String(length=36), nullable=False),
    sa.Column('upload_key', sa.String(length=36), nullable=False),
    sa.Column('report_id', sa.String(length=36), nullable=True),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('mime', sa.String(length=80), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['observations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('owner_id', 'upload_key')
    )
    op.create_index(op.f('ix_media_owner_id'), 'media', ['owner_id'], unique=False)
    op.create_index(op.f('ix_media_report_id'), 'media', ['report_id'], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
        op.execute('''ALTER TABLE incidents ADD COLUMN IF NOT EXISTS location geography(Point,4326)
          GENERATED ALWAYS AS (CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL
          THEN ST_SetSRID(ST_MakePoint(longitude,latitude),4326)::geography ELSE NULL END) STORED''')
        op.execute('CREATE INDEX IF NOT EXISTS incident_location_gist ON incidents USING GIST(location)')


def downgrade():
    raise RuntimeError('Destructive schema rollback requires an operator-reviewed migration and backup')
