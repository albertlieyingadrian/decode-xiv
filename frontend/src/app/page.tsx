"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, PlayCircle, Box } from "lucide-react";
import ThreeScene from "@/components/ThreeScene";
import LoadingOverlay from "@/components/LoadingOverlay";

// Emil Kowalski easing curves
const easeOutQuint = [0.23, 1, 0.32, 1] as const;

export default function Home() {
  const [url, setUrl] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string>("Connecting to server...");
  const [result, setResult] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setIsLoading(true);
    setError(null);
    setResult(null);
    setLoadingStep("Connecting to server...");

    try {
      const response = await fetch("http://localhost:8000/api/process-paper", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error("Failed to process paper");
      }

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
          // Last element might be incomplete
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
              console.error("Error parsing NDJSON line:", e);
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An error occurred");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-50 selection:bg-neutral-800 selection:text-white font-sans overflow-x-hidden flex flex-col items-center py-24 px-6">
      
      {/* Header / Hero Section */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: easeOutQuint }}
        className="text-center max-w-3xl mb-12"
      >
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-6 bg-gradient-to-br from-white to-neutral-500 bg-clip-text text-transparent">
          Unpack Research with Animation
        </h1>
        <p className="text-lg text-neutral-400 leading-relaxed max-w-2xl mx-auto">
          Paste an arXiv URL below. We use AI to extract the core concepts and automatically generate beautiful 2D Manim videos and interactive 3D visualizations.
        </p>
      </motion.div>

      {/* Search Input Area */}
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
              "Visualize"
            )}
          </button>
        </div>
      </motion.form>

      {/* Error State */}
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

      {/* Loading State */}
      <AnimatePresence>
        {isLoading && (
            <LoadingOverlay activeStep={loadingStep} />
        )}
      </AnimatePresence>

      {/* Results State */}
      <AnimatePresence>
        {result && !isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: easeOutQuint }}
            className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-8"
          >
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
              
              {/* Manim Video Result */}
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
                        src={result.manim_video_url.startsWith('http') ? result.manim_video_url : `http://localhost:8000${result.manim_video_url}`}
                      >
                         Your browser does not support the video tag.
                      </video>
                   ) : (
                      <div className="text-neutral-500 flex flex-col items-center">
                         <p>Video processing failed or not available in MVP.</p>
                      </div>
                   )}
                </div>
              </div>

               {/* Three.js Fallback/Placeholder (We'd embed canvas here normally) */}
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
          </motion.div>
        )}
      </AnimatePresence>

    </main>
  );
}
