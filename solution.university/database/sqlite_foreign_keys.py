import sqlite3
from sqlalchemy import event
from sqlalchemy.engine import Engine

"""------------------------------------------------------------------------------------------------
SQLite ignores foreign keys unless every connection is told otherwise. Without
this, `ondelete='CASCADE'` is declared and never enforced: deleting a student
leaves their enrollments behind, nothing raises, and the database looks healthy
until something reads a row whose parent is gone.

The listener is registered on Engine itself rather than on one engine, because
this application has more than one and does not create them in the same place:
the generator builds its own, and the session maker in the shared library builds
another on first use. A rule attached to only one of them would hold while the
schema was created and lapse the moment a controller wrote anything.
"""
@event.listens_for(Engine, 'connect')
def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()
