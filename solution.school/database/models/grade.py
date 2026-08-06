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
class Grade(BaseDatabaseModel):
    __tablename__ = 'grade'
    __table_args__ = (
        Index('idx__grade__enrolment_id', 'enrolment_id'),
        Index('idx__grade__assessed_on', 'assessed_on'),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    enrolment_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('enrolment.id', ondelete='CASCADE'))

    value: Mapped[str] = mapped_column(String(4))
    assessed_on: Mapped[date] = mapped_column(Date)
    comment: Mapped[Optional[str]] = mapped_column(String(2048))
