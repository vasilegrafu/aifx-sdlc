from testing.builders import a_subject
from database.controllers import SubjectDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_subject()

    got = SubjectDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_subject()

    assert made.id in [x.id for x in SubjectDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_subject()

    got = SubjectDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]


def test_get_by_code():
    made = a_subject()

    got = SubjectDbCtrl.get_by_code(None, made.code)

    assert got is not None
    assert got.id == made.id



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_subject()

    SubjectDbCtrl.delete_by_id(None, made.id)

    assert SubjectDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_subject()

    SubjectDbCtrl.delete_all(None)

    assert SubjectDbCtrl.get_all(None) == []
