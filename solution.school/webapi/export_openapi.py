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


def export():
    schema = app.openapi()

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

    OUTPUT.write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
    return schema, ids


"""----------------------------------------------------------------
"""
if __name__ == '__main__':
    ConfigurationLoader.load()

    schema, ids = export()
    print(f'exported {len(schema["paths"])} paths, {len(ids)} operations -> {OUTPUT}')
