from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Student


class StudentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, student):
        StandardDbCtrl(session).save(student)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Student, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Student)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_registration_number(session, registration_number):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.registration_number == registration_number)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_email(session, email):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.email == email)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_status(session, status):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.status == status)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Student)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Student)\
                                .filter(Student.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Student)\
                                .filter(Student.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_status(session, status):
        StandardDbCtrl(session).select(Student)\
                                .filter(Student.status == status)\
                                .delete()
