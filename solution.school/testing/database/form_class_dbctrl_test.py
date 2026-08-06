from testing.builders import a_form_class
from database.controllers import FormClassDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = a_form_class()

    got = FormClassDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = a_form_class()

    assert made.id in [x.id for x in FormClassDbCtrl.get_all(None)]


def test_get_by_ids():
    made = a_form_class()

    got = FormClassDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = a_form_class()

    FormClassDbCtrl.delete_by_id(None, made.id)

    assert FormClassDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    a_form_class()

    FormClassDbCtrl.delete_all(None)

    assert FormClassDbCtrl.get_all(None) == []
