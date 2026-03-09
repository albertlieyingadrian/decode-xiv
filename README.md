# visual-arxiv

Setup and run the ArXiv Animator backend and Next.js frontend.

---

## Prerequisites

- **Python 3.10+** (for backend)
- **Node.js 18+** and npm (for frontend)
- **Manim** (optional, for generating Manim animations; install via `pip install manim` or [manim community](https://docs.manim.community/))

---

## Backend setup

1. **Go to the backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   - Copy the example env file:
     ```bash
     cp .env.local.example .env
     ```
   - Edit `.env` and set at least:
     - `GEMINI_API_KEY` — get a key from [Google AI Studio](https://aistudio.google.com/apikey)
   - Optional: set `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` for OpenRouter, or Manim options (`MANIM_REVIEW_CYCLES`, `MANIM_SCENE_TIMEOUT`, etc.) as in the example.

5. **Run the API server**
   ```bash
   uvicorn main:app --reload
   ```
   Or use the helper script (stops anything on port 8000 first):
   ```bash
   ./start_backend.sh
   ```
   Backend runs at **http://localhost:8000**.

---

## Frontend setup

1. **Go to the frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Run the dev server**
   ```bash
   npm run dev
   ```
   Frontend runs at **http://localhost:3000**.

---

## Running the app

1. Start the **backend** first (in one terminal):
   ```bash
   cd backend && source venv/bin/activate && uvicorn main:app --reload
   ```

2. Start the **frontend** (in another terminal):
   ```bash
   cd frontend && npm run dev
   ```

3. Open **http://localhost:3000** in your browser. The frontend talks to the API at `http://localhost:8000` (CORS is set for `localhost:3000`).
