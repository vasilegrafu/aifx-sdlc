from devfx.database.sqlalchemy import StandardDbCtrl
from database.session_injector import session_injector
from database.models import Student

class StudentDbCtrl:
    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def save(session, student_spec):
        StandardDbCtrl(session).save(student_spec)

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
    def get_list(session, filtering_spec, sorting_spec):
        query = StandardDbCtrl(session).select(Student)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.all()

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_page(session, filtering_spec, sorting_spec, pagination_spec):
        query = StandardDbCtrl(session).select(Student)
        if filtering_spec:
            query = query.filter_by_spec(filtering_spec)
        if sorting_spec:
            query = query.order_by_spec(sorting_spec)
        return query.paginate_by_spec(pagination_spec)

    # ----------------------------------------------------------------
    @staticmethod
    @session_injector
    def get_by_id(session, id):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.id == id)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_ids(session, ids):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.id.in_(ids))\
                                        .all()

    @staticmethod
    @session_injector
    def get_by_admission_number(session, admission_number):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.admission_number == admission_number)\
                                        .one_or_none()

    @staticmethod
    @session_injector
    def get_by_form_class_id(session, form_class_id):
        return StandardDbCtrl(session).select(Student)\
                                        .filter(Student.form_class_id == form_class_id)\
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
    def delete_by_admission_number(session, admission_number):
        StandardDbCtrl(session).select(Student)\
                                .filter(Student.admission_number == admission_number)\
                                .delete()

    @staticmethod
    @session_injector
    def delete_by_form_class_id(session, form_class_id):
        StandardDbCtrl(session).select(Student)\
                                .filter(Student.form_class_id == form_class_id)\
                                .delete()
