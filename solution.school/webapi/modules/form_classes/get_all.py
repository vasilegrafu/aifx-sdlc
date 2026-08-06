from devfx.ux.webapi import DataListRequest, DataListResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import FormClassDbCtrl
from .form_class_data import FormClassData

"""----------------------------------------------------------------
"""
class GetFormClassDataListRequest(DataListRequest):
    pass

"""----------------------------------------------------------------
"""
class GetFormClassDataListResponse(DataListResponse[FormClassData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/form-classes/get-all', tags=['FormClassData'], operation_id='getAllFormClasses')
@route_wrapper
async def get_all(request: GetFormClassDataListRequest) -> GetFormClassDataListResponse:
    try:
        instances = FormClassDbCtrl.get_all(None)
        return GetFormClassDataListResponse(data_list=[FormClassData.map_from(_) for _ in instances])
    except Exception as e:
        response = GetFormClassDataListResponse()
        response.add_error(f'An error occurred while retrieving the form class list: {str(e)}')
        return response
