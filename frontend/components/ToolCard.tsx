"use client";

import { useState } from "react";

interface ToolCardProps {
  tool: string;
  status: "running" | "done";
  output?: string;
  index: number;
}

const TOOL_ICONS: Record<string, string> = {
  web_search: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
  web_fetch: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
  get_current_time: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  get_news: "M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z",
  get_weather: "M12 3v2m0 14v2M5.6 5.6l1.4 1.4m10.4 10.4l1.4 1.4M3 12h2m14 0h2M5.6 18.4l1.4-1.4m10.4-10.4l1.4-1.4M12 7a5 5 0 115 5 4 4 0 00-4-4z",
  execute: "M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
};

const TOOL_LABELS: Record<string, string> = {
  web_search: "Tìm kiếm web",
  web_fetch: "Lấy nội dung web",
  get_current_time: "Xem giờ",
  get_news: "Tin tức",
  get_weather: "Thời tiết",
  execute: "Thực thi lệnh",
};

function getToolDisplay(tool: string) {
  const iconPath = TOOL_ICONS[tool] || "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z";
  const label = TOOL_LABELS[tool] || tool;
  return { iconPath, label };
}

export default function ToolCard({ tool, status, output, index }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { iconPath, label } = getToolDisplay(tool);
  const isRunning = status === "running";

  return (
    <div
      className={`rounded-lg border transition-all duration-200 ${
        isRunning
          ? "border-accent/30 bg-accent-light/50"
          : "border-border bg-surface hover:border-border-strong"
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-center gap-2.5 px-3 py-2.5">
        {/* Icon */}
        <span className="flex-shrink-0 w-7 h-7 rounded-md bg-surface-alt flex items-center justify-center">
          {isRunning ? (
            <svg
              className="w-3.5 h-3.5 text-accent animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83" strokeLinecap="round" />
            </svg>
          ) : (
            <svg
              className="w-3.5 h-3.5 text-success"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </span>

        {/* Tool icon */}
        <svg className="w-4 h-4 text-text-secondary flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d={iconPath} strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Label */}
        <span className="text-sm font-medium text-text-primary">{label}</span>

        {/* Expand button (only when output exists) */}
        {output && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary transition-colors"
          >
            <span className="hidden sm:inline">{expanded ? "Thu gọn" : "Chi tiết"}</span>
            <svg
              className={`w-3.5 h-3.5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        )}
      </div>

      {/* Output */}
      {expanded && output && (
        <div className="px-3 pb-3">
          <pre className="text-xs font-mono text-text-secondary bg-surface-alt rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-words leading-relaxed">
            {output}
          </pre>
        </div>
      )}
    </div>
  );
}
