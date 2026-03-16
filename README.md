## DecodeXiv

**DecodeXiv** turns any arXiv URL into a living experience: 2D animations that walk through the math, 3D views you can rotate and explore, and one-click runnable Colab notebooks generated from the paper.

For full project background see `PROJECT.md`. For UI screenshots and captions see `docs/README.md`.

---

## Reproducible Testing Instructions

These steps let anyone (including judges) run and test the project end-to-end on their own machine.

### 1. Prerequisites

- **Python** 3.10+  
- **Node.js** 18+ and **npm** or **pnpm**  
- **ffmpeg** (required by Manim for video rendering)  
- A **Gemini API key** with access to **Gemini 2.5 Flash**

### 2. Environment variables

Create a `.env` file in the `backend/` directory:

```bash
cd backend
cp .env.example .env  # if present, otherwise create it
```

Ensure at least:

```bash
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Optional but supported:

- `OPENROUTER_API_KEY` for OpenRouter-based LLMs  
- Google OAuth / Drive variables for “Open in Colab” (see comments in `backend/main.py` if you want this fully wired up)

### 3. Run the backend (FastAPI)

From the repo root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

- Open `http://localhost:8000/health` and expect a small JSON payload.

### 4. Run the frontend (Next.js)

In a new terminal, from the repo root:

```bash
cd frontend
npm install  # or pnpm install
npm run dev
```

Then open `http://localhost:3000` in your browser.

By default the frontend is configured to call the backend at `http://localhost:8000`. If you change ports or run through a tunnel, update the backend URL in the frontend config (look for `NEXT_PUBLIC_BACKEND_URL` or the hard-coded base URL in `src/app/page.tsx`).

### 5. End-to-end test scenario

Once both services are running:

1. Go to `http://localhost:3000`.  
2. Paste a known-good arXiv URL, for example:  
   - `https://arxiv.org/abs/1706.03762` (Attention Is All You Need)  
   - `https://arxiv.org/abs/1512.03385` (ResNet)  
3. Choose **Quick Visualize** and click the main action button.
4. Observe streaming progress messages (fetching paper, generating animation, running reproduction pipeline).
5. Verify that you get:
   - A paper **summary** (title, authors, abstract).  
   - A **Manim video** illustrating the main idea.  
   - A **3D architecture view** (interactive graph).  
   - A **Reproduce Experiment** card with a downloadable notebook (and optional “Open in Colab” if configured).

This full flow is what judges can use to verify that the project works as intended.

### 6. Deep Dive mode test

To test the section-by-section Deep Dive:

1. On the home screen, select **Deep Dive (Section-by-Section)**.  
2. Use the same arXiv URL as above.  
3. Wait for the PDF + section list to load.  
4. Click a section in the list and confirm that a **per-section Manim animation** plays alongside the PDF.  

This validates the PDF parsing, section detection, and multi-animation pipeline.

### 7. Optional: Docker / Cloud Run

The repo also includes:

- `backend/Dockerfile` and `frontend/Dockerfile`  
- `cloudbuild.yaml` and `deploy_gcp.sh`

Judges can optionally:

- Build and run containers locally:

  ```bash
  # backend
  docker build -t decode-arxiv-backend ./backend
  docker run -p 8000:8000 -e GEMINI_API_KEY=YOUR_GEMINI_API_KEY decode-arxiv-backend

  # frontend
  docker build -t decode-arxiv-frontend ./frontend
  docker run -p 3000:3000 -e NEXT_PUBLIC_BACKEND_URL=http://host.docker.internal:8000 decode-arxiv-frontend
  ```

- Or use `deploy_gcp.sh` and `cloudbuild.yaml` to deploy backend and frontend to Cloud Run (see inline comments in those files for the exact commands and required GCP project settings).

In all cases, the test flow is the same: open the frontend, paste an arXiv URL, and confirm that the animations, 3D view, and reproduction notebook are generated successfully.

# decode-arxiv

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
