from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Student
from database.controllers import StudentDbCtrl
from database.enums import StudentStatus


def test_save_then_read_back(student):
    read_back = StudentDbCtrl.get_by_id(None, id=student.id)
    assert read_back.first_name == 'Ada'
    assert read_back.last_name == 'Lovelace'
    assert read_back.date_of_birth == date(2005, 12, 10)


def test_get_by_registration_number(student):
    found = StudentDbCtrl.get_by_registration_number(None,
                                                     registration_number='S2026-0001')
    assert found.id == student.id
    assert StudentDbCtrl.get_by_registration_number(None,
                                                    registration_number='S9999') is None


def test_get_by_email(student):
    assert StudentDbCtrl.get_by_email(None, email='ada@university.edu').id == student.id


def test_get_by_status_returns_many(student):
    found = StudentDbCtrl.get_by_status(None, status=StudentStatus.ACTIVE.code)
    assert isinstance(found, list)
    assert [s.id for s in found] == [student.id]


def test_status_round_trips_through_the_enum(student):
    read_back = StudentDbCtrl.get_by_id(None, id=student.id)
    assert StudentStatus.from_code(read_back.status) is StudentStatus.ACTIVE


def test_save_data_updates_in_place(student):
    StudentDbCtrl.save_data(None, Student.registration_number == 'S2026-0001',
                            status=StudentStatus.GRADUATED.code)
    assert len(StudentDbCtrl.get_all(None)) == 1, 'upsert must not insert a second row'
    read_back = StudentDbCtrl.get_by_id(None, id=student.id)
    assert read_back.status == StudentStatus.GRADUATED.code


def test_save_data_inserts_when_nothing_matches():
    StudentDbCtrl.save_data(None, Student.registration_number == 'S2026-0002',
                            registration_number='S2026-0002', first_name='Grace',
                            last_name='Hopper', email='grace@university.edu',
                            enrolled_on=date(2026, 9, 1),
                            status=StudentStatus.ACTIVE.code)
    assert StudentDbCtrl.get_by_registration_number(
        None, registration_number='S2026-0002').first_name == 'Grace'


def test_save_data_rejects_an_unknown_attribute(student):
    """A misspelled assign would otherwise set nothing and report success."""
    with pytest.raises(Exception, match='does not exist'):
        StudentDbCtrl.save_data(None, Student.registration_number == 'S2026-0001',
                                statuss='XX')


def test_registration_number_is_unique(student):
    with pytest.raises(IntegrityError):
        StudentDbCtrl.save(None, Student(registration_number='S2026-0001',
                                         first_name='Someone', last_name='Else',
                                         email='else@university.edu',
                                         enrolled_on=date(2026, 9, 1),
                                         status=StudentStatus.ACTIVE.code))


def test_email_is_unique(student):
    with pytest.raises(IntegrityError):
        StudentDbCtrl.save(None, Student(registration_number='S2026-0003',
                                         first_name='Someone', last_name='Else',
                                         email='ada@university.edu',
                                         enrolled_on=date(2026, 9, 1),
                                         status=StudentStatus.ACTIVE.code))
