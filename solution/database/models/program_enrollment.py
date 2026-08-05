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
class ProgramEnrollment(BaseDatabaseModel):
    __tablename__ = 'program_enrollment'
    __table_args__ = (
        Index('idx__program_enrollment__student_id', 'student_id'),
        Index('idx__program_enrollment__program_id', 'program_id'),
        Index('idx__program_enrollment__student_id__program_id', 'student_id', 'program_id'),
        Index('idx__program_enrollment__status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('student.id', ondelete='CASCADE'))
    program_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('program.id', ondelete='CASCADE'))

    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(8))
