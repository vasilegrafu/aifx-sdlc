from devfx.database.sqlalchemy.session_injector_builder import SessionInjectorBuilder
from devfx.database.sqlalchemy.isolation_levels import IsolationLevels
from .session_maker import SessionMaker

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas, forced by the target.

atlas is one line:

    session_injector = SessionInjectorBuilder(SessionMaker).build()

devfx defaults every session to READ COMMITTED, which SQL Server has and SQLite
does not -- it rejects the level outright, so every controller call would fail
at the point of opening a session.

The wrapper exists so the *departure lives here and only here*: the controllers
still write a bare `@session_injector`, exactly as the exemplars do. Putting
`@session_injector(isolation_level=...)` on seventy methods would spread one
platform fact across the whole layer and make every file differ from its model.
"""
_session_injector = SessionInjectorBuilder(SessionMaker).build()


def session_injector(fn=None, isolation_level=IsolationLevels.SERIALIZABLE):
    if fn is None:
        return _session_injector(isolation_level=isolation_level)
    return _session_injector(fn, isolation_level=isolation_level)
