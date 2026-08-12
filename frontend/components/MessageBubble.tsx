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
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 whitespace-pre-wrap ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-900"
        } relative`}
      >
        {isUser ? (
          content
        ) : (
          <ReactMarkdown
            components={{
              pre: ({ children }) => (
                <pre className="overflow-x-auto rounded bg-gray-800 p-3 text-gray-100 text-xs my-2">
                  {children}
                </pre>
              ),
              code: ({ children, className }) => {
                const isBlock = className?.includes("language-");
                return isBlock ? (
                  <code className={className}>{children}</code>
                ) : (
                  <code className="rounded bg-gray-200 px-1 py-0.5 text-xs">
                    {children}
                  </code>
                );
              },
              a: ({ children, ...props }) => (
                <a
                  {...props}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 underline"
                >
                  {children}
                </a>
              ),
              ul: ({ children }) => (
                <ul className="list-disc pl-5 my-1">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal pl-5 my-1">{children}</ol>
              ),
              li: ({ children }) => <li className="my-0.5">{children}</li>,
              h1: ({ children }) => (
                <h1 className="text-xl font-bold my-2">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-lg font-bold my-2">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-bold my-1">{children}</h3>
              ),
              p: ({ children }) => <p className="my-1">{children}</p>,
            }}
          >
            {content}
          </ReactMarkdown>
        )}
        {isStreaming && (
          <span className="absolute right-2 bottom-1 animate-pulse text-gray-500">
            ▋
          </span>
        )}
      </div>
    </div>
  );
}
