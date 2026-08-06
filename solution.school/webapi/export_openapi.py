"""
Export OpenAPI schema to file.

This script exports the FastAPI OpenAPI schema to openapi.json file.
Useful for version control and offline client generation.

Usage:
    python -m webapi.export_openapi
"""

import json
from pathlib import Path
from collections import Counter
from config import ConfigurationLoader
from webapi.app import app

"""----------------------------------------------------------------
"""
OUTPUT = Path(__file__).resolve().parent / 'openapi.json'


def _without_schema_uuids(node):
    """
    devfx stamps `x-schema-uuid: uuid4()` onto every request, response and data
    model at *class definition* time -- `devfx/ux/webapi/{base_data,requests,
    responses}.py`. Within one process the value is fixed, so the spec is stable;
    across processes all 25 of them change, and two exports of an unchanged API
    differ by exactly 50 lines.

    That matters because the TypeScript client is generated from this file. Left
    in, every regeneration produces a diff whether or not the API moved, and a
    real change -- a removed field, a renamed operation -- arrives buried in
    noise that reviewers have already learned to skip.

    Dropped here rather than upstream: devfx is a linked library shared with
    atlas, and the key may well mean something to something else. This removes it
    from the exported artefact only.
    """
    if isinstance(node, dict):
        return {k: _without_schema_uuids(v)
                for k, v in node.items() if k != 'x-schema-uuid'}
    if isinstance(node, list):
        return [_without_schema_uuids(x) for x in node]
    return node


def build():
    """
    Building is separate from writing so that a test can ask what the code
    describes without also repairing the file it is checking. Called from
    `export()` it would silently overwrite a stale `openapi.json`, and the test
    that caught the staleness would pass on the next run.
    """
    schema = _without_schema_uuids(app.openapi())

    # operationId becomes the generated TypeScript client's method name, and the
    # OpenAPI spec requires it to be unique across the document. A duplicate does
    # not stop the export -- it produces a client with two methods of one name,
    # which is discovered in the React layer and blamed on the generator.
    ids = [op.get('operationId')
           for path in schema['paths'].values() for op in path.values()]
    duplicated = {k: n for k, n in Counter(ids).items() if k and n > 1}
    if duplicated:
        raise Exception(f'duplicate operationId(s), which the client cannot '
                        f'represent: {duplicated}')

    return schema, ids


def export():
    schema, ids = build()

    OUTPUT.write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
    return schema, ids


"""----------------------------------------------------------------
"""
if __name__ == '__main__':
    ConfigurationLoader.load()

    schema, ids = export()
    print(f'exported {len(schema["paths"])} paths, {len(ids)} operations -> {OUTPUT}')
