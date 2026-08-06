from sqlalchemy import event
from sqlalchemy.engine import Engine

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas, forced by the target.

SQLite parses `ondelete='CASCADE'` and then ignores it: foreign keys are off by
default, per connection. Nothing errors -- the constraint is declared, accepted
and never enforced, and the first sign of it is an orphaned row much later.

The listener is on `Engine` itself rather than on one engine, because every
connection needs the pragma and an engine built elsewhere would otherwise be
silently unprotected.
"""
@event.listens_for(Engine, 'connect')
def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
    if 'sqlite' not in type(dbapi_connection).__module__:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()
