from database_tests.fixtures import a_grade
from database.controllers import GradeDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_grade()

    got = GradeDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_grade()

    assert made.id in [x.id for x in GradeDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_grade()

    got = GradeDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_grade()

    GradeDbCtrl.delete_by_id(None, made.id)

    assert GradeDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_grade()

    GradeDbCtrl.delete_all(None)

    assert GradeDbCtrl.get_all(None) == []
