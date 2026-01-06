"""Entry point for uvicorn with reload support."""
# Import app from app.py to avoid namespace conflict with app/ directory
# We need to import from the file directly, not the package
import importlib.util
import os

# Get the path to app.py
app_py_path = os.path.join(os.path.dirname(__file__), "app.py")
spec = importlib.util.spec_from_file_location("app_module", app_py_path)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)

# Get the app object from the module
app = app_module.app

# This allows uvicorn to use "main:app" as the import string
__all__ = ["app"]
