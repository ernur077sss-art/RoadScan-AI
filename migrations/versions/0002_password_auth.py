"""Add password login without assigning passwords to existing OTP accounts."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('password_hash', sa.Text(), nullable=True))
    # Existing test-OTP accounts must not be presented as verified SIM owners.
    op.add_column('users', sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column('users', 'phone_verified')
    op.drop_column('users', 'password_hash')
