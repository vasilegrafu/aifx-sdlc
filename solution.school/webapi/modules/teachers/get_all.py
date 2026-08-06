from devfx.ux.webapi import DataListRequest, DataListResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import TeacherDbCtrl
from .teacher_data import TeacherData

"""----------------------------------------------------------------
"""
class GetTeacherDataListRequest(DataListRequest):
    pass

"""----------------------------------------------------------------
"""
class GetTeacherDataListResponse(DataListResponse[TeacherData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/teachers/get-all', tags=['TeacherData'], operation_id='getAllTeachers')
@route_wrapper
async def get_all(request: GetTeacherDataListRequest) -> GetTeacherDataListResponse:
    try:
        instances = TeacherDbCtrl.get_all(None)
        return GetTeacherDataListResponse(data_list=[TeacherData.map_from(_) for _ in instances])
    except Exception as e:
        response = GetTeacherDataListResponse()
        response.add_error(f'An error occurred while retrieving the teacher list: {str(e)}')
        return response
