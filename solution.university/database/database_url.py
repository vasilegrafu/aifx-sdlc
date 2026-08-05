from pathlib import Path

"""------------------------------------------------------------------------------------------------
A relative sqlite path in the configuration is relative to the application, not
to whatever directory something was launched from.

This lives on its own because two callers need the same answer: the generator,
which creates the file, and the session maker, which opens it. When only the
generator resolved the path, both worked from inside the application directory
and neither worked from anywhere else -- the tests failed with `unable to open
database file` the first time they ran from the repository root.
"""
APP_ROOT = Path(__file__).resolve().parents[1]
SQLITE_PREFIX = 'sqlite:///'


def resolve(url: str) -> str:
    if not url.startswith(SQLITE_PREFIX):
        return url
    path = Path(url[len(SQLITE_PREFIX):])
    return SQLITE_PREFIX + (path if path.is_absolute() else APP_ROOT / path).as_posix()


def database_file(url: str) -> Path | None:
    """The file the url actually points at, or None for a server database.

    Derived from the url and never from a name beside it: the two can disagree,
    and a drop that deletes a file the engine is not about to write is a drop
    that silently does nothing.
    """
    url = resolve(url)
    return Path(url[len(SQLITE_PREFIX):]) if url.startswith(SQLITE_PREFIX) else None
