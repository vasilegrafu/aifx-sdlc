from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Department


class DepartmentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, department):
        StandardDbCtrl(session).save(department)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Department, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Department)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Department)\
                                        .filter(Department.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Department)\
                                        .filter(Department.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_code(session, code):
        return StandardDbCtrl(session).select(Department)\
                                        .filter(Department.code == code)\
                                        .first()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Department)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Department)\
                                .filter(Department.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Department)\
                                .filter(Department.id.in_(ids))\
                                .delete()
