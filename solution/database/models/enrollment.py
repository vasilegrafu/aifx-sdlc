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
class Enrollment(BaseDatabaseModel):
    __tablename__ = 'enrollment'
    __table_args__ = (
        Index('idx__enrollment__student_id', 'student_id'),
        Index('idx__enrollment__offering_id', 'offering_id'),
        Index('idx__enrollment__student_id__offering_id', 'student_id', 'offering_id', unique=True),
        Index('idx__enrollment__status', 'status'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('student.id', ondelete='CASCADE'))
    offering_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('course_offering.id', ondelete='CASCADE'))

    enrolled_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(8))

    grade: Mapped[Optional[str]] = mapped_column(String(8))
    grade_points: Mapped[Optional[float]] = mapped_column(Float)
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
