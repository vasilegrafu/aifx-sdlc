from typing import List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Index, ForeignKeyConstraint
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
class StockInstrument(BaseDatabaseModel):
    __tablename__ = 'stock_instrument'
    __table_args__ = (
        Index('idx__stock_instrument__ticker_symbol', 'ticker_symbol', unique=True),
        {'schema': 'reference_data'},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    
    ticker_symbol: Mapped[str] = mapped_column(String(8))
    name: Mapped[Optional[str]] = mapped_column(String(256))
    exchange: Mapped[str] = mapped_column(String(256))
    description: Mapped[Optional[str]] = mapped_column(String(2048))
    
    economic_sector: Mapped[str] = mapped_column(String(8))
