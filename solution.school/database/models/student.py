from typing import List, Optional
from datetime import datetime, date
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
        Index('idx__student__admission_number', 'admission_number', unique=True),
        Index('idx__student__form_class_id', 'form_class_id'),
        Index('idx__student__last_name', 'last_name'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    form_class_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('form_class.id', ondelete='CASCADE'))

    admission_number: Mapped[str] = mapped_column(String(16))
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    date_of_birth: Mapped[date] = mapped_column(Date)
    enrolled_on: Mapped[date] = mapped_column(Date)
