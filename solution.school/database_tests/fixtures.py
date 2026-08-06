from datetime import date
from uuid import uuid4

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
