# PaperTrail – Prototype

A first working prototype: an HTML/JS frontend that talks to a Flask backend.

```
frontend pages  ──fetch──►  Flask API (localhost:5001)
                                             GET  /health
                                             POST /auth/register → create account (name, email and/or phone), returns token
                                             POST /auth/login    → log in with email or phone, returns token
                                             POST /auth/logout   → token stops working
                                             GET  /auth/me       → who is logged in
                                             POST /upload      → saves PDF, creates job
                                             GET  /jobs        → list of uploads
                                             GET  /status/<id> → one job
                                             POST /ask         → placeholder (not built yet)
```

## Run it (Mac)

**Terminal 1 – backend**
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

**Terminal 2 – frontend**
```bash
cd frontend
python3 -m http.server 8000
```

Open http://localhost:8000 in Chrome.

## Pages (frontend folder)
| Page | What it is |
|---|---|
| `index.html` | Home page with links to log in and register |
| `login.html` | Sign in with email or phone and password |
| `register.html` | Create an account: first name, last name, email and/or phone, password |
| `dashboard.html` | Upload PDFs, see your documents, ask questions (logged-in users only) |

Shared code is in `js/common.js`, page code in `js/auth.js` and `js/dashboard.js`, and all styles in `css/style.css`.

Port 5001 is used because macOS AirPlay Receiver already uses port 5000.

## What works now
- Home, login, registration and dashboard pages
- Sign up with first name, last name, email and/or phone; log in with email or phone
- Passwords stored as hashes; each user sees only their own documents
- Server status on the dashboard
- Upload a PDF by clicking or drag-and-drop
- Uploaded documents list with job status
- Chat box sends the question to `/ask` (returns "not built yet" for now)

## Next steps
- Store users and documents in the database (they reset when the server restarts for now)
- Redis job queue + worker process
- Extract text with pdfplumber, split into chunks
- Search inside documents, then real answers from `/ask`
