from sqlalchemy import BigInteger, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base_model import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)

    # id задаёт клиент, автогенерации нет
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    balance: Mapped[int] = mapped_column(BigInteger, server_default="0")
