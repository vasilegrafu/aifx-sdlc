from pathlib import Path

"""------------------------------------------------------------------------------------------------
"""
APPLICATION_ROOT = Path(__file__).resolve().parents[1]

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas, forced by the target.

atlas's url names a server, so no caller has to resolve anything. A SQLite url
carries a *file path*, and a relative one resolves against the working
directory -- so the generator and anything that opens a session agree only
while both run from the application root, and disagree from anywhere else
without either of them failing.

The rule therefore lives in one place and every caller uses it.
"""
PREFIX = 'sqlite:///'

def resolve(url: str) -> str:
    if not url.startswith(PREFIX):
        return url
    path = Path(url[len(PREFIX):])
    return url if path.is_absolute() else f'{PREFIX}{(APPLICATION_ROOT / path).as_posix()}'

def database_file(url: str) -> Path | None:
    """The file a SQLite url points at, or None for a server url."""
    resolved = resolve(url)
    return Path(resolved[len(PREFIX):]) if resolved.startswith(PREFIX) else None
