import pytest

from config import Configuration, ConfigurationLoader

if(not Configuration.is_loaded()):
    ConfigurationLoader.load()

from database.database_generator import generate

"""------------------------------------------------------------------------------------------------
The tests follow environment.json like everything else -- there is no override
here, by choice. Switching to prod and running the suite therefore drops and
recreates the prod database. Reaching that state means deliberately editing
environment.json, which then shows as modified in git -- that visibility is what
keeps it from happening by accident.

One database, so one generation per session, and it lives here rather than in
each suite's conftest.

Both suites had their own session-scoped `generate()`, which worked while each
ran alone and failed the moment they ran together: the second one deletes the
SQLite file that the first suite's connections still hold open, and Windows
reports it as a PermissionError from a fixture that has nothing to do with the
test being run.
"""
@pytest.fixture(scope='session', autouse=True)
def database():
    generate()


@pytest.fixture(autouse=True)
def empty_tables(database):
    # Children first: the cascade would do it, but an explicit order keeps a
    # failure here readable instead of arriving as a foreign key error.
    from database.controllers import (GradeDbCtrl, EnrolmentDbCtrl, StudentDbCtrl,
                                      FormClassDbCtrl, TeacherDbCtrl, SubjectDbCtrl,
                                      SchoolYearDbCtrl)
    GradeDbCtrl.delete_all(None)
    EnrolmentDbCtrl.delete_all(None)
    StudentDbCtrl.delete_all(None)
    FormClassDbCtrl.delete_all(None)
    TeacherDbCtrl.delete_all(None)
    SubjectDbCtrl.delete_all(None)
    SchoolYearDbCtrl.delete_all(None)
