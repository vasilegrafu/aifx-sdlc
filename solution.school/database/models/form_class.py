from typing import List, Optional
from datetime import datetime, date
from uuid import UUID, uuid4
from sqlalchemy import Index, ForeignKey, ForeignKeyConstraint, CheckConstraint
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
class FormClass(BaseDatabaseModel):
    __tablename__ = 'form_class'
    __table_args__ = (
        Index('idx__form_class__school_year_id', 'school_year_id'),
        Index('idx__form_class__form_tutor_id', 'form_tutor_id'),
        Index('idx__form_class__school_year_id__name', 'school_year_id', 'name', unique=True),
        CheckConstraint('year_group between 1 and 13', name='ck__form_class__year_group'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    school_year_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('school_year.id', ondelete='CASCADE'))
    form_tutor_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid, ForeignKey('teacher.id', ondelete='SET NULL'))

    name: Mapped[str] = mapped_column(String(16))
    year_group: Mapped[int] = mapped_column(SmallInteger)

    # DEPARTURE from atlas: atlas declares foreign keys and no relationship().
    # Only the many-to-one direction is declared, and eagerly. session_injector
    # closes the session per call, so anything not loaded by that query is
    # unreachable -- a lazy relationship raises DetachedInstanceError at every
    # caller. The collection direction is deliberately absent: declaring it both
    # ways makes the eager loads cycle, and the controllers already answer it
    # (StudentDbCtrl.get_by_form_class_id, EnrolmentDbCtrl.get_by_student_id).
    school_year: Mapped['SchoolYear'] = relationship(lazy='selectin')
    form_tutor: Mapped[Optional['Teacher']] = relationship(lazy='selectin')
