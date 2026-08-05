from typing import List, Optional
from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import Index, ForeignKey, ForeignKeyConstraint
from sqlalchemy import Boolean
from sqlalchemy import SmallInteger, Integer, BigInteger
from sqlalchemy import Float, Double
from sqlalchemy import Date, Time, DateTime
from sqlalchemy import String, Text
from sqlalchemy import Uuid
from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship

from database.base_database_model import BaseDatabaseModel

# ----------------------------------------------------------------
class Instructor(BaseDatabaseModel):
    __tablename__ = 'instructor'
    __table_args__ = (
        Index('idx__instructor__staff_number', 'staff_number', unique=True),
        Index('idx__instructor__email', 'email', unique=True),
        Index('idx__instructor__department_id', 'department_id'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    department_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('department.id', ondelete='CASCADE'))

    staff_number: Mapped[str] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(256))
    last_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(256))
