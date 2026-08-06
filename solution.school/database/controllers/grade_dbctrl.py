from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import Grade

class GradeDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, grade_spec):
        StandardDbCtrl(session).save(grade_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Grade, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Grade)\
                                      .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(Grade)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(Grade)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Grade)\
                                        .filter(Grade.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Grade)\
                                        .filter(Grade.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_enrolment_id(session, enrolment_id):
        return StandardDbCtrl(session).select(Grade)\
                                        .filter(Grade.enrolment_id == enrolment_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Grade)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Grade)\
                                .filter(Grade.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Grade)\
                                .filter(Grade.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_enrolment_id(session, enrolment_id):
        StandardDbCtrl(session).select(Grade)\
                                .filter(Grade.enrolment_id == enrolment_id)\
                                .delete()
