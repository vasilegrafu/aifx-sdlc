import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Program
from database.controllers import ProgramDbCtrl, DepartmentDbCtrl
from database.enums import DegreeLevel


def test_save_then_read_back(program):
    read_back = ProgramDbCtrl.get_by_id(None, id=program.id)
    assert read_back.name == 'BSc Computer Science'
    assert read_back.duration_semesters == 6


def test_get_by_code(program):
    assert ProgramDbCtrl.get_by_code(None, code='BSC-CS').id == program.id


def test_get_by_department_id_returns_many(program, department):
    found = ProgramDbCtrl.get_by_department_id(None, department_id=department.id)
    assert [p.id for p in found] == [program.id]


def test_degree_level_round_trips_through_the_enum(program):
    read_back = ProgramDbCtrl.get_by_id(None, id=program.id)
    assert DegreeLevel.from_code(read_back.degree_level) is DegreeLevel.BACHELOR


def test_code_is_unique(program, department):
    with pytest.raises(IntegrityError):
        ProgramDbCtrl.save(None, Program(department_id=department.id, code='BSC-CS',
                                         name='Duplicate',
                                         degree_level=DegreeLevel.MASTER.code,
                                         duration_semesters=4))


def test_deleting_the_department_cascades(program, department):
    DepartmentDbCtrl.delete_by_id(None, id=department.id)
    assert ProgramDbCtrl.get_all(None) == []
