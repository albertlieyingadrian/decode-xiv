"use client";

import { useState, useCallback } from "react";
import SectionTimeline from "./SectionTimeline";
import SectionAnimationPlayer from "./SectionAnimationPlayer";
import PaperViewer from "./PaperViewer";
import { FileText, Play, Columns } from "lucide-react";

type Section = {
  id: string;
  title: string;
  text: string;
  video_url: string;
  page_start: number;
  page_end: number;
};

type Props = {
  title: string;
  authors: string[];
  summary: string;
  pdfUrl: string;
  totalPages: number;
  sections: Section[];
};

type ViewMode = "sections" | "sidebyside";

export default function SideBySideMode({
  title,
  authors,
  summary,
  pdfUrl,
  totalPages,
  sections,
}: Props) {
  const [activeSection, setActiveSection] = useState(sections[0]?.id || "");
  const [currentPage, setCurrentPage] = useState(1);
  const [viewMode, setViewMode] = useState<ViewMode>("sections");
  // scrollToSection is set ONLY by explicit user clicks (timeline/pills),
  // cleared after PaperViewer finishes scrolling — prevents the feedback loop.
  const [scrollToSection, setScrollToSection] = useState<string | null>(null);

  const currentSectionData = sections.find((s) => s.id === activeSection) || null;

  // User explicitly clicked a section (timeline or pill) → update active + trigger scroll
  const handleSectionClick = useCallback((id: string) => {
    setActiveSection(id);
    setScrollToSection(id);
  }, []);

  // Scroll observer detected a new section → just update active, do NOT scroll
  const handleSectionFromScroll = useCallback((sectionId: string) => {
    setActiveSection(sectionId);
  }, []);

  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  const handleScrollToSectionDone = useCallback(() => {
    setScrollToSection(null);
  }, []);

  return (
    <div className="w-full max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white mb-1">{title}</h2>
          <p className="text-neutral-400 text-sm">{authors.join(", ")}</p>
        </div>

        {/* View mode toggle */}
        <div className="flex-shrink-0 flex items-center bg-neutral-900 rounded-full p-1 border border-neutral-800">
          <button
            onClick={() => setViewMode("sections")}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              viewMode === "sections"
                ? "bg-white text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            <Play size={14} />
            Sections
          </button>
          <button
            onClick={() => setViewMode("sidebyside")}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors ${
              viewMode === "sidebyside"
                ? "bg-white text-black"
                : "text-neutral-400 hover:text-white"
            }`}
          >
            <Columns size={14} />
            Paper Mode
          </button>
        </div>
      </div>

      {viewMode === "sections" ? (
        /* SECTIONS MODE: Timeline + Animation Player */
        <div className="flex gap-6" style={{ height: "calc(100vh - 220px)" }}>
          {/* Left sidebar: timeline */}
          <div className="w-64 flex-shrink-0 overflow-y-auto pr-2">
            <SectionTimeline
              sections={sections}
              currentSection={activeSection}
              onSelect={handleSectionClick}
            />
          </div>

          {/* Main content: animation player */}
          <div className="flex-1 overflow-y-auto">
            <SectionAnimationPlayer
              section={currentSectionData}
              allSections={sections}
            />
          </div>
        </div>
      ) : (
        /* SIDE-BY-SIDE MODE: PDF + Animation */
        <div className="flex gap-4" style={{ height: "calc(100vh - 220px)" }}>
          {/* Left: PDF Viewer */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-3">
              <FileText size={16} className="text-neutral-400" />
              <span className="text-sm font-medium text-neutral-300">
                Paper — Page {currentPage}
              </span>
            </div>
            <div style={{ height: "calc(100% - 32px)" }}>
              <PaperViewer
                pdfUrl={pdfUrl}
                totalPages={totalPages}
                sections={sections}
                activeSection={activeSection}
                scrollToSection={scrollToSection}
                onScrollToSectionDone={handleScrollToSectionDone}
                onPageChange={handlePageChange}
                onSectionFromScroll={handleSectionFromScroll}
              />
            </div>
          </div>

          {/* Right: Animation + Section nav */}
          <div className="w-[480px] flex-shrink-0 flex flex-col gap-4 overflow-y-auto">
            {/* Compact section pills */}
            <div className="flex flex-wrap gap-2">
              {sections.map((s) => (
                <button
                  key={s.id}
                  onClick={() => handleSectionClick(s.id)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                    s.id === activeSection
                      ? "bg-white text-black"
                      : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-white"
                  }`}
                >
                  {s.title}
                </button>
              ))}
            </div>

            {/* Animation player */}
            <SectionAnimationPlayer
              section={currentSectionData}
              allSections={sections}
            />
          </div>
        </div>
      )}
    </div>
  );
}
