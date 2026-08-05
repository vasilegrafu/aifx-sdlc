import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Department
from database.controllers import DepartmentDbCtrl


def test_save_then_read_back(department):
    read_back = DepartmentDbCtrl.get_by_id(None, id=department.id)
    assert read_back is not None
    assert read_back.code == 'CS'
    assert read_back.name == 'Computer Science'


def test_get_by_code(department):
    assert DepartmentDbCtrl.get_by_code(None, code='CS').id == department.id
    assert DepartmentDbCtrl.get_by_code(None, code='NOPE') is None


def test_get_all_and_get_by_ids(department):
    DepartmentDbCtrl.save(None, Department(code='MATH', name='Mathematics'))
    assert len(DepartmentDbCtrl.get_all(None)) == 2
    assert len(DepartmentDbCtrl.get_by_ids(None, ids=[department.id])) == 1


def test_delete_by_id(department):
    DepartmentDbCtrl.delete_by_id(None, id=department.id)
    assert DepartmentDbCtrl.get_by_id(None, id=department.id) is None


def test_delete_all(department):
    DepartmentDbCtrl.save(None, Department(code='MATH', name='Mathematics'))
    DepartmentDbCtrl.delete_all(None)
    assert DepartmentDbCtrl.get_all(None) == []


def test_code_is_unique(department):
    """The unique index is the only thing preventing two departments called CS."""
    with pytest.raises(IntegrityError):
        DepartmentDbCtrl.save(None, Department(code='CS', name='Duplicate'))
