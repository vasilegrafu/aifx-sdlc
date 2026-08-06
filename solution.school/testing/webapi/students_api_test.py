import uuid

from testing.builders import a_form_class

"""------------------------------------------------------------------------------------------------
Every endpoint answers 200 even when it fails: the layer never raises, it
returns a response carrying `has_errors` and `messages`. So a test that only
asserts the status code proves nothing -- each one below reads the body.
"""


# ----------------------------------------------------------------
def test_health_answers():
    from fastapi.testclient import TestClient
    from webapi.app import app
    with TestClient(app) as c:
        assert c.get('/health').json()['status'] == 'healthy'


# ----------------------------------------------------------------
def test_get_new_returns_a_blank_student_with_an_id():
    from fastapi.testclient import TestClient
    from webapi.app import app
    with TestClient(app) as c:
        body = c.post('/students/get-new', json={}).json()

    assert body['has_errors'] is False
    assert body['data']['id']
    assert body['data']['admission_number'] == ''


# ----------------------------------------------------------------
def test_save_then_get_page_finds_it(client):
    form = a_form_class()
    new = client.post('/students/get-new', json={}).json()['data']
    new.update(form_class_id=str(form.id), admission_number='ADM-0001',
               first_name='Alan', last_name='Turing',
               date_of_birth='2012-06-23', enrolled_on='2026-09-01')

    saved = client.post('/students/save', json={'data': new}).json()
    assert saved['result'] == 'SUCCESS', saved['messages']

    page = client.post('/students/get-page', json={
        'pagination_spec': {'page_size': 10, 'page_number': 1}}).json()
    assert page['has_errors'] is False, page['messages']
    assert 'ADM-0001' in [d['admission_number'] for d in page['data_list']]


def test_get_by_id_round_trips(client):
    form = a_form_class()
    new = client.post('/students/get-new', json={}).json()['data']
    new.update(form_class_id=str(form.id), admission_number='ADM-0002',
               first_name='Grace', last_name='Hopper',
               date_of_birth='2012-12-09', enrolled_on='2026-09-01')
    client.post('/students/save', json={'data': new})

    got = client.post('/students/get-by-id', json={'id': new['id']}).json()

    assert got['has_errors'] is False, got['messages']
    assert got['data']['last_name'] == 'Hopper'


def test_get_by_id_reports_a_missing_student_as_an_error_not_a_crash(client):
    got = client.post('/students/get-by-id', json={'id': str(uuid.uuid4())}).json()

    assert got['has_errors'] is True
    assert got['data'] is None


def test_delete_by_id_removes_it(client):
    form = a_form_class()
    new = client.post('/students/get-new', json={}).json()['data']
    new.update(form_class_id=str(form.id), admission_number='ADM-0003',
               first_name='Edsger', last_name='Dijkstra',
               date_of_birth='2012-05-11', enrolled_on='2026-09-01')
    client.post('/students/save', json={'data': new})

    deleted = client.post('/students/delete-by-id', json={'id': new['id']}).json()
    assert deleted['result'] == 'SUCCESS', deleted['messages']

    got = client.post('/students/get-by-id', json={'id': new['id']}).json()
    assert got['has_errors'] is True
