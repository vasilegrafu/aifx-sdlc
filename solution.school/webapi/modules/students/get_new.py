from devfx.ux.webapi import DataRequest, DataResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from .student_data import StudentData
import uuid

"""----------------------------------------------------------------
"""
class GetNewStudentDataRequest(DataRequest):
    pass

"""----------------------------------------------------------------
"""
class GetNewStudentDataResponse(DataResponse[StudentData]):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/get-new', tags=['StudentData'], operation_id='getNew')
@route_wrapper
async def get_new(request: GetNewStudentDataRequest) -> GetNewStudentDataResponse:
    try:
        data = StudentData(
            id=str(uuid.uuid4()),
            form_class_id=None,
            admission_number='',
            first_name='',
            last_name='',
            date_of_birth=None,
            enrolled_on=None
        )
        return GetNewStudentDataResponse(data=data)
    except Exception as e:
        response = GetNewStudentDataResponse()
        response.add_error(f'An error occurred while creating new student data: {str(e)}')
        return response
