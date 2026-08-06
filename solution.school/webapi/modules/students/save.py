from pydantic import Field
from devfx.ux.webapi import OperationRequest, OperationResult, OperationResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.models import Student
from database.controllers import StudentDbCtrl
from .student_data import StudentData

"""----------------------------------------------------------------
"""
class SaveStudentDataRequest(OperationRequest):
    data: StudentData = Field()

"""----------------------------------------------------------------
"""
class SaveStudentDataResponse(OperationResponse):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/save', tags=['StudentData'], operation_id='save')
@route_wrapper
async def save(request: SaveStudentDataRequest) -> SaveStudentDataResponse:
    try:
        StudentDbCtrl.save_data(None, Student.id == request.data.id,
                                    id=request.data.id,
                                    form_class_id=request.data.form_class_id,
                                    admission_number=request.data.admission_number,
                                    first_name=request.data.first_name,
                                    last_name=request.data.last_name,
                                    date_of_birth=request.data.date_of_birth,
                                    enrolled_on=request.data.enrolled_on)

        response = SaveStudentDataResponse(result=OperationResult.SUCCESS)

        student = StudentDbCtrl.get_by_admission_number(None, admission_number=request.data.admission_number)
        student_data = StudentData.map_from(student)
        response.add_info(f'Student data saved successfully: {student_data}')

        return response
    except Exception as e:
        response = SaveStudentDataResponse(result=OperationResult.FAILURE)
        response.add_error(f'An error occurred while saving student with admission number {request.data.admission_number}: {str(e)}')
        return response
