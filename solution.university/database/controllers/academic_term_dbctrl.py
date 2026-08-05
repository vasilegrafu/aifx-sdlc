from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import AcademicTerm


class AcademicTermDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, academic_term):
        StandardDbCtrl(session).save(academic_term)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(AcademicTerm, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(AcademicTerm)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(AcademicTerm)\
                                        .filter(AcademicTerm.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(AcademicTerm)\
                                        .filter(AcademicTerm.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_code(session, code):
        return StandardDbCtrl(session).select(AcademicTerm)\
                                        .filter(AcademicTerm.code == code)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_academic_year(session, academic_year):
        return StandardDbCtrl(session).select(AcademicTerm)\
                                        .filter(AcademicTerm.academic_year == academic_year)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(AcademicTerm)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(AcademicTerm)\
                                .filter(AcademicTerm.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(AcademicTerm)\
                                .filter(AcademicTerm.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_academic_year(session, academic_year):
        StandardDbCtrl(session).select(AcademicTerm)\
                                .filter(AcademicTerm.academic_year == academic_year)\
                                .delete()
