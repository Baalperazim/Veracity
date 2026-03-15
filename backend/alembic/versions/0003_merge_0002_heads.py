"""merge parallel 0002 migrations

Revision ID: 0003_merge_0002_heads
Revises: 0002_add_asset_anchors, 0002_tokenization_foundation, 0002_token_issuance_layer
Create Date: 2026-03-15 00:00:00.000000
"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0003_merge_0002_heads"
down_revision: Union[str, Sequence[str], None] = (
    "0002_add_asset_anchors",
    "0002_tokenization_foundation",
    "0002_token_issuance_layer",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
