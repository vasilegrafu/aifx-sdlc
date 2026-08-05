import functools
from devfx.database.sqlalchemy.session_injector_builder import SessionInjectorBuilder
from devfx.database.sqlalchemy.isolation_levels import IsolationLevels
from .session_maker import SessionMaker

# devfx defaults to READ COMMITTED. SQLite offers SERIALIZABLE, READ UNCOMMITTED
# and nothing else, so that default raises before a single controller runs.
# SERIALIZABLE is what SQLite does anyway, so this names the behaviour rather
# than changing it -- and it belongs here, in the application, because the choice
# follows the database this application was pointed at, not the library.
session_injector = functools.partial(SessionInjectorBuilder(SessionMaker).build(),
                                     isolation_level=IsolationLevels.SERIALIZABLE)
