from datetime import date

"""------------------------------------------------------------------------------------------------
The four lookups exist to fill dropdowns in the React edit form, so what matters
is that each answers with a list under its own operation and does not error.
"""


def test_every_lookup_answers_with_a_list(client):
    for path in ('/form-classes/get-all', '/subjects/get-all',
                 '/school-years/get-all', '/teachers/get-all'):
        body = client.post(path, json={}).json()
        assert body['has_errors'] is False, (path, body['messages'])
        assert isinstance(body['data_list'], list), path


def test_a_saved_subject_comes_back_from_its_lookup(client):
    from database.controllers import SubjectDbCtrl
    from database.models import Subject
    SubjectDbCtrl.save(None, Subject(code='MATH', name='Mathematics'))

    body = client.post('/subjects/get-all', json={}).json()

    assert 'MATH' in [d['code'] for d in body['data_list']]
