from typing import List, Optional
from datetime import datetime
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
class StockCandlestick(BaseDatabaseModel):
    __tablename__ = 'stock_candlestick'
    __table_args__ = (
        Index('idx__stock_candlestick__instrument_id', 'instrument_id'),
        Index('idx__stock_candlestick__timeframe', 'timeframe'),
        Index('idx__stock_candlestick__time', 'time'),
        Index('idx__stock_candlestick__instrument_id__timeframe', 'instrument_id', 'timeframe'),
        Index('idx__stock_candlestick__instrument_id__timeframe__time', 'instrument_id', 'timeframe', 'time'),
        {'schema': 'market_data'},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey('reference_data.stock_instrument.id', ondelete='CASCADE'))
    timeframe: Mapped[str] = mapped_column(String(8))
    time: Mapped[datetime] = mapped_column(DateTime)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
