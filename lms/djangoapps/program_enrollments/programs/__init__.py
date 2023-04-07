"""
    - Module `workflows.py`:
        - The the functionalities are used in module of Service Discovery PROXY.
        - `CRUD` for programs/program user roles...
        - The Programs data are stored in Service Discovery's Database.

"""

from .workflows import (
    ProgramListLoader,
    ProgramCoursesLoader,
    ProgramCreator,
    ProgramLoader,
    CoursesLoader,
    ProgramCourseRegister,
    ProgramCourseReorder,
    ProgramPartialUpdate,
    ProgramEraser,
    ProgramCourseEraser
)
