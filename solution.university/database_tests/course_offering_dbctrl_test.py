import pytest
from sqlalchemy.exc import IntegrityError

from database.models import CourseOffering
from database.controllers import (CourseOfferingDbCtrl, CourseDbCtrl,
                                  AcademicTermDbCtrl, InstructorDbCtrl)


def test_save_then_read_back(course_offering):
    read_back = CourseOfferingDbCtrl.get_by_id(None, id=course_offering.id)
    assert read_back.capacity == 30


def test_get_by_course_id(course_offering, course):
    found = CourseOfferingDbCtrl.get_by_course_id(None, course_id=course.id)
    assert [o.id for o in found] == [course_offering.id]


def test_get_by_term_id(course_offering, academic_term):
    found = CourseOfferingDbCtrl.get_by_term_id(None, term_id=academic_term.id)
    assert [o.id for o in found] == [course_offering.id]


def test_get_by_instructor_id(course_offering, instructor):
    found = CourseOfferingDbCtrl.get_by_instructor_id(None, instructor_id=instructor.id)
    assert [o.id for o in found] == [course_offering.id]


def test_a_course_is_offered_once_per_term(course_offering, course, academic_term):
    with pytest.raises(IntegrityError):
        CourseOfferingDbCtrl.save(None, CourseOffering(course_id=course.id,
                                                       term_id=academic_term.id,
                                                       instructor_id=None, capacity=10))


def test_instructor_is_optional(course, academic_term):
    """The offering exists before anyone is assigned to teach it."""
    CourseOfferingDbCtrl.save(None, CourseOffering(course_id=course.id,
                                                   term_id=academic_term.id,
                                                   instructor_id=None, capacity=10))
    assert CourseOfferingDbCtrl.get_all(None)[0].instructor_id is None


def test_deleting_the_instructor_leaves_the_offering(course_offering, instructor):
    """SET NULL, not CASCADE: a teacher leaving does not cancel the class."""
    InstructorDbCtrl.delete_by_id(None, id=instructor.id)
    read_back = CourseOfferingDbCtrl.get_by_id(None, id=course_offering.id)
    assert read_back is not None
    assert read_back.instructor_id is None


def test_deleting_the_course_cascades(course_offering, course):
    CourseDbCtrl.delete_by_id(None, id=course.id)
    assert CourseOfferingDbCtrl.get_all(None) == []


def test_deleting_the_term_cascades(course_offering, academic_term):
    AcademicTermDbCtrl.delete_by_id(None, id=academic_term.id)
    assert CourseOfferingDbCtrl.get_all(None) == []
