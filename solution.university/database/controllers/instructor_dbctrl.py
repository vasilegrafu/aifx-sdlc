from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Instructor


class InstructorDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, instructor):
        StandardDbCtrl(session).save(instructor)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Instructor, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Instructor)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Instructor)\
                                        .filter(Instructor.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Instructor)\
                                        .filter(Instructor.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_staff_number(session, staff_number):
        return StandardDbCtrl(session).select(Instructor)\
                                        .filter(Instructor.staff_number == staff_number)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_email(session, email):
        return StandardDbCtrl(session).select(Instructor)\
                                        .filter(Instructor.email == email)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_department_id(session, department_id):
        return StandardDbCtrl(session).select(Instructor)\
                                        .filter(Instructor.department_id == department_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Instructor)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Instructor)\
                                .filter(Instructor.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Instructor)\
                                .filter(Instructor.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_department_id(session, department_id):
        StandardDbCtrl(session).select(Instructor)\
                                .filter(Instructor.department_id == department_id)\
                                .delete()
