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
class Enrolment(BaseDatabaseModel):
    __tablename__ = 'enrolment'
    __table_args__ = (
        Index('idx__enrolment__student_id', 'student_id'),
        Index('idx__enrolment__subject_id', 'subject_id'),
        Index('idx__enrolment__student_id__subject_id', 'student_id', 'subject_id', unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('student.id', ondelete='CASCADE'))
    subject_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('subject.id', ondelete='CASCADE'))

    enrolled_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8))

    # DEPARTURE from atlas: atlas declares foreign keys and no relationship().
    # Only the many-to-one direction is declared, and eagerly. session_injector
    # closes the session per call, so anything not loaded by that query is
    # unreachable -- a lazy relationship raises DetachedInstanceError at every
    # caller. The collection direction is deliberately absent: declaring it both
    # ways makes the eager loads cycle, and the controllers already answer it
    # (StudentDbCtrl.get_by_form_class_id, EnrolmentDbCtrl.get_by_student_id).
    student: Mapped['Student'] = relationship(lazy='selectin')
    subject: Mapped['Subject'] = relationship(lazy='selectin')
