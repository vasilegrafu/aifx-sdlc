from devfx.ux.webapi import DataListRequest, DataListResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import SchoolYearDbCtrl
from .school_year_data import SchoolYearData

"""----------------------------------------------------------------
"""
class GetSchoolYearDataListRequest(DataListRequest):
    pass

"""----------------------------------------------------------------
"""
class GetSchoolYearDataListResponse(DataListResponse[SchoolYearData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/school-years/get-all', tags=['SchoolYearData'], operation_id='getAllSchoolYears')
@route_wrapper
async def get_all(request: GetSchoolYearDataListRequest) -> GetSchoolYearDataListResponse:
    try:
        instances = SchoolYearDbCtrl.get_all(None)
        return GetSchoolYearDataListResponse(data_list=[SchoolYearData.map_from(_) for _ in instances])
    except Exception as e:
        response = GetSchoolYearDataListResponse()
        response.add_error(f'An error occurred while retrieving the school year list: {str(e)}')
        return response
