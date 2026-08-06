from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import ConfigurationLoader

# Load Configuration
ConfigurationLoader.load()

# Setup FastAPI Application
app = FastAPI(title="School WebAPI",
              description="FastAPI-based web API using devfx framework",
              version="1.0.0",
              docs_url="/docs",
              redoc_url="/redoc")

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=True,
                   allow_methods=["*"],
                   allow_headers=["*"])

# Health Check Endpoint
@app.get("/health", tags=["Health"], operation_id="healthCheck")
def health():
    return {
        "status": "healthy",
        "service": app.title,
        "version": app.version
    }

"""----------------------------------------------------------------
This import list IS the registration chain.

An endpoint module that is not imported here is never executed, so its
`@app.post(...)` never runs and the route simply does not exist. Nothing errors,
the file imports cleanly on its own, and the only symptom is a 404 from a path
that is right there in the source. Every new endpoint file adds a line here.
"""
# Students
import webapi.modules.students.get_page
import webapi.modules.students.get_list
import webapi.modules.students.get_by_id
import webapi.modules.students.get_new
import webapi.modules.students.save
import webapi.modules.students.delete_by_id

# Lookups
import webapi.modules.form_classes.get_all
import webapi.modules.subjects.get_all
import webapi.modules.school_years.get_all
import webapi.modules.teachers.get_all
