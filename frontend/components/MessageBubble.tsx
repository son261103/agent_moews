"use client";

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
        {content}
        {isStreaming && (
          <span className="absolute right-2 bottom-1 animate-pulse text-gray-500">
            ▋
          </span>
        )}
      </div>
    </div>
  );
}
