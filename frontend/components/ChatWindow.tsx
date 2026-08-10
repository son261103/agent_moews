"use client";

import { useEffect, useRef, useState } from "react";
import MessageBubble from "./MessageBubble";
import AgentSteps from "./AgentSteps";
import { streamChat, StreamEvent } from "@/lib/sse";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
}

interface ToolCall {
  tool: string;
  status: "running" | "done";
  output?: string;
}

export default function ChatWindow({ threadId }: { threadId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [plan, setPlan] = useState<string[]>([]);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [streamContent, setStreamContent] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent]);

  useEffect(() => {
    return () => {
      stopRef.current?.();
      stopRef.current = null;
    };
  }, []);

  const send = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input,
      isUser: true,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setPlan([]);
    setToolCalls([]);
    setStreamContent("");

    let buffer = "";
    stopRef.current?.();
    stopRef.current = streamChat(
      threadId,
      input,
      (event: StreamEvent) => {
        switch (event.type) {
          case "token":
            buffer += event.content || "";
            setStreamContent(buffer);
            break;
          case "tool_start":
            setToolCalls((prev) => [
              ...prev,
              { tool: event.tool || "", status: "running" },
            ]);
            setPlan((prev) =>
              prev.length === 0 ? [`Using tool: ${event.tool}`] : prev
            );
            break;
          case "tool_end":
            setToolCalls((prev) =>
              prev.map((tc) =>
                tc.tool === event.tool && tc.status === "running"
                  ? { ...tc, status: "done" as const, output: event.output }
                  : tc
              )
            );
            break;
          case "done":
            const finalContent = buffer;
            if (finalContent) {
              setMessages((prev) => [
                ...prev,
                {
                  id: (Date.now() + 1).toString(),
                  content: finalContent,
                  isUser: false,
                },
              ]);
            }
            buffer = "";
            setStreamContent("");
            setIsLoading(false);
            break;
          case "error":
            setMessages((prev) => [
              ...prev,
              {
                id: (Date.now() + 1).toString(),
                content: `Error: ${event.message}`,
                isUser: false,
              },
            ]);
            setIsLoading(false);
            break;
        }
      }
    );
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} content={msg.content} isUser={msg.isUser} />
        ))}
        {streamContent && (
          <MessageBubble content={streamContent} isUser={false} />
        )}
        {(isLoading || toolCalls.length > 0) && (
          <AgentSteps plan={plan} toolCalls={toolCalls} isRunning={isLoading} />
        )}
        <div ref={bottomRef} />
      </div>
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask the agent anything..."
            className="flex-1 rounded-lg border px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            onClick={send}
            disabled={isLoading || !input.trim()}
            className="rounded-lg bg-blue-600 px-6 py-2 text-white disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
