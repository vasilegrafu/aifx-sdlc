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
class Student(BaseDatabaseModel):
    __tablename__ = 'student'
    __table_args__ = (
        Index('idx__student__registration_number', 'registration_number', unique=True),
        Index('idx__student__email', 'email', unique=True),
        Index('idx__student__last_name', 'last_name'),
        Index('idx__student__status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    registration_number: Mapped[str] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(256))
    last_name: Mapped[str] = mapped_column(String(256))
    email: Mapped[str] = mapped_column(String(256))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)

    enrolled_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8))
