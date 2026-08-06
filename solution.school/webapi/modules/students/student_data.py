from pydantic import Field
from uuid import UUID
from datetime import date
from devfx.ux.webapi import BaseData
from database.models import Student

"""----------------------------------------------------------------
"""
class StudentData(BaseData):
    id: UUID | None = Field(default=None)
    form_class_id: UUID | None = Field(default=None)
    admission_number: str | None = Field(default=None)
    first_name: str | None = Field(default=None)
    last_name: str | None = Field(default=None)
    date_of_birth: date | None = Field(default=None)
    enrolled_on: date | None = Field(default=None)

    def __str__(self) -> str:
        return (f"id={self.id}, "
            f"form_class_id={self.form_class_id}, "
            f"admission_number={self.admission_number}, "
            f"first_name={self.first_name}, "
            f"last_name={self.last_name}")

    @staticmethod
    def map_from(student: Student) -> 'StudentData':
        return StudentData(
            id=student.id,
            form_class_id=student.form_class_id,
            admission_number=student.admission_number,
            first_name=student.first_name,
            last_name=student.last_name,
            date_of_birth=student.date_of_birth,
            enrolled_on=student.enrolled_on,
        )
