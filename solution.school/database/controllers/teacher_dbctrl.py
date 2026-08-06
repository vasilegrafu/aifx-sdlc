from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import Teacher

class TeacherDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, teacher_spec):
        StandardDbCtrl(session).save(teacher_spec)

    @staticmethod
    @session_injector
    def save_data(session, criteria, **assigns):
        return StandardDbCtrl(session).save_data(Teacher, criteria, **assigns)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_all(session):
        return StandardDbCtrl(session).select(Teacher)\
                                      .all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(Teacher)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(Teacher)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Teacher)\
                                        .filter(Teacher.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Teacher)\
                                        .filter(Teacher.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_staff_number(session, staff_number):
        return StandardDbCtrl(session).select(Teacher)\
                                        .filter(Teacher.staff_number == staff_number)\
                                        .one_or_none()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def delete_all(session):
        StandardDbCtrl(session).select(Teacher)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_id(session, id):
        StandardDbCtrl(session).select(Teacher)\
                                .filter(Teacher.id == id)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_ids(session, ids):
        StandardDbCtrl(session).select(Teacher)\
                                .filter(Teacher.id.in_(ids))\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_staff_number(session, staff_number):
        StandardDbCtrl(session).select(Teacher)\
                                .filter(Teacher.staff_number == staff_number)\
                                .delete()
