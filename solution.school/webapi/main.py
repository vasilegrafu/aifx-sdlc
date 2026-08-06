import os
import uvicorn
from webapi.app import app
from config import Environment

if __name__ == '__main__':
    # Server configuration
    host = os.getenv('API_HOST', 'localhost')
    port = int(os.getenv('API_PORT', '64266'))

    # environment.json decides, and this only reads it. Passing an environment
    # in here would make the server a config-mutating tool, and let a deployment
    # overwrite the value its image was built with.
    environment = Environment.get()

    # Development mode settings
    is_development = environment.lower() in ('dev')
    reload = is_development
    log_level = "debug" if is_development else "info"

    # Print startup information
    print("=" * 60)
    print(f"Starting FastAPI server ({environment} mode)")
    print("=" * 60)
    print(f"API Endpoint:       http://{host}:{port}")
    print(f"Interactive Docs:   http://{host}:{port}/docs")
    print(f"Auto-reload:        {'Enabled' if reload else 'Disabled'}")
    print("=" * 60)

    # Run the FastAPI application with uvicorn
    uvicorn.run(
        "webapi.app:app",  # Use string import for reload to work
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
        access_log=True,
    )
