from pydantic import Field
from uuid import UUID
from devfx.ux.webapi import DataRequest, DataResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import StudentDbCtrl
from .student_data import StudentData

"""----------------------------------------------------------------
"""
class GetStudentDataByIdRequest(DataRequest):
    id: UUID = Field()

"""----------------------------------------------------------------
"""
class GetStudentDataByIdResponse(DataResponse[StudentData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/get-by-id', tags=['StudentData'], operation_id='getById')
@route_wrapper
async def get_by_id(request: GetStudentDataByIdRequest) -> GetStudentDataByIdResponse:
    try:
        student = StudentDbCtrl.get_by_id(None, request.id)
        if student is None:
            response = GetStudentDataByIdResponse()
            response.add_error(f'No student found with id {request.id}')
            return response
        return GetStudentDataByIdResponse(data=StudentData.map_from(student))
    except Exception as e:
        response = GetStudentDataByIdResponse()
        response.add_error(f'An error occurred while retrieving student {request.id}: {str(e)}')
        return response
