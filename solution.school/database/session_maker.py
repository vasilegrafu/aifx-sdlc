from devfx.database.sqlalchemy.session_maker_builder import SessionMakerBuilder
from config import Configuration, ConfigurationLoader
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
"""
SessionMaker = SessionMakerBuilder.build(database_name='school',
                                         database_url=resolve(Configuration.get('database:url')))
