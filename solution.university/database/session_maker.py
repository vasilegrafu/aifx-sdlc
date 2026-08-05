from devfx.database.sqlalchemy.session_maker_builder import SessionMakerBuilder
from config import Configuration, ConfigurationLoader
from .database_url import resolve
from . import sqlite_foreign_keys  # noqa: F401  -- registers the pragma listener

if (not Configuration.is_loaded()):
    ConfigurationLoader.load()

# resolve(), not the raw configured url: the sessions must open the same file the
# generator created, from whatever directory the process was started in.
SessionMaker = SessionMakerBuilder.build(database_name='database',
                                         database_url=resolve(Configuration.get('database:url')))
