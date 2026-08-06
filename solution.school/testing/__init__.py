"""Everything that tests the application, in one place.

    testing/builders.py   the data every suite needs, written once
    testing/database/     the models and controllers
    testing/webapi/       the endpoints, through TestClient
    testing/logic/        (empty)
    testing/webapp/       (empty -- the React layer's tests will live here)

Deliberately empty of imports. Re-exporting the builders from here would mean
that importing *any* test module pulls in `database.controllers`, and that
import binds the SessionMaker to whatever environment is current -- before
conftest.py has had the chance to pin it to `test`. The suite would then run
against the development database while appearing to work.
"""
