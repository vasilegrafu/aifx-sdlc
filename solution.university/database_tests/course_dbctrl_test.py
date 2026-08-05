import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Course
from database.controllers import CourseDbCtrl, DepartmentDbCtrl


def test_save_then_read_back(course):
    read_back = CourseDbCtrl.get_by_id(None, id=course.id)
    assert read_back.name == 'Introduction'
    assert read_back.credits == 6.0
    assert read_back.description is None, 'description is nullable'


def test_get_by_code(course):
    assert CourseDbCtrl.get_by_code(None, code='CS101').id == course.id


def test_get_by_department_id_returns_many(course, department):
    found = CourseDbCtrl.get_by_department_id(None, department_id=department.id)
    assert [c.id for c in found] == [course.id]


def test_code_is_unique(course, department):
    with pytest.raises(IntegrityError):
        CourseDbCtrl.save(None, Course(department_id=department.id, code='CS101',
                                       name='Duplicate', description=None, credits=3.0))


def test_deleting_the_department_cascades(course, department):
    DepartmentDbCtrl.delete_by_id(None, id=department.id)
    assert CourseDbCtrl.get_all(None) == []
