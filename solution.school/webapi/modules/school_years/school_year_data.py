from pydantic import Field
from uuid import UUID
from datetime import date
from devfx.ux.webapi import BaseData
from database.models import SchoolYear

"""----------------------------------------------------------------
"""
class SchoolYearData(BaseData):
    id: UUID | None = Field(default=None)
    code: str | None = Field(default=None)
    starts_on: date | None = Field(default=None)
    ends_on: date | None = Field(default=None)

    def __str__(self) -> str:
        return (f"id={self.id}, "
            f"code={self.code}, "
            f"starts_on={self.starts_on}, "
            f"ends_on={self.ends_on}")

    @staticmethod
    def map_from(school_year: SchoolYear) -> 'SchoolYearData':
        return SchoolYearData(
            id=school_year.id,
            code=school_year.code,
            starts_on=school_year.starts_on,
            ends_on=school_year.ends_on,
        )
