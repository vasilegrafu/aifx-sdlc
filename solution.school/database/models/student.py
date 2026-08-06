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

    # DEPARTURE from atlas: atlas declares foreign keys and no relationship().
    # Only the many-to-one direction is declared, and eagerly. session_injector
    # closes the session per call, so anything not loaded by that query is
    # unreachable -- a lazy relationship raises DetachedInstanceError at every
    # caller. The collection direction is deliberately absent: declaring it both
    # ways makes the eager loads cycle, and the controllers already answer it
    # (StudentDbCtrl.get_by_form_class_id, EnrolmentDbCtrl.get_by_student_id).
    form_class: Mapped['FormClass'] = relationship(lazy='selectin')
