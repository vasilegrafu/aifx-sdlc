from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import Enrolment

class EnrolmentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, enrolment_spec):
        StandardDbCtrl(session).save(enrolment_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Enrolment, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Enrolment)\
                                      .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(Enrolment)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(Enrolment)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Enrolment)\
                                        .filter(Enrolment.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Enrolment)\
                                        .filter(Enrolment.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_student_id(session, student_id):
        return StandardDbCtrl(session).select(Enrolment)\
                                        .filter(Enrolment.student_id == student_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_subject_id(session, subject_id):
        return StandardDbCtrl(session).select(Enrolment)\
                                        .filter(Enrolment.subject_id == subject_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Enrolment)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Enrolment)\
                                .filter(Enrolment.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Enrolment)\
                                .filter(Enrolment.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_student_id(session, student_id):
        StandardDbCtrl(session).select(Enrolment)\
                                .filter(Enrolment.student_id == student_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_subject_id(session, subject_id):
        StandardDbCtrl(session).select(Enrolment)\
                                .filter(Enrolment.subject_id == subject_id)\
                                .delete()
