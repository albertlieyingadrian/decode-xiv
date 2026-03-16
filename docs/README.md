# Visual arXiv — Screenshots

Captions for the application screenshots, in order of the typical user flow.


| #   | Image           | Caption                                                                                                                                           |
| --- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | visual-arxiv-01 | **Home** — Mode toggle (Quick Visualize vs Deep Dive) and arXiv URL input.                                                                        |
| 2   | visual-arxiv-02 | **URL submitted** — User has entered an arXiv URL and chosen a mode; ready to visualize.                                                          |
| 3   | visual-arxiv-03 | **Streaming progress** — Loading overlay showing live NDJSON progress (e.g. fetching paper, generating animation, running reproduction pipeline). |
| 4   | visual-arxiv-04 | **Paper summary** — Quick Visualize result: paper title, authors, and abstract.                                                                   |
| 5   | visual-arxiv-05 | **Concept animation** — Manim-generated 2D video illustrating the paper’s main idea from title and abstract.                                      |
| 6   | visual-arxiv-06 | **3D architecture view** — Interactive Three.js scene (nodes/edges) for the model or concepts in the paper.                                       |
| 7   | visual-arxiv-07 | **Reproduce experiment** — Card with download notebook and “Open in Colab” (via Google Drive).                                                    |
| 8   | visual-arxiv-08 | **Deep Dive mode** — Side-by-side view: PDF on one side, section list with per-section videos on the other.                                       |
| 9   | visual-arxiv-09 | **Section-by-section viewer** — PDF and section list with a selected section’s Manim animation playing.                                           |
| 10  | visual-arxiv-10 | **Colab / result** — “Open in Colab” flow or final result view (e.g. notebook opened in Colab).                                                   |



---

## Automated deployment

Deployment is fully automated using infrastructure-as-code and a single entry script:

- **[cloudbuild.yaml](../cloudbuild.yaml)** — Cloud Build pipeline: build and push backend/frontend Docker images to Artifact Registry, deploy both services to Cloud Run (backend first, then frontend built with the backend URL), with logging set to `CLOUD_LOGGING_ONLY`.
- **[deploy_gcp.sh](../deploy_gcp.sh)** — Bash script that enables required GCP APIs (`cloudbuild`, `run`, `artifactregistry`, `containerregistry`), creates the Artifact Registry repository if needed, loads `GEMINI_API_KEY` and `OPENROUTER_API_KEY` from `backend/.env`, and runs `gcloud builds submit --config cloudbuild.yaml` with substitutions. One command deploys the full stack.
