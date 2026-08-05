from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Program


class ProgramDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, program):
        StandardDbCtrl(session).save(program)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Program, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Program)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Program)\
                                        .filter(Program.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Program)\
                                        .filter(Program.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_code(session, code):
        return StandardDbCtrl(session).select(Program)\
                                        .filter(Program.code == code)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_department_id(session, department_id):
        return StandardDbCtrl(session).select(Program)\
                                        .filter(Program.department_id == department_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Program)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Program)\
                                .filter(Program.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Program)\
                                .filter(Program.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_department_id(session, department_id):
        StandardDbCtrl(session).select(Program)\
                                .filter(Program.department_id == department_id)\
                                .delete()
