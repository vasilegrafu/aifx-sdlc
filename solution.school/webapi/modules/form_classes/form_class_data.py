from pydantic import Field
from uuid import UUID
from datetime import date
from devfx.ux.webapi import BaseData
from database.models import FormClass

"""----------------------------------------------------------------
"""
class FormClassData(BaseData):
    id: UUID | None = Field(default=None)
    school_year_id: UUID | None = Field(default=None)
    form_tutor_id: UUID | None = Field(default=None)
    name: str | None = Field(default=None)
    year_group: int | None = Field(default=None)

    def __str__(self) -> str:
        return (f"id={self.id}, "
            f"school_year_id={self.school_year_id}, "
            f"form_tutor_id={self.form_tutor_id}, "
            f"name={self.name}, "
            f"year_group={self.year_group}")

    @staticmethod
    def map_from(form_class: FormClass) -> 'FormClassData':
        return FormClassData(
            id=form_class.id,
            school_year_id=form_class.school_year_id,
            form_tutor_id=form_class.form_tutor_id,
            name=form_class.name,
            year_group=form_class.year_group,
        )
