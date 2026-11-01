"""Start the development server: `python run.py` (or `flask run`)."""
from dotenv import load_dotenv

load_dotenv()

from backend import create_app  # noqa: E402  (load .env before reading config)

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
