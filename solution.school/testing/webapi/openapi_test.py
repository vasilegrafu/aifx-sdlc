import json
from pathlib import Path

from webapi.export_openapi import build, OUTPUT

"""------------------------------------------------------------------------------------------------
`webapi/openapi.json` is a committed artefact that nothing regenerates
automatically, so it can silently stop describing the API: an endpoint gets a
field, the file still says otherwise, and the generated TypeScript client is
built from the stale copy. Nothing errors -- the client simply omits a field
that exists, or sends one that does not.

`test_the_committed_spec_matches_the_code` is what makes the file trustworthy
rather than merely present. When it fails, the fix is to run the export -- task
`export solution.school/openapi.json`, or `python -m webapi.export_openapi`.

The stability test pins the reason the export strips `x-schema-uuid`: without
it two exports of an unchanged API differ by 50 lines, every regeneration of the
client shows a diff, and a real change is invisible among them.
"""


# ----------------------------------------------------------------
def test_the_committed_spec_matches_the_code():
    committed = json.loads(Path(OUTPUT).read_text(encoding='utf-8'))

    generated, _ = build()

    assert generated == committed, (
        'webapi/openapi.json is stale -- run `python -m webapi.export_openapi`')


def test_the_export_is_stable_across_runs():
    first, _ = build()
    second, _ = build()

    assert first == second


def test_the_export_carries_no_generated_uuids():
    schema, _ = build()

    assert 'x-schema-uuid' not in json.dumps(schema)
