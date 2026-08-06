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
class SchoolYear(BaseDatabaseModel):
    __tablename__ = 'school_year'
    __table_args__ = (
        Index('idx__school_year__code', 'code', unique=True),
        CheckConstraint('ends_on > starts_on', name='ck__school_year__dates'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    code: Mapped[str] = mapped_column(String(16))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)

