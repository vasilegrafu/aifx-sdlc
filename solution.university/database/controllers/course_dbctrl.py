from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Course


class CourseDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, course):
        StandardDbCtrl(session).save(course)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Course, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Course)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Course)\
                                        .filter(Course.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Course)\
                                        .filter(Course.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_code(session, code):
        return StandardDbCtrl(session).select(Course)\
                                        .filter(Course.code == code)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_department_id(session, department_id):
        return StandardDbCtrl(session).select(Course)\
                                        .filter(Course.department_id == department_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Course)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Course)\
                                .filter(Course.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Course)\
                                .filter(Course.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_department_id(session, department_id):
        StandardDbCtrl(session).select(Course)\
                                .filter(Course.department_id == department_id)\
                                .delete()
