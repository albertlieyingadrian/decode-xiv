# Visual arXiv

## Elevator pitch

Thousands of AI papers go up every day, but we're still stuck in static PDFs—broken code, missing datasets, equations that don't "click." **Visual ArXiv** turns any arXiv URL into a living experience: 2D animations that walk through the math, 3D views you can rotate and explore, and one-click runnable Colab notebooks. Visualize, reproduce, and understand—without wading through walls of text.

## Built with

**Languages:** Python, TypeScript, JavaScript  

**Frameworks:** FastAPI, Next.js, React  

**Google Cloud:** Google Cloud Build, Cloud Run (managed), Artifact Registry, Container Registry, Cloud Logging  

**Google APIs & AI:** Gemini API (Gemini 2.5 Flash), Google ADK (Agent Development Kit), Google Colab, Google Drive API, Google Identity Services (OAuth 2.0)  

**Other:** Manim Community (animation), PyMuPDF (PDF text extraction), Three.js / React Three Fiber / Drei (3D), Framer Motion, Tailwind CSS, react-pdf, arXiv API, Docker, OpenRouter (optional), LiteLLM (optional), Papers With Code API, Hugging Face  

**Comma list:** Python, TypeScript, JavaScript, FastAPI, Next.js, React, Google Cloud Build, Cloud Run (managed), Artifact Registry, Container Registry, Cloud Logging, Gemini API (Gemini 2.5 Flash), Google ADK (Agent Development Kit), Google Colab, Google Drive API, Google Identity Services (OAuth 2.0), Manim Community, PyMuPDF, Three.js, React Three Fiber, Drei, Framer Motion, Tailwind CSS, react-pdf, arXiv API, Docker, OpenRouter, LiteLLM, Papers With Code API, Hugging Face  

---

## Inspiration

Research papers, especially on arXiv are dense and abstract. We wanted to make them **immediately graspable**: turn a paper URL into animated explanations, interactive 3D views, and runnable code so anyone can visualize and reproduce the core ideas without wading through equations and prose. We were inspired by tools like 3Blue1Brown (Manim) and the need for better reproducibility and accessibility in ML/science.

## What it does

**Visual arXiv** turns an arXiv paper URL into a full visual and reproducible experience in one click:

- **2D concept animation**: Generates a Manim (Manim Community) video that illustrates the paper’s main idea from the title and abstract, with an automatic review-and-revision loop so the script actually runs.
- **3D architecture overview**: Produces a structured Three.js config (nodes/edges) for an interactive 3D view of models or concepts described in the paper.
- **Reproduce experiment**: Runs a 6-stage pipeline (paper parsing → spec extraction → external resource search → code planning → code generation → notebook assembly) to build a runnable Colab notebook that reproduces the paper’s core experiment, with optional “Open in Colab” via Google Drive.
- **Deep Dive mode**: Optionally downloads the PDF, extracts text by page, uses AI to identify sections, and generates section-by-section Manim animations with a side-by-side PDF + video viewer.

Users paste an arXiv URL, choose **Quick Visualize** or **Deep Dive (Section-by-Section)**, and get streaming progress, then results: summary, Manim video, 3D scene, and reproduction notebook (download or open in Colab).

## How we built it

- **Backend (FastAPI, Python)**  
  - arXiv metadata fetched via the `arxiv` client; PDFs downloaded for Deep Dive.  
  - **Manim workflow**: Gemini (or OpenRouter) generates initial Manim code + Three.js config from title/abstract; we run Manim in a subprocess, capture logs, and run multiple review cycles (standard or “enhanced” visual review based on success rate) with Gemini revising the script until it renders or we exhaust cycles. Rendered MP4s are served from `/static/videos/`.  
  - **Concept extraction**: Google ADK agent (Gemini) extracts key visual concepts from the paper to enrich the prompt for animation generation.  
  - **Reproduction pipeline**: A separate 6-stage pipeline (see `reproduce_pipeline.py`) parses the paper, extracts a reproducibility spec, searches Papers With Code / HuggingFace, plans and generates notebook cells, and assembles a `.ipynb`; it runs in parallel with the Manim workflow when using Quick Visualize.  
  - **Section-by-section**: PyMuPDF extracts text per page; Gemini identifies sections; we generate and render one Manim animation per section (with retries) and return PDF URL + section list with video URLs for the side-by-side viewer.  
  - All long-running work is streamed to the frontend as NDJSON (`status: step | complete | error`).

