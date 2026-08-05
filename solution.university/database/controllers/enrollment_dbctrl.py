from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import Enrollment


class EnrollmentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, enrollment):
        StandardDbCtrl(session).save(enrollment)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Enrollment, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .filter(Enrollment.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .filter(Enrollment.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_student_id(session, student_id):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .filter(Enrollment.student_id == student_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_offering_id(session, offering_id):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .filter(Enrollment.offering_id == offering_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_status(session, status):
        return StandardDbCtrl(session).select(Enrollment)\
                                        .filter(Enrollment.status == status)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Enrollment)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Enrollment)\
                                .filter(Enrollment.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Enrollment)\
                                .filter(Enrollment.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_student_id(session, student_id):
        StandardDbCtrl(session).select(Enrollment)\
                                .filter(Enrollment.student_id == student_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_offering_id(session, offering_id):
        StandardDbCtrl(session).select(Enrollment)\
                                .filter(Enrollment.offering_id == offering_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_status(session, status):
        StandardDbCtrl(session).select(Enrollment)\
                                .filter(Enrollment.status == status)\
                                .delete()
