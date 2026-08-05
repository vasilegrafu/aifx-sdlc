import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Instructor
from database.controllers import InstructorDbCtrl, DepartmentDbCtrl


def test_save_then_read_back(instructor):
    read_back = InstructorDbCtrl.get_by_id(None, id=instructor.id)
    assert read_back.last_name == 'Turing'


def test_get_by_staff_number(instructor):
    assert InstructorDbCtrl.get_by_staff_number(None, staff_number='T-0001').id == instructor.id


def test_get_by_department_id_returns_many(instructor, department):
    found = InstructorDbCtrl.get_by_department_id(None, department_id=department.id)
    assert [i.id for i in found] == [instructor.id]


def test_staff_number_is_unique(instructor, department):
    with pytest.raises(IntegrityError):
        InstructorDbCtrl.save(None, Instructor(department_id=department.id,
                                               staff_number='T-0001',
                                               first_name='Another', last_name='Person',
                                               email='another@university.edu'))


def test_deleting_the_department_cascades(instructor, department):
    DepartmentDbCtrl.delete_by_id(None, id=department.id)
    assert InstructorDbCtrl.get_all(None) == []
