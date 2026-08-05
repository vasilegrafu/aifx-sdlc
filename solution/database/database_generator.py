from pathlib import Path
from sqlalchemy import create_engine, event
from config import Configuration, ConfigurationLoader
from database.base_database_model import BaseDatabaseModel

# Importing the models package registers every model on the shared metadata.
# This one line is the whole registration chain: break it and the tables are
# simply never created, with nothing raising.
import database.models

"""------------------------------------------------------------------------------------------------
"""
DATABASE_NAME = 'university'

APP_ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = APP_ROOT / 'database_storage'

"""------------------------------------------------------------------------------------------------
"""
def storage_path(name: str) -> Path:
    return STORAGE_DIR / f'{name}.db'

def _resolve(url: str) -> str:
    """A relative sqlite path in the configuration is relative to the application,
    not to whatever directory the generator happened to be run from."""
    prefix = 'sqlite:///'
    if not url.startswith(prefix):
        return url
    path = Path(url[len(prefix):])
    return prefix + (path if path.is_absolute() else APP_ROOT / path).as_posix()

def drop_and_create_database(url: str):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    storage_path(DATABASE_NAME).unlink(missing_ok=True)

def configure_engine(engine):
    # Foreign keys are off by default in SQLite, and every pooled connection
    # needs the pragma rather than only the first. Without it the references are
    # declared and never enforced, which looks identical to working until
    # something orphans a row.
    @event.listens_for(engine, 'connect')
    def _on_connect(dbapi_connection, connection_record):
        dbapi_connection.execute('PRAGMA foreign_keys=ON')

def generate():
    url = _resolve(Configuration.get('database:url'))
    drop_and_create_database(url)
    engine = create_engine(url)
    configure_engine(engine)
    BaseDatabaseModel.metadata.create_all(engine)

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    ConfigurationLoader.load()

    generate()

    print(f'{DATABASE_NAME}: {len(BaseDatabaseModel.metadata.tables)} tables '
          f'in {storage_path(DATABASE_NAME)}')
