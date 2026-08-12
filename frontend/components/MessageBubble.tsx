"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ToolCard from "./ToolCard";
import ThinkingBlock from "./ThinkingBlock";

export interface ToolCall {
  id: string;
  tool: string;
  status: "running" | "done";
  input?: any;
  output?: string;
}

export interface ThinkingState {
  isRunning: boolean;
  content: string;
}

interface MessageBubbleProps {
  content: string;
  isUser: boolean;
  isStreaming?: boolean;
  toolCalls?: ToolCall[];
  thinking?: ThinkingState;
}

export default function MessageBubble({
  content,
  isUser,
  isStreaming = false,
  toolCalls = [],
  thinking,
}: MessageBubbleProps) {
  // 1. User Message Bubble
  if (isUser) {
    return (
      <div className="flex justify-end my-1">
        <div className="max-w-[80%] sm:max-w-[70%] rounded-2xl rounded-tr-sm bg-accent text-white px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-xs">
          {content}
        </div>
      </div>
    );
  }

  // 2. Error Message Callout Alert Box
  const isError = content.startsWith("Lỗi:") || content.startsWith("Error:");
  if (isError) {
    return (
      <div className="flex justify-start gap-3 my-2">
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 flex items-center justify-center text-red-600 mt-0.5">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4m0 4h.01" strokeLinecap="round" />
          </svg>
        </div>
        <div className="max-w-[85%] rounded-xl border border-red-200 bg-red-50/80 p-3.5 text-xs text-red-800 font-mono leading-relaxed space-y-1">
          <div className="font-semibold text-red-900 flex items-center gap-1.5 text-sm font-sans">
            <span>Đã xảy ra lỗi</span>
          </div>
          <div className="whitespace-pre-wrap break-words">{content}</div>
        </div>
      </div>
    );
  }

  const hasTools = toolCalls && toolCalls.length > 0;
  const hasThinking = thinking && (thinking.isRunning || thinking.content);
  const hasContent = Boolean(content) || isStreaming;

  // 3. Assistant Message Turn
  return (
    <div className="flex justify-start gap-3 py-2">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-panel text-text-on-dark flex items-center justify-center mt-0.5 shadow-xs">
        <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* Content Turn Column */}
      <div className="flex-1 min-w-0 max-w-[88%] space-y-2.5">
        {/* Step 1: Tool Calls Executed in this Turn */}
        {hasTools && (
          <div className="space-y-2">
            {toolCalls.map((tc, i) => (
              <ToolCard
                key={tc.id}
                tool={tc.tool}
                status={tc.status}
                input={tc.input}
                output={tc.output}
                index={i}
              />
            ))}
          </div>
        )}

        {/* Step 2: Reflection / Thinking Block */}
        {hasThinking && (
          <ThinkingBlock
            isRunning={thinking.isRunning}
            content={thinking.content}
          />
        )}

        {/* Step 3: Streamed & Final Text Response */}
        {hasContent && (
          <div className={`text-sm leading-relaxed text-text-primary ${isStreaming ? "streaming-cursor" : ""}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                pre: ({ children }) => (
                  <div className="my-3.5 rounded-xl overflow-hidden border border-border shadow-xs">
                    <div className="flex items-center justify-between bg-[#21252B] px-4 py-2 text-xs text-[#abb2bf] font-mono select-none">
                      <span className="flex items-center gap-1.5 font-semibold">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block" />
                        <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/80 inline-block" />
                        <span className="w-2.5 h-2.5 rounded-full bg-green-500/80 inline-block" />
                        <span className="ml-2 text-[#5c6370]">Code</span>
                      </span>
                    </div>
                    <pre className="overflow-x-auto bg-[#1e2227] p-4 text-[#abb2bf] text-xs leading-relaxed font-mono">
                      {children}
                    </pre>
                  </div>
                ),
                code: ({ children, className }) => {
                  const isBlock = className?.includes("language-");
                  if (isBlock) {
                    return <code className={className}>{children}</code>;
                  }
                  return (
                    <code className="rounded-md bg-surface-alt border border-border/70 text-text-primary px-1.5 py-0.5 text-xs font-mono font-medium">
                      {children}
                    </code>
                  );
                },
                a: ({ children, ...props }) => (
                  <a
                    {...props}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent font-medium underline underline-offset-2 decoration-accent/40 hover:decoration-accent hover:text-accent-hover transition-colors"
                  >
                    {children}
                  </a>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 my-2 space-y-1 leading-relaxed text-text-primary">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 my-2 space-y-1 leading-relaxed text-text-primary">{children}</ol>
                ),
                li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                h1: ({ children }) => (
                  <h1 className="text-xl font-bold mt-5 mb-2.5 text-text-primary border-b border-border pb-1.5">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-lg font-bold mt-4 mb-2 text-text-primary">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-base font-semibold mt-3.5 mb-1.5 text-text-primary">{children}</h3>
                ),
                p: ({ children }) => <p className="my-2 leading-relaxed">{children}</p>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-accent pl-4 py-1 my-3 text-text-secondary bg-surface-alt/50 rounded-r-lg italic">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="my-4 overflow-x-auto rounded-xl border border-border/80 shadow-xs bg-surface">
                    <table className="w-full text-xs text-left border-collapse">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-surface-alt border-b border-border text-text-primary font-semibold">
                    {children}
                  </thead>
                ),
                th: ({ children }) => (
                  <th className="px-3.5 py-2.5 font-semibold text-text-primary border-b border-border font-sans">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3.5 py-2.5 border-b border-border/40 text-text-secondary font-sans leading-relaxed hover:bg-surface-alt/30 transition-colors">
                    {children}
                  </td>
                ),
                tr: ({ children }) => (
                  <tr className="border-b border-border/40 last:border-0 hover:bg-surface-alt/40 transition-colors">
                    {children}
                  </tr>
                ),
                hr: () => <hr className="my-5 border-border" />,
                strong: ({ children }) => (
                  <strong className="font-semibold text-text-primary">{children}</strong>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}


