"use client";

import { useState } from "react";

interface ThinkingBlockProps {
  isRunning: boolean;
  content: string;
}

export default function ThinkingBlock({ isRunning, content }: ThinkingBlockProps) {
  const [userToggled, setUserToggled] = useState(false);

  // Don't render if no reflection has occurred
  if (!isRunning && !content) return null;

  // When running, always expanded. When done, respect user toggle (default collapsed).
  const expanded = isRunning || userToggled;

  const handleToggle = () => {
    if (isRunning) return; // Don't allow collapse while running
    setUserToggled((v) => !v);
  };

  return (
    <div className="rounded-lg border border-border bg-thinking-bg overflow-hidden transition-all duration-200">
      <button
        onClick={handleToggle}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-sm hover:bg-surface-alt/60 transition-colors"
      >
        {/* Icon */}
        <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
          {isRunning ? (
            <svg
              className="w-4 h-4 text-accent animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83" strokeLinecap="round" />
            </svg>
          ) : (
            <svg
              className="w-4 h-4 text-success"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="12" cy="12" r="10" />
            </svg>
          )}
        </span>

        {/* Label */}
        <span className={`flex-1 text-left font-medium ${isRunning ? "thinking-shimmer" : "text-text-secondary"}`}>
          {isRunning ? "Đang suy nghĩ..." : "Đã kiểm tra"}
        </span>

        {/* Content preview when collapsed */}
        {!isRunning && !expanded && content && (
          <span className="text-xs text-text-tertiary truncate max-w-[200px] hidden sm:inline">
            {content.length > 60 ? content.slice(0, 60) + "..." : content}
          </span>
        )}

        {/* Chevron */}
        <svg
          className={`w-4 h-4 text-text-tertiary transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Collapsible content */}
      {expanded && content && (
        <div className="px-3 pb-3 pt-1 text-sm text-text-secondary leading-relaxed border-t border-border/50">
          {content}
        </div>
      )}

      {/* Running indicator bar */}
      {isRunning && (
        <div className="h-0.5 w-full overflow-hidden">
          <div className="h-full bg-accent/30 animate-pulse" />
        </div>
      )}
    </div>
  );
}
