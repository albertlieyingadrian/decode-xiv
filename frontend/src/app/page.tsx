"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { Search, PlayCircle, Box, Download, ExternalLink, FlaskConical, Zap, Layers } from "lucide-react";
import ThreeScene from "@/components/ThreeScene";
import LoadingOverlay from "@/components/LoadingOverlay";
import { uploadNotebookAndOpenColab } from "@/lib/google-drive";

// Lazy load SideBySideMode (uses react-pdf which needs dynamic import for SSR)
const SideBySideMode = dynamic(() => import("@/components/SideBySideMode"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-64 text-neutral-500">
      Loading section viewer...
    </div>
  ),
});

const easeOutQuint = [0.23, 1, 0.32, 1] as const;

type AnalysisMode = "quick" | "deep";

export default function Home() {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string>("Connecting to server...");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reproduceColabUploading, setReproduceColabUploading] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("quick");

  /** Shared NDJSON streaming logic */
  const streamResponse = async (endpoint: string) => {
    const response = await fetch(`http://localhost:8000${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) throw new Error("Failed to process paper");
    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;
    let partialLine = "";

    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) {
        const chunk = partialLine + decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        partialLine = lines.pop() || "";
        for (const line of lines) {
          if (line.trim() === "") continue;
          try {
            const data = JSON.parse(line);
            if (data.status === "step") {
              setLoadingStep(data.message);
            } else if (data.status === "error") {
              throw new Error(data.message);
            } else if (data.status === "complete") {
              setResult(data.result);
            }
          } catch (e) {
            if (e instanceof Error && e.message !== "Failed to process paper") {
              console.error("Error parsing NDJSON line:", e);
            } else {
              throw e;
            }
          }
        }
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setIsLoading(true);
    setError(null);
    setResult(null);
    setLoadingStep("Connecting to server...");

    try {
      const endpoint = analysisMode === "deep"
        ? "/api/process-paper-sections"
        : "/api/process-paper";
      await streamResponse(endpoint);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsLoading(false);
    }
  };

  const isDeepResult = result?.sections && result?.pdf_url;

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-50 selection:bg-neutral-800 selection:text-white font-sans overflow-x-hidden flex flex-col items-center py-24 px-6">

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: easeOutQuint }}
        className="text-center max-w-3xl mb-12"
      >
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 bg-gradient-to-br from-white to-neutral-500 bg-clip-text text-transparent">
          Visualize, Reproduce, Understand
        </h1>
        <p className="text-lg text-neutral-400 leading-relaxed max-w-2xl mx-auto">
          Paste an arXiv URL below. We generate animated explanations, interactive 3D visualizations, and a runnable Colab notebook to reproduce the paper&apos;s core experiment — all in one click.
        </p>
      </motion.div>

      {/* Mode Toggle */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex items-center bg-neutral-900 rounded-full p-1 border border-neutral-800 mb-6"
      >
        <button
          onClick={() => setAnalysisMode("quick")}
          disabled={isLoading}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-colors ${
            analysisMode === "quick"
              ? "bg-white text-black"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Zap size={14} />
          Quick Visualize
        </button>
        <button
          onClick={() => setAnalysisMode("deep")}
          disabled={isLoading}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-colors ${
            analysisMode === "deep"
              ? "bg-white text-black"
              : "text-neutral-400 hover:text-white"
          }`}
        >
          <Layers size={14} />
          Deep Dive (Section-by-Section)
        </button>
      </motion.div>

      {/* Search */}
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6, delay: 0.2, ease: easeOutQuint }}
        className="w-full max-w-2xl relative mb-16"
      >
        <div className="relative group flex items-center bg-neutral-900 border border-neutral-800 rounded-full p-2 hover:border-neutral-700 transition-colors duration-300 ease-out focus-within:border-white focus-within:ring-4 focus-within:ring-white/10">
          <div className="pl-4 pr-3 text-neutral-500">
            <Search size={20} />
          </div>
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://arxiv.org/abs/..."
            className="w-full bg-transparent border-none outline-none text-white placeholder:text-neutral-600 py-3 text-lg"
            required
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !url}
            className="ml-2 bg-white text-black px-6 py-3 rounded-full font-medium hover:bg-neutral-200 transition-colors active:scale-95 disabled:opacity-50 disabled:active:scale-100 flex items-center justify-center min-w-[120px]"
            style={{ willChange: "transform" }}
          >
            {isLoading ? (
              <div className="w-5 h-5 rounded-full border-2 border-black border-t-white animate-spin" />
            ) : (
              analysisMode === "deep" ? "Deep Dive" : "Visualize"
            )}
          </button>
        </div>
      </motion.form>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="text-red-400 mb-8 max-w-2xl w-full text-center p-4 bg-red-950/30 rounded-2xl border border-red-900/50"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading */}
      <AnimatePresence>
        {isLoading && <LoadingOverlay activeStep={loadingStep} mode={analysisMode} />}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {result && !isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: easeOutQuint }}
            className="w-full"
          >
            {isDeepResult ? (
              /* ── DEEP DIVE MODE ── */
              <SideBySideMode
                title={result.title}
                authors={result.authors}
                summary={result.summary}
                pdfUrl={result.pdf_url}
                totalPages={result.total_pages}
                sections={result.sections}
              />
            ) : (
              /* ── QUICK VISUALIZE MODE ── */
              <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left Column: Info & Summary */}
                <div className="flex flex-col space-y-6">
                  <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 hover:border-neutral-700 transition-colors">
                    <h2 className="text-2xl font-bold mb-2 text-white">{result.title}</h2>
                    <p className="text-neutral-400 mb-6 text-sm">{result.authors.join(", ")}</p>
                    <div className="prose prose-invert prose-p:text-neutral-300 max-w-none">
                      <h3 className="text-lg font-semibold text-white mb-2">Abstract Summary</h3>
                      <p className="leading-relaxed whitespace-pre-line">{result.summary}</p>
                    </div>
                  </div>
                </div>

                {/* Right Column: Visualizations */}
                <div className="flex flex-col space-y-6">
                  {/* Manim Video */}
                  <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 overflow-hidden flex flex-col hover:border-neutral-700 transition-colors group">
                    <div className="flex items-center space-x-2 mb-4">
                      <PlayCircle className="text-neutral-400 group-hover:text-white transition-colors" />
                      <h3 className="text-lg font-semibold">2D Concept Animation (Manim)</h3>
                    </div>
                    <div className="aspect-video bg-black rounded-xl overflow-hidden relative border border-neutral-800 flex items-center justify-center">
                      {result.manim_video_url && result.manim_video_url.length > 5 ? (
                        <video
                          controls
                          className="w-full h-full object-cover"
                          src={result.manim_video_url.startsWith("http") ? result.manim_video_url : `http://localhost:8000${result.manim_video_url}`}
                        >
                          Your browser does not support the video tag.
                        </video>
                      ) : (
                        <div className="text-neutral-500 flex flex-col items-center">
                          <p>Video processing failed or not available.</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 3D Scene */}
                  <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 overflow-hidden flex flex-col hover:border-neutral-700 transition-colors group">
                    <div className="flex items-center space-x-2 mb-4">
                      <Box className="text-neutral-400 group-hover:text-white transition-colors" />
                      <h3 className="text-lg font-semibold">3D Architecture Overview</h3>
                    </div>
                    <div className="aspect-video bg-black rounded-xl border border-neutral-800 flex flex-col items-center justify-center overflow-hidden">
                      <ThreeScene configStr={result.three_js_config} />
                    </div>
                  </div>
                </div>

                {/* Reproduce Experiment */}
                <div className="lg:col-span-2">
                  <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 hover:border-neutral-700 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <FlaskConical className={result.reproduce_notebook_url ? "text-emerald-400" : "text-neutral-500"} size={24} />
                        <div>
                          <h3 className="text-lg font-semibold text-white">Reproduce Experiment</h3>
                          <p className="text-neutral-400 text-sm">
                            {result.reproduce_notebook_url
                              ? "A runnable Colab notebook that reproduces the paper\u2019s core experiment"
                              : "Notebook generation failed \u2014 this may be due to API rate limits. Try again later."}
                          </p>
                        </div>
                      </div>
                      {result.reproduce_notebook_url && (
                        <div className="flex items-center gap-3">
                          <button
                            onClick={async () => {
                              const nbUrl = result.reproduce_notebook_url.startsWith("http")
                                ? result.reproduce_notebook_url
                                : `http://localhost:8000${result.reproduce_notebook_url}`;
                              const res = await fetch(nbUrl);
                              const blob = await res.blob();
                              const blobUrl = URL.createObjectURL(blob);
                              const a = document.createElement("a");
                              a.href = blobUrl;
                              a.download = `experiment_${result?.title?.replace(/[^a-zA-Z0-9 ]/g, "").replace(/\s+/g, "_").slice(0, 50) || "paper"}.ipynb`;
                              a.click();
                              URL.revokeObjectURL(blobUrl);
                            }}
                            className="flex items-center gap-2 bg-neutral-800 text-neutral-200 px-4 py-2 rounded-full text-sm font-medium hover:bg-neutral-700 transition-colors border border-neutral-700"
                          >
                            <Download size={16} />
                            Download Notebook
                          </button>
                          <button
                            disabled={reproduceColabUploading}
                            onClick={async () => {
                              const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
                              if (!clientId) {
                                alert("Google OAuth Client ID not configured.");
                                return;
                              }
                              setReproduceColabUploading(true);
                              try {
                                const nbUrl = result.reproduce_notebook_url.startsWith("http")
                                  ? result.reproduce_notebook_url
                                  : `http://localhost:8000${result.reproduce_notebook_url}`;
                                await uploadNotebookAndOpenColab(
                                  nbUrl,
                                  `experiment_${result?.title?.replace(/[^a-zA-Z0-9 ]/g, "").replace(/\s+/g, "_").slice(0, 50) || "paper"}.ipynb`,
                                  clientId
                                );
                              } catch (err) {
                                alert(err instanceof Error ? err.message : "Failed to open in Colab");
                              } finally {
                                setReproduceColabUploading(false);
                              }
                            }}
                            className="flex items-center gap-2 bg-[#F9AB00] text-black px-4 py-2 rounded-full text-sm font-medium hover:bg-[#e09e00] transition-colors disabled:opacity-60"
                          >
                            {reproduceColabUploading ? (
                              <>
                                <div className="w-4 h-4 rounded-full border-2 border-black border-t-transparent animate-spin" />
                                Uploading...
                              </>
                            ) : (
                              <>
                                <ExternalLink size={16} />
                                Open in Colab
                              </>
                            )}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

    </main>
  );
}
