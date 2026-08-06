from devfx.database.sqlalchemy.session_maker_builder import SessionMakerBuilder
from config import Configuration, ConfigurationLoader, Environment
from .database_url import resolve
import database.sqlite_foreign_keys        # noqa: F401  -- registers the pragma

if(not Configuration.is_loaded()):
    ConfigurationLoader.load()

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas, forced by the target.

atlas passes `Configuration.get('database:url')` straight through, because a
server url needs no resolving. A SQLite url carries a file path, so it goes
through `resolve` -- otherwise a session opened from one working directory and
a generator run from another quietly use two different files.

The pragma module is imported here as well as in the generator: the listener
must be registered before any engine connects, and a session made by a
controller is the other way in.

The name carries the environment, and that is not cosmetic. devfx caches the
engine in a process-global keyed on `database_name` alone, ignoring the url:

    build('school', 'sqlite:///B')  ->  actually bound to sqlite:///A

So a second SessionMaker built with the same name and a different database
silently hands back the first one. Deriving the name from the environment gives
each database its own key -- which is what lets the test session point at a test
database at all, and removes the same trap for dev against prod.

This binds at import. Whatever environment is in force when `database.*` is
first imported is the one this process uses, which is why the test session pins
it in conftest before importing anything from `database`.
"""
SessionMaker = SessionMakerBuilder.build(
    database_name=f'school.{Environment.get()}',
    database_url=resolve(Configuration.get('database:url')))
