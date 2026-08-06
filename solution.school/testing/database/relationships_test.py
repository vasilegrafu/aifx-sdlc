from datetime import datetime

from testing.builders import a_student, a_grade
from database.models import FormClass, Student
from database.controllers import StudentDbCtrl, GradeDbCtrl

"""------------------------------------------------------------------------------------------------
What these pin is not that the relationships exist -- it is that they still work
*after the session has closed*.

`session_injector` opens and closes a session around each controller call, so
every object a controller returns is detached. A relationship declared without
`lazy='selectin'` is then unreachable: the attribute is there, and touching it
raises DetachedInstanceError at every caller. Nothing catches that except a test
that traverses one outside a session, which is what these do.

The collection direction is deliberately not declared -- see the note in
`database/models/student.py`. `test_the_collection_direction_is_not_declared`
pins that too, so that adding `FormClass.students` back has to be a decision
rather than an accident: both directions eager makes the loads cycle.
"""


# ----------------------------------------------------------------
def test_many_to_one_traverses_on_a_detached_object():
    a_student()

    student = StudentDbCtrl.get_all(None)[0]

    assert student.form_class.name


def test_many_to_one_traverses_two_hops():
    a_student()

    student = StudentDbCtrl.get_all(None)[0]

    assert student.form_class.school_year.code
    assert student.form_class.form_tutor.last_name


def test_many_to_one_traverses_from_a_grade():
    a_grade()

    grade = GradeDbCtrl.get_all(None)[0]

    assert grade.enrolment.subject.code
    assert grade.enrolment.student.last_name


# ----------------------------------------------------------------
def test_the_collection_direction_is_not_declared():
    assert not hasattr(FormClass, 'students')


def test_the_controller_answers_the_collection_direction():
    made = a_student()

    got = StudentDbCtrl.get_by_form_class_id(None, made.form_class_id)

    assert [x.id for x in got] == [made.id]


# ----------------------------------------------------------------
def test_timestamps_are_populated_on_insert():
    a_student()

    student = StudentDbCtrl.get_all(None)[0]

    assert isinstance(student.created_at, datetime)
    assert isinstance(student.updated_at, datetime)
