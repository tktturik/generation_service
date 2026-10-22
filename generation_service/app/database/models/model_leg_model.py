from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class ModelLegModel(Base):
    __tablename__ = "model_legs"
    __table_args__ = (
        UniqueConstraint("model_slug", "priority"),
        CheckConstraint("provider IN ('alpha', 'beta')", name="provider_known"),
        CheckConstraint("max_ref_images >= 0", name="max_ref_images_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    model_slug: Mapped[str] = mapped_column(ForeignKey("models.slug"))
    priority: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    max_ref_images: Mapped[int] = mapped_column(Integer)
    skip_on_moderation: Mapped[bool] = mapped_column(server_default="false")
