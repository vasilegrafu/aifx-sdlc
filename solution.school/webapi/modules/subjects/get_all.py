from devfx.ux.webapi import DataListRequest, DataListResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import SubjectDbCtrl
from .subject_data import SubjectData

"""----------------------------------------------------------------
"""
class GetSubjectDataListRequest(DataListRequest):
    pass

"""----------------------------------------------------------------
"""
class GetSubjectDataListResponse(DataListResponse[SubjectData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/subjects/get-all', tags=['SubjectData'], operation_id='getAllSubjects')
@route_wrapper
async def get_all(request: GetSubjectDataListRequest) -> GetSubjectDataListResponse:
    try:
        instances = SubjectDbCtrl.get_all(None)
        return GetSubjectDataListResponse(data_list=[SubjectData.map_from(_) for _ in instances])
    except Exception as e:
        response = GetSubjectDataListResponse()
        response.add_error(f'An error occurred while retrieving the subject list: {str(e)}')
        return response
