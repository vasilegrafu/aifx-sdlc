import pytest

"""------------------------------------------------------------------------------------------------
Order matters here more than anywhere else in the application.

`database/session_maker.py` builds its SessionMaker at *import* time, from
whatever configuration is loaded then, and `session_injector` closes over it.
So the environment has to be settled before the first `database.*` import, and
after that nothing can change it. Pinning it below, before those imports, is the
whole mechanism -- move these lines under them and the suite silently runs
against the development database again.
"""
from config import Environment

# The one deliberate exception to "environment.json decides". It applies to this
# process only and never touches the file, which still reads `dev`. Without it
# the suite drops and recreates whichever database the file names -- on a day
# you had switched to prod, that is the prod database.
Environment.use_for_this_process('test')

from config import Configuration, ConfigurationLoader

if(not Configuration.is_loaded()):
    ConfigurationLoader.load()

from database.database_generator import generate
from database.controllers import (GradeDbCtrl, EnrolmentDbCtrl, StudentDbCtrl,
                                  FormClassDbCtrl, TeacherDbCtrl, SubjectDbCtrl,
                                  SchoolYearDbCtrl)


"""------------------------------------------------------------------------------------------------
One database for the session, emptied between tests.

A fresh database per test would be stricter and costs about 200ms each, which is
ten seconds across this suite and grows with every test added. Emptying the
tables buys the same independence for about two milliseconds, because nothing
here depends on identity columns or on schema state surviving a test.
"""
@pytest.fixture(scope='session', autouse=True)
def database():
    generate()


@pytest.fixture(autouse=True)
def empty_tables(database):
    # Children first: the cascade would do it, but an explicit order keeps a
    # failure here readable instead of arriving as a foreign key error.
    GradeDbCtrl.delete_all(None)
    EnrolmentDbCtrl.delete_all(None)
    StudentDbCtrl.delete_all(None)
    FormClassDbCtrl.delete_all(None)
    TeacherDbCtrl.delete_all(None)
    SubjectDbCtrl.delete_all(None)
    SchoolYearDbCtrl.delete_all(None)
