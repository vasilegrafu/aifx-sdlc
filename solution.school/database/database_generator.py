from sqlalchemy import create_engine
from config import Configuration, ConfigurationLoader
from database.base_database_model import BaseDatabaseModel
from database.database_url import resolve, database_file
import database.sqlite_foreign_keys        # noqa: F401  -- registers the pragma

# Importing the package registers its models on the shared metadata
import database.models

"""------------------------------------------------------------------------------------------------
"""
DATABASE_NAME = 'school'

"""------------------------------------------------------------------------------------------------
DEPARTURE from atlas, forced by the target.

atlas drops and creates through the server: `DROP DATABASE`, `CREATE DATABASE
... COLLATE ...`, then `CREATE SCHEMA` per domain. None of that exists in
SQLite, where a database is a file and a schema is nothing at all. What the
contract *means* -- start from empty, then create every table -- is reproduced;
the SQL it happens to emit is not.
"""
def drop_and_create_database(url: str):
    path = database_file(url)
    if path is None:
        raise Exception(f'not a SQLite url, and only SQLite is supported here: {url}')
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

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
