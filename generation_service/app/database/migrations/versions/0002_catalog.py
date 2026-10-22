"""catalog

Revision ID: 0002_catalog
Revises: 0b9b6bb613a0
Create Date: 2026-10-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_catalog'
down_revision: Union[str, Sequence[str], None] = '0b9b6bb613a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Лёгкие таблицы только для вставки данных: схема не меняется.
models_table = sa.table(
    'models',
    sa.column('slug', sa.Text()),
    sa.column('price', sa.BigInteger()),
)

model_legs_table = sa.table(
    'model_legs',
    sa.column('model_slug', sa.Text()),
    sa.column('priority', sa.Integer()),
    sa.column('provider', sa.Text()),
    sa.column('max_ref_images', sa.Integer()),
    sa.column('skip_on_moderation', sa.Boolean()),
)

CATALOG_SLUGS = ['image-fast', 'video-long']


def upgrade() -> None:
    """Upgrade schema."""
    # id ног не задаём: это identity-колонка, значения выдаёт база
    op.bulk_insert(models_table, [
        {'slug': 'image-fast', 'price': 2},
        {'slug': 'video-long', 'price': 25},
    ])
    op.bulk_insert(model_legs_table, [
        {'model_slug': 'image-fast', 'priority': 1, 'provider': 'alpha', 'max_ref_images': 4, 'skip_on_moderation': False},
        {'model_slug': 'image-fast', 'priority': 2, 'provider': 'beta', 'max_ref_images': 10, 'skip_on_moderation': False},
        {'model_slug': 'video-long', 'priority': 1, 'provider': 'beta', 'max_ref_images': 2, 'skip_on_moderation': False},
        {'model_slug': 'video-long', 'priority': 2, 'provider': 'alpha', 'max_ref_images': 1, 'skip_on_moderation': True},
    ])


def downgrade() -> None:
    """Downgrade schema."""
    # сначала ноги: на models ссылается внешний ключ model_legs.model_slug
    op.execute(sa.delete(model_legs_table).where(model_legs_table.c.model_slug.in_(CATALOG_SLUGS)))
    op.execute(sa.delete(models_table).where(models_table.c.slug.in_(CATALOG_SLUGS)))
