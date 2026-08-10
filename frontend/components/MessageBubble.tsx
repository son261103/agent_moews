"use client";

export default function MessageBubble({
  content,
  isUser,
}: {
  content: string;
  isUser: boolean;
}) {
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 whitespace-pre-wrap ${
          isUser ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {content}
      </div>
    </div>
  );
}
