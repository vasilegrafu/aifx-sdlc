from sqlalchemy import create_engine
from config import Configuration, ConfigurationLoader
from database.base_database_model import BaseDatabaseModel
from database.database_url import APP_ROOT, resolve, database_file
from database import sqlite_foreign_keys  # noqa: F401  -- registers the pragma listener

# Importing the models package registers every model on the shared metadata.
# This one line is the whole registration chain: break it and the tables are
# simply never created, with nothing raising.
import database.models

"""------------------------------------------------------------------------------------------------
"""
DATABASE_NAME = 'database'

STORAGE_DIR = APP_ROOT / 'database_storage'

"""------------------------------------------------------------------------------------------------
"""
def drop_and_create_database(url: str):
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = database_file(url)
    if path is not None:
        path.unlink(missing_ok=True)

def generate():
    url = resolve(Configuration.get('database:url'))
    drop_and_create_database(url)
    engine = create_engine(url)
    BaseDatabaseModel.metadata.create_all(engine)

"""------------------------------------------------------------------------------------------------
"""
if __name__ == '__main__':
    ConfigurationLoader.load()

    generate()

    url = Configuration.get('database:url')
    print(f'{DATABASE_NAME}: {len(BaseDatabaseModel.metadata.tables)} tables '
          f'in {database_file(url) or url}')
