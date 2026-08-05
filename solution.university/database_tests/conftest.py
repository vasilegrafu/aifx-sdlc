"""Fixtures for the database layer tests.

The tests run against their own database, never the development one. The
generator drops and recreates whatever the configuration points at, so a test
run against `config.dev.json` would silently destroy real data -- which is why
ENVIRONMENT is forced here, before anything can read configuration, rather than
left to whoever invokes pytest.
"""
import os

# Set before importing anything from the application: `database.session_maker`
# loads configuration at import time, and by then the choice is already made.
os.environ['ENVIRONMENT'] = 'test'

from datetime import date, datetime               # noqa: E402
import pytest                                     # noqa: E402

from config import Configuration, ConfigurationLoader   # noqa: E402
ConfigurationLoader.load()

from database.database_generator import generate, DATABASE_NAME   # noqa: E402
from database.models import (Department, Program, Student, Instructor,     # noqa: E402
                             AcademicTerm, Course, CourseOffering,
                             ProgramEnrollment, Enrollment)
from database.controllers import (DepartmentDbCtrl, ProgramDbCtrl,         # noqa: E402
                                  StudentDbCtrl, InstructorDbCtrl,
                                  AcademicTermDbCtrl, CourseDbCtrl,
                                  CourseOfferingDbCtrl,
                                  ProgramEnrollmentDbCtrl, EnrollmentDbCtrl)
from database.enums import DegreeLevel, StudentStatus, TermKind, EnrollmentStatus  # noqa: E402


# Children before parents: the schema forbids orphans, and that is the point
CONTROLLERS_LEAF_FIRST = (
    EnrollmentDbCtrl, ProgramEnrollmentDbCtrl, CourseOfferingDbCtrl,
    CourseDbCtrl, InstructorDbCtrl, ProgramDbCtrl, StudentDbCtrl,
    AcademicTermDbCtrl, DepartmentDbCtrl,
)


@pytest.fixture(scope='session', autouse=True)
def database():
    """One schema per test session, built by the application's own generator.

    Using `generate()` rather than `metadata.create_all` keeps the tests honest:
    if the generator breaks, every test fails, which is the correct outcome.
    """
    assert 'test' in Configuration.get('database:url'), \
        'refusing to run: the configured database is not a test database'
    generate()
    yield


@pytest.fixture(autouse=True)
def empty_tables():
    """Every test starts with no rows. Order matters -- see above."""
    for controller in CONTROLLERS_LEAF_FIRST:
        controller.delete_all(None)
    yield


# ---------------------------------------------------------------- factories


@pytest.fixture
def department():
    entity = Department(code='CS', name='Computer Science')
    DepartmentDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def program(department):
    entity = Program(department_id=department.id, code='BSC-CS',
                     name='BSc Computer Science',
                     degree_level=DegreeLevel.BACHELOR.code, duration_semesters=6)
    ProgramDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def student():
    entity = Student(registration_number='S2026-0001', first_name='Ada',
                     last_name='Lovelace', email='ada@university.edu',
                     date_of_birth=date(2005, 12, 10), enrolled_on=date(2026, 9, 1),
                     status=StudentStatus.ACTIVE.code)
    StudentDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def instructor(department):
    entity = Instructor(department_id=department.id, staff_number='T-0001',
                        first_name='Alan', last_name='Turing',
                        email='alan@university.edu')
    InstructorDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def academic_term():
    entity = AcademicTerm(code='2026-FALL', academic_year='2026/2027',
                          kind=TermKind.FALL.code,
                          starts_on=date(2026, 9, 1), ends_on=date(2027, 1, 31))
    AcademicTermDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def course(department):
    entity = Course(department_id=department.id, code='CS101', name='Introduction',
                    description=None, credits=6.0)
    CourseDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def course_offering(course, academic_term, instructor):
    entity = CourseOffering(course_id=course.id, term_id=academic_term.id,
                            instructor_id=instructor.id, capacity=30)
    CourseOfferingDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def enrollment(student, course_offering):
    entity = Enrollment(student_id=student.id, offering_id=course_offering.id,
                        enrolled_at=datetime(2026, 9, 2, 9, 0),
                        status=EnrollmentStatus.ENROLLED.code)
    EnrollmentDbCtrl.save(None, entity)
    return entity


@pytest.fixture
def program_enrollment(student, program):
    entity = ProgramEnrollment(student_id=student.id, program_id=program.id,
                               started_on=date(2026, 9, 1), ended_on=None,
                               status='AC')
    ProgramEnrollmentDbCtrl.save(None, entity)
    return entity
