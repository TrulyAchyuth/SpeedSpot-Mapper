"""Production entry point: `gunicorn wsgi:app`."""
from dotenv import load_dotenv

load_dotenv()

from backend import create_app  # noqa: E402

app = create_app("production")
