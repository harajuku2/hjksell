"""Initial HJKsell schema.

Revision ID: 0001_initial_schema
"""

from alembic import op

from hjksell.database.models import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial schema without dropping existing user data."""
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    """Initial revision has no destructive downgrade."""
    return None
