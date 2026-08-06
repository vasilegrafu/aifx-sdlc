from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import FormClass

class FormClassDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, form_class_spec):
        StandardDbCtrl(session).save(form_class_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(FormClass, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(FormClass)\
                                      .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(FormClass)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(FormClass)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(FormClass)\
                                        .filter(FormClass.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(FormClass)\
                                        .filter(FormClass.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_school_year_id(session, school_year_id):
        return StandardDbCtrl(session).select(FormClass)\
                                        .filter(FormClass.school_year_id == school_year_id)\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_form_tutor_id(session, form_tutor_id):
        return StandardDbCtrl(session).select(FormClass)\
                                        .filter(FormClass.form_tutor_id == form_tutor_id)\
                                        .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(FormClass)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(FormClass)\
                                .filter(FormClass.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(FormClass)\
                                .filter(FormClass.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_school_year_id(session, school_year_id):
        StandardDbCtrl(session).select(FormClass)\
                                .filter(FormClass.school_year_id == school_year_id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_form_tutor_id(session, form_tutor_id):
        StandardDbCtrl(session).select(FormClass)\
                                .filter(FormClass.form_tutor_id == form_tutor_id)\
                                .delete()
