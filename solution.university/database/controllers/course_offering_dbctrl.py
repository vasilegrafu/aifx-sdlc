from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from ..models import CourseOffering


class CourseOfferingDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, course_offering):
        StandardDbCtrl(session).save(course_offering)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(CourseOffering, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .filter(CourseOffering.id == id)\
                                        .first()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .filter(CourseOffering.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_course_id(session, course_id):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .filter(CourseOffering.course_id == course_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_term_id(session, term_id):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .filter(CourseOffering.term_id == term_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_instructor_id(session, instructor_id):
        return StandardDbCtrl(session).select(CourseOffering)\
                                        .filter(CourseOffering.instructor_id == instructor_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(CourseOffering)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(CourseOffering)\
                                .filter(CourseOffering.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(CourseOffering)\
                                .filter(CourseOffering.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_course_id(session, course_id):
        StandardDbCtrl(session).select(CourseOffering)\
                                .filter(CourseOffering.course_id == course_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_term_id(session, term_id):
        StandardDbCtrl(session).select(CourseOffering)\
                                .filter(CourseOffering.term_id == term_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_instructor_id(session, instructor_id):
        StandardDbCtrl(session).select(CourseOffering)\
                                .filter(CourseOffering.instructor_id == instructor_id)\
                                .delete()
