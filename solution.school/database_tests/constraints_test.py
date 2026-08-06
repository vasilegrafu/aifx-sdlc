from datetime import date
from uuid import uuid4
import pytest
from sqlalchemy.exc import IntegrityError

from database_tests.fixtures import a_student, a_subject, a_grade, an_enrolment
from database.models import Student, Enrolment
from database.controllers import (StudentDbCtrl, EnrolmentDbCtrl, GradeDbCtrl,
                                  FormClassDbCtrl)

"""------------------------------------------------------------------------------------------------
The guarantees that fail silently.

Every one of these is declared in a model and can be generated perfectly and
still not happen. On SQLite two of them do not happen at all unless every
connection is told `PRAGMA foreign_keys=ON` -- the constraint is accepted and
then ignored, and the first sign of it is an orphaned row much later.

Removing `database/sqlite_foreign_keys.py` makes the last two of these fail and
nothing else, which is what pins it here rather than in a comment.
"""


# ----------------------------------------------------------------
def test_unique_index_rejects_a_duplicate_admission_number():
    a_student(admission_number='ADM-0001')
    form = FormClassDbCtrl.get_all(None)[0]

    with pytest.raises(IntegrityError):
        StudentDbCtrl.save(None, Student(
            form_class_id=form.id, admission_number='ADM-0001',
            first_name='X', last_name='Y',
            date_of_birth=date(2012, 1, 1), enrolled_on=date(2026, 9, 1)))


def test_unique_index_allows_a_different_admission_number():
    a_student(admission_number='ADM-0001')
    form = FormClassDbCtrl.get_all(None)[0]

    StudentDbCtrl.save(None, Student(
        form_class_id=form.id, admission_number='ADM-0002',
        first_name='X', last_name='Y',
        date_of_birth=date(2012, 1, 1), enrolled_on=date(2026, 9, 1)))

    assert len(StudentDbCtrl.get_all(None)) == 2


# ----------------------------------------------------------------
def test_foreign_key_rejects_an_unknown_parent():
    with pytest.raises(IntegrityError):
        EnrolmentDbCtrl.save(None, Enrolment(
            student_id=uuid4(), subject_id=uuid4(),
            enrolled_on=date(2026, 9, 5), status='ACT'))


def test_deleting_a_student_cascades_to_enrolment_and_grade():
    a_grade()
    assert len(EnrolmentDbCtrl.get_all(None)) == 1
    assert len(GradeDbCtrl.get_all(None)) == 1

    StudentDbCtrl.delete_all(None)

    assert EnrolmentDbCtrl.get_all(None) == []
    assert GradeDbCtrl.get_all(None) == []
