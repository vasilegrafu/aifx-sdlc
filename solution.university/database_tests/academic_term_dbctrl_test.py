from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from database.models import AcademicTerm
from database.controllers import AcademicTermDbCtrl
from database.enums import TermKind


def test_save_then_read_back(academic_term):
    read_back = AcademicTermDbCtrl.get_by_id(None, id=academic_term.id)
    assert read_back.academic_year == '2026/2027'
    assert read_back.starts_on == date(2026, 9, 1)
    assert read_back.ends_on == date(2027, 1, 31)


def test_get_by_code(academic_term):
    assert AcademicTermDbCtrl.get_by_code(None, code='2026-FALL').id == academic_term.id


def test_get_by_academic_year_returns_many(academic_term):
    AcademicTermDbCtrl.save(None, AcademicTerm(code='2026-SPRING',
                                               academic_year='2026/2027',
                                               kind=TermKind.SPRING.code,
                                               starts_on=date(2027, 2, 1),
                                               ends_on=date(2027, 6, 30)))
    found = AcademicTermDbCtrl.get_by_academic_year(None, academic_year='2026/2027')
    assert len(found) == 2


def test_kind_round_trips_through_the_enum(academic_term):
    read_back = AcademicTermDbCtrl.get_by_id(None, id=academic_term.id)
    assert TermKind.from_code(read_back.kind) is TermKind.FALL


def test_code_is_unique(academic_term):
    with pytest.raises(IntegrityError):
        AcademicTermDbCtrl.save(None, AcademicTerm(code='2026-FALL',
                                                   academic_year='2027/2028',
                                                   kind=TermKind.FALL.code,
                                                   starts_on=date(2027, 9, 1),
                                                   ends_on=date(2028, 1, 31)))
