from testing.builders import an_enrolment
from database.controllers import EnrolmentDbCtrl


# ----------------------------------------------------------------
def test_save_then_get_by_id():
    made = an_enrolment()

    got = EnrolmentDbCtrl.get_by_id(None, made.id)

    assert got is not None
    assert got.id == made.id


def test_get_all_returns_it():
    made = an_enrolment()

    assert made.id in [x.id for x in EnrolmentDbCtrl.get_all(None)]


def test_get_by_ids():
    made = an_enrolment()

    got = EnrolmentDbCtrl.get_by_ids(None, [made.id])

    assert [x.id for x in got] == [made.id]



# ----------------------------------------------------------------
def test_delete_by_id_removes_it():
    made = an_enrolment()

    EnrolmentDbCtrl.delete_by_id(None, made.id)

    assert EnrolmentDbCtrl.get_by_id(None, made.id) is None


def test_delete_all_empties_the_table():
    an_enrolment()

    EnrolmentDbCtrl.delete_all(None)

    assert EnrolmentDbCtrl.get_all(None) == []
