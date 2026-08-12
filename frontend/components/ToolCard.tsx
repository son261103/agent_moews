"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ToolCardProps {
  tool: string;
  status: "running" | "done";
  input?: any;
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
  researcher: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
};

const TOOL_LABELS: Record<string, string> = {
  web_search: "Tìm kiếm web",
  web_fetch: "Đọc nội dung web",
  get_current_time: "Xem giờ",
  get_news: "Tin tức",
  get_weather: "Thời tiết",
  execute: "Thực thi lệnh",
  researcher: "Nghiên cứu & tổng hợp",
};

function getToolDisplay(tool: string) {
  const iconPath =
    TOOL_ICONS[tool] ||
    "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z";
  const label = TOOL_LABELS[tool] || tool;
  return { iconPath, label };
}

function formatSize(text: string): string {
  const bytes = new Blob([text]).size;
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function formatInputPreview(input: any): string {
  if (!input) return "";
  if (typeof input === "string") return input;
  if (typeof input === "object") {
    if (input.query) return `query: "${input.query}"`;
    if (input.url) return `url: "${input.url}"`;
    if (input.city) return `city: "${input.city}"`;
    if (input.category) return `category: "${input.category}"`;
    const keys = Object.keys(input);
    if (keys.length === 1) return `${keys[0]}: "${input[keys[0]]}"`;
    return JSON.stringify(input);
  }
  return String(input);
}

function tryParseJSON(str: string): any {
  try {
    return JSON.parse(str);
  } catch {
    try {
      const fixed = str
        .replace(/'/g, '"')
        .replace(/True/g, "true")
        .replace(/False/g, "false")
        .replace(/None/g, "null");
      return JSON.parse(fixed);
    } catch {
      return null;
    }
  }
}

export default function ToolCard({ tool, status, input, output, index }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [viewRaw, setViewRaw] = useState(false);

  const { iconPath, label } = getToolDisplay(tool);
  const isRunning = status === "running";
  const inputPreview = formatInputPreview(input);

  const parsedJSON = output ? tryParseJSON(output) : null;
  const isArrayResults = Array.isArray(parsedJSON) && parsedJSON.length > 0;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!output) return;
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={`rounded-xl border transition-all duration-200 overflow-hidden ${
        isRunning
          ? "border-accent/40 bg-accent-light/30 shadow-xs"
          : "border-border bg-surface hover:border-border-strong"
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Header Bar */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5">
        {/* Status Indicator */}
        <span className="flex-shrink-0 w-6 h-6 rounded-md bg-surface-alt flex items-center justify-center">
          {isRunning ? (
            <svg
              className="w-3.5 h-3.5 text-accent animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
            >
              <path
                d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.48-8.48l2.83-2.83M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83"
                strokeLinecap="round"
              />
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

        {/* Tool SVG Icon */}
        <svg
          className="w-4 h-4 text-text-secondary flex-shrink-0"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d={iconPath} strokeLinecap="round" strokeLinejoin="round" />
        </svg>

        {/* Tool Name / Label */}
        <span className="text-sm font-medium text-text-primary">{label}</span>

        {/* Input Parameter Preview Badge */}
        {inputPreview && (
          <span className="text-[11px] font-mono text-text-tertiary truncate max-w-[180px] sm:max-w-[320px] bg-surface-alt/80 px-2 py-0.5 rounded border border-border/50">
            {inputPreview}
          </span>
        )}

        {/* Status badge */}
        <span
          className={`text-[11px] font-mono px-2 py-0.5 rounded-md ${
            isRunning
              ? "bg-accent/10 text-accent font-medium"
              : "bg-surface-alt text-text-tertiary"
          }`}
        >
          {isRunning ? "Đang xử lý..." : "Hoàn tất"}
        </span>

        {/* Size Badge if output exists */}
        {output && (
          <span className="text-[11px] text-text-tertiary font-mono hidden sm:inline">
            {formatSize(output)}
          </span>
        )}

        {/* Action Controls */}
        <div className="ml-auto flex items-center gap-2">
          {(output || input) && (
            <>
              {/* Copy Button */}
              {output && (
                <button
                  onClick={handleCopy}
                  title="Sao chép kết quả"
                  className="text-xs text-text-tertiary hover:text-text-secondary transition-colors px-1.5 py-1 rounded hover:bg-surface-alt flex items-center gap-1"
                >
                  {copied ? (
                    <>
                      <svg className="w-3.5 h-3.5 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span className="text-success font-medium text-[11px]">Đã sao chép</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5 text-text-tertiary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      <span className="hidden md:inline text-[11px]">Sao chép</span>
                    </>
                  )}
                </button>
              )}

              {/* Expand/Collapse Toggle */}
              <button
                onClick={() => setExpanded((v) => !v)}
                className="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors px-2 py-1 rounded hover:bg-surface-alt font-medium"
              >
                <span>{expanded ? "Thu gọn" : "Chi tiết"}</span>
                <svg
                  className={`w-3.5 h-3.5 transition-transform duration-200 ${
                    expanded ? "rotate-180" : ""
                  }`}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Expanded Detail Area: Input Parameters + Output Content */}
      {expanded && (
        <div className="border-t border-border/60 bg-surface-alt/40 p-3 text-xs leading-relaxed space-y-3">
          {/* Section 1: Input Parameters */}
          {input && (
            <div className="space-y-1">
              <div className="text-[11px] font-mono font-semibold text-text-tertiary uppercase tracking-wider">
                Tham số đầu vào (Input)
              </div>
              <pre className="font-mono text-xs text-text-primary bg-surface p-2.5 rounded-lg border border-border/60 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {typeof input === "object" ? JSON.stringify(input, null, 2) : String(input)}
              </pre>
            </div>
          )}

          {/* Section 2: Output Content */}
          {output && (
            <div className="space-y-1">
              <div className="flex items-center justify-between pb-1 border-b border-border/30">
                <span className="text-[11px] font-mono font-semibold text-text-tertiary uppercase tracking-wider">
                  Kết quả trả về (Output)
                </span>
                {parsedJSON && (
                  <button
                    onClick={() => setViewRaw((v) => !v)}
                    className="text-[11px] font-mono text-accent hover:underline"
                  >
                    {viewRaw ? "Xem định dạng đẹp" : "Xem thô (Raw)"}
                  </button>
                )}
              </div>

              <div className="max-h-96 overflow-y-auto pr-1">
                {isArrayResults && !viewRaw ? (
                  <div className="space-y-2">
                    {parsedJSON.map((item: any, idx: number) => {
                      const title = item.title || item.name || `Mục ${idx + 1}`;
                      const url = item.url || item.link;
                      const content = item.content || item.snippet || item.body || JSON.stringify(item);

                      return (
                        <div
                          key={idx}
                          className="p-2.5 rounded-lg border border-border/80 bg-surface text-text-primary space-y-1"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="font-semibold text-sm text-text-primary leading-tight">
                              {title}
                            </span>
                            {url && (
                              <a
                                href={url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-accent underline text-xs flex-shrink-0 hover:text-accent-hover"
                              >
                                Mở link ↗
                              </a>
                            )}
                          </div>
                          <p className="text-text-secondary leading-relaxed whitespace-pre-wrap text-xs">
                            {content}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : parsedJSON && !viewRaw ? (
                  <pre className="font-mono text-xs text-text-primary bg-surface p-3 rounded-lg border border-border/60 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                    {JSON.stringify(parsedJSON, null, 2)}
                  </pre>
                ) : (
                  <div className="bg-surface p-3 rounded-lg border border-border/60 text-text-primary leading-relaxed whitespace-pre-wrap font-mono text-xs overflow-x-auto">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ children, ...props }) => (
                          <a
                            {...props}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-accent underline hover:text-accent-hover"
                          >
                            {children}
                          </a>
                        ),
                      }}
                    >
                      {output}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

