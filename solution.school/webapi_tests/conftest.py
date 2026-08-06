import pytest
from fastapi.testclient import TestClient
from webapi.app import app

"""------------------------------------------------------------------------------------------------
The API is exercised through TestClient rather than a running server: no port,
no background process, and the same pytest run as everything else. It goes
through the real app object, so the route table, the request models and the
devfx route_wrapper are all under test -- only the network is not.

Database generation and per-test cleanup come from the root conftest.py.
"""
@pytest.fixture()
def client(database):
    with TestClient(app) as c:
        yield c
