from dotenv import load_dotenv

load_dotenv()  # read LLM settings from backend/.env (see .env.example)

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
