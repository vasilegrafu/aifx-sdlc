from pydantic import Field
from uuid import UUID
from devfx.ux.webapi import OperationRequest, OperationResult, OperationResponse
from devfx.ux.webapi.fastapi import route_wrapper
from webapi.app import app
from database.controllers import StudentDbCtrl

"""----------------------------------------------------------------
"""
class DeleteStudentDataByIdRequest(OperationRequest):
    id: UUID = Field()

"""----------------------------------------------------------------
"""
class DeleteStudentDataByIdResponse(OperationResponse):
    pass

"""----------------------------------------------------------------
"""
@app.post('/students/delete-by-id', tags=['StudentData'], operation_id='deleteById')
@route_wrapper
async def delete_by_id(request: DeleteStudentDataByIdRequest) -> DeleteStudentDataByIdResponse:
    try:
        StudentDbCtrl.delete_by_id(None, request.id)

        response = DeleteStudentDataByIdResponse(result=OperationResult.SUCCESS)
        response.add_info(f'Student {request.id} deleted successfully')
        return response
    except Exception as e:
        response = DeleteStudentDataByIdResponse(result=OperationResult.FAILURE)
        response.add_error(f'An error occurred while deleting student {request.id}: {str(e)}')
        return response
