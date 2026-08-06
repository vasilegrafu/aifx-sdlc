"""The guard on the thing this suite is built to guarantee.

Everything else here tests the application. This tests the harness: that the
suite is bound to the *test* database and cannot reach development or
production data, whatever config/environment.json happens to say.

It is a real test rather than a comment because the binding is decided by import
order -- `database/session_maker.py` binds at import time -- and import order is
exactly the kind of thing a later refactor moves without noticing. Two ways to
break it silently: pin the environment after the first `database.*` import, or
re-export the builders from `testing/__init__.py` so importing any test module
pulls the database in first. Both leave every other test passing.
"""


def test_the_suite_is_bound_to_the_test_environment():
    from config import Environment

    assert Environment.get() == 'test'


def test_the_suite_is_bound_to_the_test_database():
    from database.session_maker import SessionMaker

    # The name matters as much as the url: devfx caches engines on the name and
    # ignores the url, so 'school' here would hand back whichever database was
    # opened first in this process.
    assert SessionMaker.database_name == 'school.test'
    assert 'school.test.sqlite3' in SessionMaker.database_url


def test_environment_json_is_untouched_by_the_test_run():
    import json
    from config.environment import ENVIRONMENT_FILE

    on_disk = json.loads(ENVIRONMENT_FILE.read_text(encoding='utf-8'))['environment']

    assert on_disk != 'test', ('the pin is process-local; environment.json '
                               'should still name a real environment')
