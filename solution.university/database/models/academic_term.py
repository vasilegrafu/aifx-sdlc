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
class AcademicTerm(BaseDatabaseModel):
    __tablename__ = 'academic_term'
    __table_args__ = (
        Index('idx__academic_term__code', 'code', unique=True),
        Index('idx__academic_term__academic_year', 'academic_year'),
        Index('idx__academic_term__starts_on', 'starts_on'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    code: Mapped[str] = mapped_column(String(16))
    academic_year: Mapped[str] = mapped_column(String(9))
    kind: Mapped[str] = mapped_column(String(8))

    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
