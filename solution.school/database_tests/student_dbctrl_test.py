from database_tests.fixtures import a_student
from database.controllers import StudentDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_student()

    got = StudentDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_student()

    assert made.id in [x.id for x in StudentDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_student()

    got = StudentDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]


def test_get_by_admission_number():
    made = a_student()

    got = StudentDbCtrl.get_by_admission_number(None, made.admission_number)

    assert got is not None
    assert got.id == made.id



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_student()

    StudentDbCtrl.delete_by_id(None, made.id)

    assert StudentDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_student()

    StudentDbCtrl.delete_all(None)

    assert StudentDbCtrl.get_all(None) == []
