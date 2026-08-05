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
class CourseOffering(BaseDatabaseModel):
    __tablename__ = 'course_offering'
    __table_args__ = (
        Index('idx__course_offering__course_id', 'course_id'),
        Index('idx__course_offering__term_id', 'term_id'),
        Index('idx__course_offering__instructor_id', 'instructor_id'),
        Index('idx__course_offering__course_id__term_id', 'course_id', 'term_id', unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    course_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('course.id', ondelete='CASCADE'))
    term_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('academic_term.id', ondelete='CASCADE'))
    instructor_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid, ForeignKey('instructor.id', ondelete='SET NULL'))

    capacity: Mapped[Optional[int]] = mapped_column(Integer)
