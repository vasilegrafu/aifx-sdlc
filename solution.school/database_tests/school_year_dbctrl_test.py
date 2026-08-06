from database_tests.fixtures import a_school_year
from database.controllers import SchoolYearDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_school_year()

    got = SchoolYearDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_school_year()

    assert made.id in [x.id for x in SchoolYearDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_school_year()

    got = SchoolYearDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]


def test_get_by_code():
    made = a_school_year()

    got = SchoolYearDbCtrl.get_by_code(None, made.code)

    assert got is not None
    assert got.id == made.id



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_school_year()

    SchoolYearDbCtrl.delete_by_id(None, made.id)

    assert SchoolYearDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_school_year()

    SchoolYearDbCtrl.delete_all(None)

    assert SchoolYearDbCtrl.get_all(None) == []
