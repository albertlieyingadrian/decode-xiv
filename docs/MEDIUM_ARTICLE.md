# How I Built Visual arXiv — Turning Dense Research Papers into Living Animations with Gemini and Google Cloud

*This piece of content was created for the purposes of entering the Gemini Live Agent Challenge hackathon. #GeminiLiveAgentChallenge*

---

Every day, thousands of AI papers appear on arXiv. And every day, researchers and students face the same ritual: open a PDF, wade through walls of equations, squint at static diagrams, and hope the ideas "click."

I wanted something better. What if you could paste a single URL and get back an animated video explaining the core concept, an interactive 3D model you can rotate and explore, and a runnable notebook that reproduces the paper's experiment?

That's **Visual arXiv**.

![Visual arXiv — Home screen with mode toggle and arXiv URL input](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-01.png)

## The Problem Nobody Talks About

Research papers are optimized for peer review, not for understanding. The format hasn't changed meaningfully in decades. Meanwhile, creators like 3Blue1Brown have proven that mathematical animation (via Manim) can make even abstract ideas instantly intuitive.

The gap was clear: the tooling to go from "paper" to "visual understanding" didn't exist as a single pipeline. You'd need to read the paper, understand it deeply, write Manim code by hand, build a 3D scene, and somehow also reproduce the experiment. Hours of work, per paper.

I wanted to collapse that into one click.

![User enters an arXiv URL and chooses a visualization mode](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-02.png)

## The Architecture: Gemini as the Brain, Google Cloud as the Backbone

Here's a high-level view of how Visual arXiv is put together:

![Visual arXiv system architecture](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-architecture.png)

The backend is a FastAPI service that orchestrates everything: fetching metadata from arXiv, running Gemini for code generation and concept extraction, executing Manim renders in subprocesses, and assembling reproduction notebooks. The frontend is a Next.js app that streams progress from the backend and renders the results.

### Gemini 2.5 Flash — The Core Intelligence

At the heart of Visual arXiv is **Gemini 2.5 Flash** via the Gemini API. It powers nearly every intelligent step in the pipeline:

**1. Manim Code Generation** — Given a paper's title and abstract, Gemini generates a complete, executable Manim Community script that illustrates the core idea as a 2D animation. This isn't just "summarize the paper." The model has to reason about which concept is most visual, how to represent it with mathematical objects, and produce valid Python that actually renders.

**2. Self-Correcting Review Loop** — Here's where it gets interesting. The first generated script often doesn't work. Manim's API is strict — wrong class names, missing imports, LaTeX calls in environments without LaTeX installed. So I built a multi-cycle review loop: Gemini generates code, I execute it, capture the error logs, and feed them back to Gemini asking it to fix the issues. It reviews its own work, revises, and we re-render. This loop runs up to three cycles, and the success rate jumped dramatically once I added it.

**3. Three.js Configuration** — Alongside the Manim script, Gemini produces a structured JSON config (nodes, edges, positions, colors) for an interactive 3D visualization of the paper's architecture. The frontend renders this with React Three Fiber.

**4. Six-Stage Reproduction Pipeline** — A separate pipeline uses Gemini to parse the paper, extract a reproducibility spec, search Papers With Code and Hugging Face for relevant resources, plan and generate notebook cells, and assemble a runnable `.ipynb` file. The result: a Colab notebook that attempts to reproduce the paper's core experiment.

**5. Section-by-Section Deep Dive** — For users who want more depth, the "Deep Dive" mode downloads the full PDF, extracts text page-by-page with PyMuPDF, uses Gemini to identify logical sections, and generates a separate Manim animation for each section. The result is a side-by-side viewer: PDF on the left, per-section animations on the right.

![Streaming progress — live updates as the pipeline fetches, generates, and renders](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-03.png)

### Google ADK (Agent Development Kit) — Structured Concept Extraction

Before generating animations, I use a **Google ADK Agent** to extract the 3–5 most important visual concepts from the paper. The ADK agent, backed by Gemini 2.5 Flash, analyzes the title and abstract and returns a structured list of concepts with suggestions for how each could be visualized. This enriched context significantly improved the quality of the animations Gemini produced downstream.

```python
concept_agent = Agent(
    name="concept_extractor",
    model=Gemini(model="gemini-2.5-flash", api_key=api_key),
    instruction="""You are an expert in scientific visualization...
    Identify the 3-5 most important concepts that should be visualized.
    For each, describe how it could be visualized in 2D or 3D.""",
)
```

This was my first time using ADK in a real project, and the agent abstraction made it clean to integrate structured AI tasks into the pipeline without managing raw prompt/response plumbing.

### Google Cloud — Production-Ready Deployment

The entire stack runs on **Google Cloud**:

