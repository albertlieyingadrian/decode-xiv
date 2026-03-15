"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

type Section = {
  id: string;
  title: string;
  page_start: number;
  page_end: number;
};

type Props = {
  pdfUrl: string;
  totalPages: number;
  sections: Section[];
  activeSection: string;
  /** Called when a timeline click needs to scroll PDF to a section */
  scrollToSection: string | null;
  onScrollToSectionDone: () => void;
  onPageChange: (page: number) => void;
  onSectionFromScroll: (sectionId: string) => void;
};

export default function PaperViewer({
  pdfUrl,
  totalPages,
  sections,
  activeSection,
  scrollToSection,
  onScrollToSectionDone,
  onPageChange,
  onSectionFromScroll,
}: Props) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageWidth, setPageWidth] = useState(600);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const suppressObserver = useRef(false);

  // Responsive page width
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setPageWidth(containerRef.current.clientWidth - 32);
      }
    };
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  const onDocumentLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n);
  }, []);

  // Scroll observation → detect which page/section is visible
  useEffect(() => {
    const container = containerRef.current;
    if (!container || numPages === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Skip if we're doing a programmatic scroll
        if (suppressObserver.current) return;

        let maxRatio = 0;
        let visiblePage = 1;
        for (const entry of entries) {
          if (entry.intersectionRatio > maxRatio) {
            maxRatio = entry.intersectionRatio;
            const pageNum = Number(entry.target.getAttribute("data-page"));
            if (pageNum) visiblePage = pageNum;
          }
        }

        if (maxRatio > 0) {
          onPageChange(visiblePage);
          for (const section of sections) {
            if (visiblePage >= section.page_start && visiblePage <= section.page_end) {
              onSectionFromScroll(section.id);
              break;
            }
          }
        }
      },
      {
        root: container,
        threshold: [0, 0.25, 0.5, 0.75, 1],
      }
    );

    pageRefs.current.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [numPages, sections, onPageChange, onSectionFromScroll]);

  // Programmatic scroll: only triggered by explicit scrollToSection prop (from click)
  useEffect(() => {
    if (!scrollToSection) return;

    const section = sections.find((s) => s.id === scrollToSection);
    if (!section) return;

    const el = pageRefs.current.get(section.page_start);
    if (el) {
      suppressObserver.current = true;
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      // Re-enable observer after scroll completes
      setTimeout(() => {
        suppressObserver.current = false;
        onScrollToSectionDone();
      }, 1000);
    } else {
      onScrollToSectionDone();
    }
  }, [scrollToSection, sections, onScrollToSectionDone]);

  const activeSectionData = sections.find((s) => s.id === activeSection);

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto overflow-x-hidden bg-neutral-950 rounded-xl border border-neutral-800"
    >
      <Document
        file={pdfUrl}
        onLoadSuccess={onDocumentLoadSuccess}
        loading={
          <div className="flex items-center justify-center h-64 text-neutral-500">
            Loading PDF...
          </div>
        }
        error={
          <div className="flex items-center justify-center h-64 text-red-400">
            Failed to load PDF
          </div>
        }
      >
        {Array.from({ length: numPages || totalPages }, (_, i) => {
          const pageNum = i + 1;
          const isHighlighted =
            activeSectionData &&
            pageNum >= activeSectionData.page_start &&
            pageNum <= activeSectionData.page_end;

          return (
            <div
              key={pageNum}
              data-page={pageNum}
              ref={(el) => {
                if (el) pageRefs.current.set(pageNum, el);
              }}
              className={`relative mx-auto my-2 transition-all duration-300 ${
                isHighlighted ? "ring-2 ring-white/30 rounded-lg" : ""
              }`}
            >
              <Page
                pageNumber={pageNum}
                width={pageWidth}
                renderTextLayer={true}
                renderAnnotationLayer={true}
              />
              <div className="absolute bottom-2 right-3 bg-black/70 text-neutral-400 text-xs px-2 py-0.5 rounded">
                {pageNum}
              </div>
            </div>
          );
        })}
      </Document>
    </div>
  );
}
