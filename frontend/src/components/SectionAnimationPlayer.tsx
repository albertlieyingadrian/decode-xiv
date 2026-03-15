"use client";

import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PlayCircle } from "lucide-react";

type Section = {
  id: string;
  title: string;
  text: string;
  video_url: string;
  page_start: number;
  page_end: number;
};

type Props = {
  section: Section | null;
  allSections: Section[];
};

export default function SectionAnimationPlayer({ section, allSections }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);

  // Preload next section video
  useEffect(() => {
    if (!section) return;
    const idx = allSections.findIndex((s) => s.id === section.id);
    const next = allSections[idx + 1];
    if (next?.video_url) {
      const link = document.createElement("link");
      link.rel = "prefetch";
      link.href = next.video_url;
      link.as = "video";
      document.head.appendChild(link);
      return () => { document.head.removeChild(link); };
    }
  }, [section, allSections]);

  // Auto-play when section changes
  useEffect(() => {
    if (videoRef.current && section?.video_url) {
      videoRef.current.load();
      videoRef.current.play().catch(() => {});
    }
  }, [section?.id, section?.video_url]);

  if (!section) {
    return (
      <div className="aspect-video bg-black rounded-xl border border-neutral-800 flex items-center justify-center text-neutral-500">
        <p>Select a section to view its animation</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <PlayCircle size={20} className="text-neutral-400" />
        <h3 className="text-lg font-semibold text-white">{section.title}</h3>
      </div>

      {/* Video player with crossfade */}
      <div className="aspect-video bg-black rounded-xl overflow-hidden border border-neutral-800 relative">
        <AnimatePresence mode="wait">
          {section.video_url ? (
            <motion.video
              key={section.id}
              ref={videoRef}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              controls
              className="w-full h-full object-contain absolute inset-0"
              src={section.video_url}
            />
          ) : (
            <motion.div
              key={`${section.id}-fallback`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="w-full h-full flex flex-col items-center justify-center text-neutral-500 absolute inset-0"
            >
              <p className="text-sm">Animation not available for this section</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Section summary */}
      <p className="text-sm text-neutral-400 leading-relaxed">{section.text}</p>
    </div>
  );
}