- **Frontend (Next.js, React, TypeScript)**  
  - Single page with mode toggle (Quick vs Deep Dive), arXiv URL input, and NDJSON streaming to drive a loading overlay and final result.  
  - Quick mode: paper info, Manim video player, Three.js scene (from `ThreeScene` + config), and Reproduce Experiment card (download notebook / Open in Colab via Google Drive).  
  - Deep Dive: `SideBySideMode` shows the PDF and section list with per-section videos (lazy-loaded with `react-pdf`).  
  - Framer Motion for layout and step transitions; styling with Tailwind.

- **Deployment**  
  - Backend and frontend have Dockerfiles; `deploy_gcp.sh` and `cloudbuild.yaml` target Google Cloud (e.g. Cloud Run).  
  - Backend needs `GEMINI_API_KEY`; optional `OPENROUTER_API_KEY` for OpenRouter; optional Google OAuth for Colab upload.

## Challenges we ran into

- **Manim correctness**: The model often produced invalid Manim (wrong APIs, `MathTex` without LaTeX, `VGroup` with non-VMobjects, etc.). We added strict prompt rules and a multi-cycle review loop that feeds execution logs back to the LLM and re-renders until success or max cycles.
- **JSON from the LLM**: Gemini sometimes returned JSON with comments or minor syntax issues. We added robust parsing (find first `{`/last `}`, strip `//` comments, fallback to `ast.literal_eval`) so we could reliably get `manim_code` and `threejs_config`.
- **Coordinating two long pipelines**: Quick Visualize runs the Manim workflow and the reproduction pipeline in parallel and streams progress from both; we used a shared queue and drained it in the async generator so the frontend sees a single coherent stream.
- **Section-by-section scale**: Generating many section animations can hit rate limits and take a long time; we added retries, clearer rate-limit error messages, and optional parallel section generation with a cap (e.g. 4 workers) to balance speed and API limits.
- **Colab integration**: Opening the reproduction notebook in Colab required uploading the `.ipynb` to Google Drive and opening the Colab link; we added optional Google OAuth and a dedicated “Open in Colab” flow in the frontend.

## Accomplishments that we're proud of

- **End-to-end from URL to video + 3D + notebook** with a single submit and clear streaming UX.  
- **Self-correcting Manim pipeline** (review → revise → re-render) so many papers produce a working animation without manual fixes.  
- **Dual mode**: quick “one animation + 3D + reproduce” vs deep “PDF + per-section animations” in one app.  
- **Reproduction pipeline** that goes from abstract to runnable Colab notebook with external resource search (Papers With Code, HuggingFace) and structured code generation.  
- **Google ADK** integration for concept extraction, improving the quality of what we ask the animation model to visualize.  
- **Deployable stack** with Docker and GCP config so the app can run in the cloud.

## What we learned

- Manim’s API and execution environment (e.g. no LaTeX) need to be encoded very explicitly in prompts and validated via real runs; log feedback is essential.  
- Streaming NDJSON from FastAPI and consuming it in the frontend (ReadableStream, line-by-line parse) gives a much better UX for long jobs than a single blocking request.  
- Running Manim and reproduction in parallel improves perceived speed but requires careful progress aggregation and error handling so one failure doesn’t hide the other’s result.  
- Section-level PDF parsing plus LLM section detection works well for structured papers; handling messy layouts and non-English text is still an area to improve.

## What's next

- **Caching**: Cache Manim videos and reproduction notebooks by arXiv ID to avoid re-running for the same paper.  
- **Better 3D**: Use the Three.js config for more than a static schema e.g. animate transitions, link nodes to paper sections.  
- **More animation backends**: Support other engines (e.g. Lottie, or headless browser for D3/svg) for papers where Manim is less suitable.  
- **Reproduction quality**: Add execution checks (run notebook in Colab or a kernel) and surface success/failure and diff from paper results.  
- **Accessibility**: Transcripts or captions for animations, and `prefers-reduced-motion` support.  
- **Cost and limits**: Smarter batching, queueing, and rate-limit handling for section-by-section and reproduction so the app scales for many users.
