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
class FormClass(BaseDatabaseModel):
    __tablename__ = 'form_class'
    __table_args__ = (
        Index('idx__form_class__school_year_id', 'school_year_id'),
        Index('idx__form_class__form_tutor_id', 'form_tutor_id'),
        Index('idx__form_class__school_year_id__name', 'school_year_id', 'name', unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    school_year_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('school_year.id', ondelete='CASCADE'))
    form_tutor_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid, ForeignKey('teacher.id', ondelete='SET NULL'))

    name: Mapped[str] = mapped_column(String(16))
    year_group: Mapped[int] = mapped_column(SmallInteger)
