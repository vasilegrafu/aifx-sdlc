from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import ProgramEnrollment


class ProgramEnrollmentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, program_enrollment):
        StandardDbCtrl(session).save(program_enrollment)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(ProgramEnrollment, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .filter(ProgramEnrollment.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .filter(ProgramEnrollment.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_student_id(session, student_id):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .filter(ProgramEnrollment.student_id == student_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_program_id(session, program_id):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .filter(ProgramEnrollment.program_id == program_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_status(session, status):
        return StandardDbCtrl(session).select(ProgramEnrollment)\
                                        .filter(ProgramEnrollment.status == status)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .filter(ProgramEnrollment.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .filter(ProgramEnrollment.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_student_id(session, student_id):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .filter(ProgramEnrollment.student_id == student_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_program_id(session, program_id):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .filter(ProgramEnrollment.program_id == program_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_status(session, status):
        StandardDbCtrl(session).select(ProgramEnrollment)\
                                .filter(ProgramEnrollment.status == status)\
                                .delete()