- **Cloud Run** hosts both the FastAPI backend and the Next.js frontend as managed, containerized services. The backend needs enough memory and CPU to run Manim renders in subprocesses, and Cloud Run's scaling handled this well.
- **Cloud Build** orchestrates the CI/CD pipeline. A single `cloudbuild.yaml` builds both Docker images, pushes them to **Artifact Registry**, deploys the backend, retrieves its URL, then builds and deploys the frontend with the backend URL injected as an environment variable.
- **Cloud Logging** captures all runtime logs — especially useful for debugging the Manim review loop in production.

### Google OAuth + Drive + Colab — The "Open in Colab" Flow

For the reproduction notebook, I added an "Open in Colab" button that uses **Google Identity Services (OAuth 2.0)** to authenticate the user, uploads the `.ipynb` to their **Google Drive** via the Drive API, and opens it directly in **Google Colab**. One click from paper URL to runnable experiment.

## What the User Sees

Once you paste a URL and hit Visualize, the streaming overlay shows real-time progress. When it finishes, you get four things:

### Paper Summary

The title, authors, and abstract displayed cleanly so you can orient yourself.

![Paper summary — title, authors, and abstract](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-04.png)

### 2D Concept Animation (Manim)

A generated video that walks through the paper's main idea with mathematical objects, labels, and transitions — all produced by Gemini and rendered by Manim.

![Manim-generated 2D animation illustrating the paper's main idea](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-05.png)

### 3D Architecture Overview

An interactive Three.js scene where you can rotate, zoom, and explore the model's architecture as a node-and-edge graph.

![Interactive 3D scene showing the model architecture](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-06.png)

### Reproduce Experiment

A generated Colab notebook that tries to reproduce the paper's core experiment. You can download it or open it directly in Colab.

![Reproduce Experiment card with download and Open in Colab](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-07.png)

## Deep Dive Mode: Section-by-Section

For longer papers, the Deep Dive mode gives you a side-by-side experience: the original PDF on the left, and a list of detected sections on the right, each with its own generated animation.

![Deep Dive — side-by-side PDF and section list](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-08.png)

Click any section to see its dedicated animation playing alongside the corresponding PDF pages.

![Section-by-section viewer with a selected section's Manim animation](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-09.png)

## The Hardest Problem: Making Manim Actually Work

If I had to name the single biggest challenge, it was getting Gemini to produce valid Manim code. The Manim Community library has a strict API, and the model would frequently:

- Use `MathTex` (requires LaTeX, which isn't installed in the Docker container)
- Reference deprecated methods like `ShowCreation` instead of `Create`
- Pass wrong argument types to `VGroup`
- Generate coordinates that put objects off-screen

My solution was threefold:

1. **Strict prompt engineering** — explicit rules in the system prompt listing every known pitfall
2. **Error-log feedback** — the review loop sends full execution logs back to Gemini
3. **Adaptive review prompts** — when the success rate is high, I switch to an "enhanced visual review" prompt that focuses on aesthetics rather than bugs

This self-correcting pattern — generate, execute, review, revise — is one I'd use again for any code-generation task. The model gets dramatically better when it can see the consequences of its own output.

## Streaming UX: Making Long Jobs Feel Fast

Both the Manim workflow and the reproduction pipeline run in parallel and take 1–3 minutes total. Instead of a loading spinner and a prayer, I stream progress as **NDJSON** from FastAPI. The frontend consumes this with a `ReadableStream`, updating a loading overlay in real time: "Fetching paper metadata…", "Generating animation…", "Searching Papers With Code…", "Rendering MP4…"

This was a small detail that made a huge difference in how the app feels.

## The Full Stack

**Languages:** Python, TypeScript, JavaScript

**Frameworks:** FastAPI, Next.js, React

**Google Cloud:** Cloud Build, Cloud Run (managed), Artifact Registry, Container Registry, Cloud Logging

**Google APIs & AI:** Gemini API (Gemini 2.5 Flash), Google ADK (Agent Development Kit), Google Colab, Google Drive API, Google Identity Services (OAuth 2.0)

**Other:** Manim Community (animation), PyMuPDF (PDF extraction), Three.js / React Three Fiber / Drei (3D), Framer Motion, Tailwind CSS, react-pdf, arXiv API, Docker, Papers With Code API, Hugging Face

![Final result — Open in Colab flow](https://raw.githubusercontent.com/albertlieyingadrian/visual-arxiv/main/docs/visual-arxiv-10.png)

## What's Next

There's a lot I'd still like to build:

- **Caching** animations and notebooks by arXiv ID so the same paper doesn't re-render
- **Animated 3D scenes** that transition between architectural stages rather than a static graph
- **Execution verification** for reproduction notebooks — does the generated code actually run?
- **Accessibility** — captions for animations and `prefers-reduced-motion` support
- Better rate-limit handling for section-by-section mode at scale

## Try It Yourself

Visual arXiv is open source. Paste any arXiv URL, choose Quick Visualize or Deep Dive, and see what happens. If nothing else, it's a fun way to explore papers you've been meaning to read.

---

*This article was created for the purposes of entering the Gemini Live Agent Challenge hackathon. #GeminiLiveAgentChallenge*
