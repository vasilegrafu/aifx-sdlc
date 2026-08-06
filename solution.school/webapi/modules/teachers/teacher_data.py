from pydantic import Field
from uuid import UUID
from datetime import date
from devfx.ux.webapi import BaseData
from database.models import Teacher

"""----------------------------------------------------------------
"""
class TeacherData(BaseData):
    id: UUID | None = Field(default=None)
    staff_number: str | None = Field(default=None)
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)
    email: str | None = Field(default=None)

    def __str__(self) -> str:
        return (f"id={self.id}, "
            f"staff_number={self.staff_number}, "
            f"first_name={self.first_name}, "
            f"last_name={self.last_name}, "
            f"email={self.email}")

    @staticmethod
    def map_from(teacher: Teacher) -> 'TeacherData':
        return TeacherData(
            id=teacher.id,
            staff_number=teacher.staff_number,
            first_name=teacher.first_name,
            last_name=teacher.last_name,
            email=teacher.email,
        )
