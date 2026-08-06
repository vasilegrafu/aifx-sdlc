from devfx.ux.webapi import DataListRequest, DataListResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import StudentDbCtrl
from .student_data import StudentData

"""----------------------------------------------------------------
"""
class GetStudentDataListRequest(DataListRequest):
    pass

"""----------------------------------------------------------------
"""
class GetStudentDataListResponse(DataListResponse[StudentData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/get-list', tags=['StudentData'], operation_id='getList')
@route_wrapper
async def get_list(request: GetStudentDataListRequest) -> GetStudentDataListResponse:
    try:
        instances = StudentDbCtrl.get_list(None,
                                           filtering_spec=request.filtering_spec,
                                           sorting_spec=request.sorting_spec)
        return GetStudentDataListResponse(data_list=[StudentData.map_from(_) for _ in instances])
    except Exception as e:
        response = GetStudentDataListResponse()
        response.add_error(f'An error occurred while retrieving the student list: {str(e)}')
        return response
