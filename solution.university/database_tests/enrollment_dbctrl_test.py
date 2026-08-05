import uuid
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from database.models import Enrollment
from database.controllers import (EnrollmentDbCtrl, StudentDbCtrl,
                                  CourseOfferingDbCtrl)
from database.enums import EnrollmentStatus


def test_save_then_read_back(enrollment):
    read_back = EnrollmentDbCtrl.get_by_id(None, id=enrollment.id)
    assert read_back.status == EnrollmentStatus.ENROLLED.code
    assert read_back.grade is None


def test_get_by_student_id(enrollment, student):
    found = EnrollmentDbCtrl.get_by_student_id(None, student_id=student.id)
    assert [e.id for e in found] == [enrollment.id]


def test_get_by_offering_id(enrollment, course_offering):
    found = EnrollmentDbCtrl.get_by_offering_id(None, offering_id=course_offering.id)
    assert [e.id for e in found] == [enrollment.id]


def test_grading_through_save_data(enrollment):
    EnrollmentDbCtrl.save_data(None, Enrollment.id == enrollment.id,
                               status=EnrollmentStatus.COMPLETED.code,
                               grade='A', grade_points=4.0,
                               graded_at=datetime(2027, 1, 20, 12, 0))
    read_back = EnrollmentDbCtrl.get_by_id(None, id=enrollment.id)
    assert read_back.grade == 'A'
    assert read_back.grade_points == 4.0
    assert EnrollmentStatus.from_code(read_back.status) is EnrollmentStatus.COMPLETED


def test_a_student_cannot_enrol_twice_in_one_offering(enrollment, student,
                                                      course_offering):
    with pytest.raises(IntegrityError):
        EnrollmentDbCtrl.save(None, Enrollment(student_id=student.id,
                                               offering_id=course_offering.id,
                                               enrolled_at=datetime(2026, 9, 3, 9, 0),
                                               status=EnrollmentStatus.ENROLLED.code))


def test_foreign_key_is_enforced(course_offering):
    """Without PRAGMA foreign_keys=ON this silently succeeds on SQLite."""
    with pytest.raises(IntegrityError):
        EnrollmentDbCtrl.save(None, Enrollment(student_id=uuid.uuid4(),
                                               offering_id=course_offering.id,
                                               enrolled_at=datetime(2026, 9, 2, 9, 0),
                                               status=EnrollmentStatus.ENROLLED.code))


def test_deleting_a_student_cascades_to_enrollments(enrollment, student):
    StudentDbCtrl.delete_by_id(None, id=student.id)
    assert EnrollmentDbCtrl.get_all(None) == [], 'the enrollment was left orphaned'


def test_deleting_an_offering_cascades_to_enrollments(enrollment, course_offering):
    CourseOfferingDbCtrl.delete_by_id(None, id=course_offering.id)
    assert EnrollmentDbCtrl.get_all(None) == []
