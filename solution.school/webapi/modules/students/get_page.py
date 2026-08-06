from devfx.ux.webapi import DataPageRequest, DataPageResponse, DataPageSpecs
from devfx.ux.webapi.fastapi import route_wrapper
from devfx.data_retrieval_specs import FilteringSpec
from webapi.app import app
from database.models import Student
from database.controllers import StudentDbCtrl
from .student_data import StudentData

"""----------------------------------------------------------------
"""
class GetStudentDataPageRequest(DataPageRequest):
    pass

"""----------------------------------------------------------------
"""
class GetStudentDataPageResponse(DataPageResponse[StudentData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/get-page', tags=['StudentData'], operation_id='getPage')
@route_wrapper
async def get_page(request: GetStudentDataPageRequest) -> GetStudentDataPageResponse:
    try:
        filtering_spec = None
        if request.filtering_spec and request.filtering_spec.rule == 'search' and request.filtering_spec.args:
            search_term = request.filtering_spec.args[0].strip() if request.filtering_spec.args[0] else None
            if search_term:
                rule = ("Student.last_name LIKE :arg0 OR Student.first_name LIKE :arg0"
                        " OR Student.admission_number LIKE :arg0")
                filtering_spec = FilteringSpec(rule=rule, args=[f"%{search_term}%"])

        page = StudentDbCtrl.get_page(
            None,
            filtering_spec=filtering_spec,
            sorting_spec=request.sorting_spec,
            pagination_spec=request.pagination_spec
        )

        return GetStudentDataPageResponse(
            data_list=[StudentData.map_from(_) for _ in page.instances],
            page_specs=DataPageSpecs(
                page_size=page.page_size,
                page_number=page.page_number,
                total_items_count=page.total_instances_count
            )
        )
    except Exception as e:
        response = GetStudentDataPageResponse()
        response.add_error(f'An error occurred while retrieving student page: {str(e)}')
        return response
