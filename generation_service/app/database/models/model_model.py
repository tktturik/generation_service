from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class ModelModel(Base):
    __tablename__ = "models"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    price: Mapped[int] = mapped_column(BigInteger)
