"""The generator is the thing that makes every other test possible.

A model that no `__init__` imports is never registered, never becomes a table,
and fails nowhere -- so the count is asserted rather than assumed.
"""
from sqlalchemy import create_engine, inspect

from config import Configuration
from database.base_database_model import BaseDatabaseModel
from database.database_url import resolve, database_file
from database.models import (Department, Program, Student, Instructor, AcademicTerm,
                             Course, CourseOffering, ProgramEnrollment, Enrollment)

EXPECTED = {Department, Program, Student, Instructor, AcademicTerm, Course,
            CourseOffering, ProgramEnrollment, Enrollment}


def test_every_model_is_registered_on_the_metadata():
    registered = set(BaseDatabaseModel.metadata.tables)
    for model in EXPECTED:
        assert model.__tablename__ in registered, \
            f'{model.__name__} is defined but nothing imports it into the metadata'


def test_the_generated_database_holds_every_table():
    engine = create_engine(resolve(Configuration.get('database:url')))
    tables = set(inspect(engine).get_table_names())
    assert {m.__tablename__ for m in EXPECTED} <= tables


def test_every_declared_index_exists():
    engine = create_engine(resolve(Configuration.get('database:url')))
    inspector = inspect(engine)
    for model in EXPECTED:
        declared = {index.name for index in model.__table__.indexes}
        created = {index['name'] for index in inspector.get_indexes(model.__tablename__)}
        assert declared <= created, f'{model.__name__} is missing {declared - created}'


def test_the_database_file_follows_the_configuration():
    """The drop targets the file the engine writes, not a constant beside it."""
    assert database_file(
        'sqlite:///database_storage/somewhere_else.db').name == 'somewhere_else.db'
    assert database_file('mssql+pyodbc://host/db') is None
