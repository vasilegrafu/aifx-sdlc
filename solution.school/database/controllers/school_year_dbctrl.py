from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import SchoolYear

class SchoolYearDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, school_year_spec):
        StandardDbCtrl(session).save(school_year_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(SchoolYear, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(SchoolYear)\
                                      .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(SchoolYear)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(SchoolYear)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(SchoolYear)\
                                        .filter(SchoolYear.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(SchoolYear)\
                                        .filter(SchoolYear.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_code(session, code):
        return StandardDbCtrl(session).select(SchoolYear)\
                                        .filter(SchoolYear.code == code)\
                                        .one_or_none()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(SchoolYear)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(SchoolYear)\
                                .filter(SchoolYear.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(SchoolYear)\
                                .filter(SchoolYear.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_code(session, code):
        StandardDbCtrl(session).select(SchoolYear)\
                                .filter(SchoolYear.code == code)\
                                .delete()
