from datetime import date

from database.models import ProgramEnrollment
from database.controllers import (ProgramEnrollmentDbCtrl, StudentDbCtrl,
                                  ProgramDbCtrl)


def test_save_then_read_back(program_enrollment):
    read_back = ProgramEnrollmentDbCtrl.get_by_id(None, id=program_enrollment.id)
    assert read_back.started_on == date(2026, 9, 1)
    assert read_back.ended_on is None, 'an open enrollment has no end date'


def test_get_by_student_id(program_enrollment, student):
    found = ProgramEnrollmentDbCtrl.get_by_student_id(None, student_id=student.id)
    assert [e.id for e in found] == [program_enrollment.id]


def test_get_by_program_id(program_enrollment, program):
    found = ProgramEnrollmentDbCtrl.get_by_program_id(None, program_id=program.id)
    assert [e.id for e in found] == [program_enrollment.id]


def test_a_student_can_hold_a_history_of_programs(program_enrollment, student, program):
    """Transfers are why this is a table and not two columns on student."""
    ProgramEnrollmentDbCtrl.save_data(None, ProgramEnrollment.id == program_enrollment.id,
                                      ended_on=date(2027, 6, 30), status='WD')
    ProgramEnrollmentDbCtrl.save(None, ProgramEnrollment(student_id=student.id,
                                                         program_id=program.id,
                                                         started_on=date(2027, 9, 1),
                                                         ended_on=None, status='AC'))
    history = ProgramEnrollmentDbCtrl.get_by_student_id(None, student_id=student.id)
    assert len(history) == 2
    assert sorted(e.status for e in history) == ['AC', 'WD']


def test_deleting_the_student_cascades(program_enrollment, student):
    StudentDbCtrl.delete_by_id(None, id=student.id)
    assert ProgramEnrollmentDbCtrl.get_all(None) == []


def test_deleting_the_program_cascades(program_enrollment, program):
    ProgramDbCtrl.delete_by_id(None, id=program.id)
    assert ProgramEnrollmentDbCtrl.get_all(None) == []
