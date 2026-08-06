from datetime import date

"""------------------------------------------------------------------------------------------------
The data every suite needs, written once.

`database_tests` and `webapi_tests` both have to put a student in the database
before they can assert anything about one, and a student is only reachable
through a form class, a school year and a teacher. Each suite was growing its
own copy of that chain -- `webapi_tests` had a private `_a_form_class` that
rebuilt what `database_tests` already had -- and two copies of a fixture drift
in exactly the way that makes a failure hard to read.

These are plain functions rather than pytest fixtures on purpose: nothing here
is test-only. Seeding a development database is the same job.

Each builder creates whatever it depends on, so a test asks for the one thing it
is about:

    a_grade()   -> grade -> enrolment -> student -> form class -> year, teacher
"""

from database.models import (SchoolYear, Subject, Teacher, FormClass, Student,
                             Enrolment, Grade)
from database.controllers import (SchoolYearDbCtrl, SubjectDbCtrl, TeacherDbCtrl,
                                  FormClassDbCtrl, StudentDbCtrl, EnrolmentDbCtrl,
                                  GradeDbCtrl)


def a_school_year(code='2026-2027'):
    year = SchoolYear(code=code, starts_on=date(2026, 9, 1), ends_on=date(2027, 7, 20))
    SchoolYearDbCtrl.save(None, year)
    return year


def a_teacher(staff_number='T-001'):
    teacher = Teacher(staff_number=staff_number, first_name='Ada', last_name='Byron')
    TeacherDbCtrl.save(None, teacher)
    return teacher


def a_subject(code='MATH'):
    subject = Subject(code=code, name='Mathematics')
    SubjectDbCtrl.save(None, subject)
    return subject


def a_form_class(name='9B'):
    form = FormClass(school_year_id=a_school_year().id, form_tutor_id=a_teacher().id,
                     name=name, year_group=9)
    FormClassDbCtrl.save(None, form)
    return form


def a_student(admission_number='ADM-0001'):
    student = Student(form_class_id=a_form_class().id, admission_number=admission_number,
                      first_name='Alan', last_name='Turing',
                      date_of_birth=date(2012, 6, 23), enrolled_on=date(2026, 9, 1))
    StudentDbCtrl.save(None, student)
    return student


def an_enrolment():
    enrolment = Enrolment(student_id=a_student().id, subject_id=a_subject().id,
                          enrolled_on=date(2026, 9, 5), status='ACT')
    EnrolmentDbCtrl.save(None, enrolment)
    return enrolment


def a_grade(value='A'):
    grade = Grade(enrolment_id=an_enrolment().id, value=value, assessed_on=date(2027, 1, 15))
    GradeDbCtrl.save(None, grade)
    return grade


def a_school(students=3, subjects=2):
    """A whole small school, for tests that need a populated database rather
    than one specific row -- paging, searching, and the API list endpoints."""
    year = a_school_year()
    tutor = a_teacher()
    form = FormClass(school_year_id=year.id, form_tutor_id=tutor.id,
                     name='9B', year_group=9)
    FormClassDbCtrl.save(None, form)

    made_subjects = []
    for i in range(subjects):
        subject = Subject(code=f'SUB{i}', name=f'Subject {i}')
        SubjectDbCtrl.save(None, subject)
        made_subjects.append(subject)

    made_students = []
    for i in range(students):
        student = Student(form_class_id=form.id,
                          admission_number=f'ADM-{i + 1:04d}',
                          first_name=f'First{i}', last_name=f'Last{i}',
                          date_of_birth=date(2012, 1, 1 + i),
                          enrolled_on=date(2026, 9, 1))
        StudentDbCtrl.save(None, student)
        made_students.append(student)
        for subject in made_subjects:
            EnrolmentDbCtrl.save(None, Enrolment(
                student_id=student.id, subject_id=subject.id,
                enrolled_on=date(2026, 9, 5), status='ACT'))

    return {'school_year': year, 'teacher': tutor, 'form_class': form,
            'subjects': made_subjects, 'students': made_students}
