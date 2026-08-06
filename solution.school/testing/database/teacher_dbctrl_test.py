from testing.builders import a_teacher
from database.controllers import TeacherDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_teacher()

    got = TeacherDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_teacher()

    assert made.id in [x.id for x in TeacherDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_teacher()

    got = TeacherDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]


def test_get_by_staff_number():
    made = a_teacher()

    got = TeacherDbCtrl.get_by_staff_number(None, made.staff_number)

    assert got is not None
    assert got.id == made.id



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_teacher()

    TeacherDbCtrl.delete_by_id(None, made.id)

    assert TeacherDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_teacher()

    TeacherDbCtrl.delete_all(None)

    assert TeacherDbCtrl.get_all(None) == []
