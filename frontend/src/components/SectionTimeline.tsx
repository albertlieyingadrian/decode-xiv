"use client";

import { motion } from "framer-motion";

type Section = {
  id: string;
  title: string;
  text: string;
  video_url: string;
  page_start: number;
  page_end: number;
};

type Props = {
  sections: Section[];
  currentSection: string;
  onSelect: (id: string) => void;
};

const SECTION_ICONS: Record<string, string> = {
  introduction: "01",
  related_work: "02",
  method: "03",
  architecture: "04",
  experiments: "05",
  results: "06",
  conclusion: "07",
};

export default function SectionTimeline({ sections, currentSection, onSelect }: Props) {
  return (
    <nav className="flex flex-col gap-1 w-full">
      {sections.map((section, i) => {
        const isActive = section.id === currentSection;
        const hasVideo = !!section.video_url;
        const number = SECTION_ICONS[section.id] || String(i + 1).padStart(2, "0");

        return (
          <button
            key={section.id}
            onClick={() => onSelect(section.id)}
            className={`relative flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200 group
              ${isActive
                ? "bg-white/10 border border-white/20"
                : "hover:bg-white/5 border border-transparent"
              }`}
          >
            {/* Number badge */}
            <span
              className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold transition-colors
                ${isActive ? "bg-white text-black" : "bg-neutral-800 text-neutral-400 group-hover:bg-neutral-700"}`}
            >
              {number}
            </span>

            {/* Section info */}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium truncate transition-colors ${isActive ? "text-white" : "text-neutral-300"}`}>
                {section.title}
              </p>
              <p className="text-xs text-neutral-500 truncate">
                Pages {section.page_start}–{section.page_end}
              </p>
            </div>

            {/* Video status dot */}
            <span
              className={`flex-shrink-0 w-2 h-2 rounded-full ${hasVideo ? "bg-emerald-400" : "bg-neutral-600"}`}
              title={hasVideo ? "Animation ready" : "No animation"}
            />

            {/* Active indicator bar */}
            {isActive && (
              <motion.div
                layoutId="section-indicator"
                className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-white rounded-full"
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
          </button>
        );
      })}
    </nav>
  );
}
