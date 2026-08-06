from pydantic import Field
from uuid import UUID
from datetime import date
from devfx.ux.webapi import BaseData
from database.models import Subject

"""----------------------------------------------------------------
"""
class SubjectData(BaseData):
    id: UUID | None = Field(default=None)
    code: str | None = Field(default=None)
    name: str | None = Field(default=None)
    description: str | None = Field(default=None)

    def __str__(self) -> str:
        return (f"id={self.id}, "
            f"code={self.code}, "
            f"name={self.name}, "
            f"description={self.description}")

    @staticmethod
    def map_from(subject: Subject) -> 'SubjectData':
        return SubjectData(
            id=subject.id,
            code=subject.code,
            name=subject.name,
            description=subject.description,
        )
