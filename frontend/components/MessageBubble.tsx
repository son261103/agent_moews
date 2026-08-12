"use client";

import ReactMarkdown from "react-markdown";

export default function MessageBubble({
  content,
  isUser,
  isStreaming = false,
}: {
  content: string;
  isUser: boolean;
  isStreaming?: boolean;
}) {
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-br-md bg-user-bubble text-user-text px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-3 py-1">
      {/* Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-panel flex items-center justify-center mt-0.5">
        <svg className="w-4 h-4 text-text-on-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* Content */}
      <div className={`max-w-[80%] min-w-0 text-sm leading-relaxed text-text-primary ${isStreaming ? "streaming-cursor" : ""}`}>
        <ReactMarkdown
          components={{
            pre: ({ children }) => (
              <div className="my-3 rounded-lg overflow-hidden border border-border">
                <div className="flex items-center justify-between bg-[#21252B] px-4 py-1.5">
                  <span className="text-xs text-[#5C6370] font-mono">code</span>
                </div>
                <pre className="overflow-x-auto bg-code-bg p-4 text-code-text text-xs leading-relaxed">
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
                <code className="rounded-md bg-inline-code-bg text-inline-code-text px-1.5 py-0.5 text-xs font-mono font-medium">
                  {children}
                </code>
              );
            },
            a: ({ children, ...props }) => (
              <a
                {...props}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent underline underline-offset-2 decoration-accent/40 hover:decoration-accent transition-colors"
              >
                {children}
              </a>
            ),
            ul: ({ children }) => (
              <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal pl-5 my-2 space-y-1">{children}</ol>
            ),
            li: ({ children }) => <li className="leading-relaxed">{children}</li>,
            h1: ({ children }) => (
              <h1 className="text-xl font-bold mt-4 mb-2 text-text-primary">{children}</h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-lg font-bold mt-3 mb-1.5 text-text-primary">{children}</h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-base font-semibold mt-3 mb-1 text-text-primary">{children}</h3>
            ),
            p: ({ children }) => <p className="my-1.5">{children}</p>,
            blockquote: ({ children }) => (
              <blockquote className="border-l-3 border-accent/40 pl-4 my-2 text-text-secondary italic">
                {children}
              </blockquote>
            ),
            table: ({ children }) => (
              <div className="my-3 overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">{children}</table>
              </div>
            ),
            th: ({ children }) => (
              <th className="px-3 py-2 text-left font-semibold bg-surface-alt border-b border-border text-text-primary">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-3 py-2 border-b border-border/50">{children}</td>
            ),
            hr: () => <hr className="my-4 border-border" />,
            strong: ({ children }) => (
              <strong className="font-semibold text-text-primary">{children}</strong>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
