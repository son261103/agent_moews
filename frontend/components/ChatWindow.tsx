"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import MessageBubble from "./MessageBubble";
import ThinkingBlock from "./ThinkingBlock";
import ToolCard from "./ToolCard";
import { streamChat, StreamEvent } from "@/lib/sse";
import { getThread } from "@/lib/api";

interface Message {
  id: string;
  content: string;
  isUser: boolean;
}

interface ToolCall {
  id: string;
  tool: string;
  status: "running" | "done";
  output?: string;
}

interface ThinkingState {
  isRunning: boolean;
  content: string;
}

const EXAMPLE_PROMPTS = [
  "Thời tiết hôm nay ở Hà Nội thế nào?",
  "Cho tôi xem tin tức mới nhất",
  "Bây giờ là mấy giờ rồi?",
  "Tìm kiếm giúp tôi thông tin về LangChain",
];

export default function ChatWindow({
  threadId,
  onThreadUpdated,
}: {
  threadId: string;
  onThreadUpdated?: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [streamContent, setStreamContent] = useState("");
  const [thinking, setThinking] = useState<ThinkingState>({ isRunning: false, content: "" });
  const bottomRef = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const toolIdCounter = useRef(0);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamContent, toolCalls, thinking]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRef.current?.();
      stopRef.current = null;
    };
  }, [threadId]);

  // Load thread history on mount
  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setToolCalls([]);
    setStreamContent("");
    setThinking({ isRunning: false, content: "" });
    getThread(threadId).then((thread) => {
      if (cancelled || !thread) return;
      setMessages(
        thread.messages.map((m, i) => ({
          id: `${m.timestamp}-${i}`,
          content: m.content,
          isUser: m.role === "user",
        }))
      );
    });
    return () => {
      cancelled = true;
    };
  }, [threadId]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, [input]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      isUser: true,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setToolCalls([]);
    setStreamContent("");
    setThinking({ isRunning: false, content: "" });
    toolIdCounter.current = 0;

    let buffer = "";
    stopRef.current?.();
    stopRef.current = streamChat(
      threadId,
      input.trim(),
      (event: StreamEvent) => {
        switch (event.type) {
          case "reset":
            buffer = "";
            setStreamContent("");
            setToolCalls([]);
            setThinking({ isRunning: false, content: "" });
            break;

          case "token":
            buffer += event.content || "";
            setStreamContent(buffer);
            break;

          case "tool_start":
            toolIdCounter.current += 1;
            setToolCalls((prev) => [
              ...prev,
              {
                id: `tool-${toolIdCounter.current}`,
                tool: event.tool || "unknown",
                status: "running",
              },
            ]);
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

          case "reflection":
            if (event.status === "start") {
              setThinking((prev) => ({ ...prev, isRunning: true }));
            } else if (event.status === "end") {
              setThinking({
                isRunning: false,
                content: event.content || "",
              });
            }
            break;

          case "plan":
            // Plan events are informational; we handle them gracefully
            // They could be shown in thinking block if desired
            break;

          case "done": {
            const finalContent = buffer;
            if (finalContent) {
              setMessages((prev) => [
                ...prev,
                {
                  id: `msg-${Date.now()}`,
                  content: finalContent,
                  isUser: false,
                },
              ]);
            }
            buffer = "";
            setStreamContent("");
            setIsLoading(false);
            setThinking((prev) => ({ ...prev, isRunning: false }));
            onThreadUpdated?.();
            break;
          }

          case "error":
            setMessages((prev) => [
              ...prev,
              {
                id: `msg-${Date.now()}`,
                content: `Lỗi: ${event.message || "Đã xảy ra lỗi không xác định"}`,
                isUser: false,
              },
            ]);
            setIsLoading(false);
            setThinking((prev) => ({ ...prev, isRunning: false }));
            onThreadUpdated?.();
            break;
        }
      },
      (err) => {
        setIsLoading(false);
        setThinking({ isRunning: false, content: "" });
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}`,
            content: `Lỗi: ${err.message || "Không kết nối được máy chủ"}`,
            isUser: false,
          },
        ]);
      }
    );
  }, [input, isLoading, threadId, onThreadUpdated]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExampleClick = (prompt: string) => {
    setInput(prompt);
    textareaRef.current?.focus();
  };

  const hasMessages = messages.length > 0 || streamContent;

  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Header */}
      <div className="flex-shrink-0 h-14 border-b border-border flex items-center px-6">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-success" />
          <span className="text-sm font-semibold text-text-primary">Agent Moew</span>
        </div>
        {isLoading && (
          <div className="ml-4 flex items-center gap-2 text-xs text-text-tertiary">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span>Đang xử lý...</span>
          </div>
        )}
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full px-6">
            <div className="w-16 h-16 rounded-2xl bg-panel flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-text-on-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-text-primary mb-1">Agent Moew</h2>
            <p className="text-sm text-text-secondary mb-8">AI Agent thông minh, sẵn sàng hỗ trợ bạn</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
              {EXAMPLE_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(prompt)}
                  className="text-left p-3.5 rounded-xl border border-border bg-surface hover:bg-surface-alt hover:border-border-strong transition-all duration-150 text-sm text-text-secondary hover:text-text-primary group"
                >
                  <span className="line-clamp-2">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message list */
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-2">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} content={msg.content} isUser={msg.isUser} />
            ))}

            {/* Tool calls */}
            {toolCalls.length > 0 && (
              <div className="ml-11 space-y-2 py-1">
                {toolCalls.map((tc, i) => (
                  <ToolCard
                    key={tc.id}
                    tool={tc.tool}
                    status={tc.status}
                    output={tc.output}
                    index={i}
                  />
                ))}
              </div>
            )}

            {/* Thinking block */}
            {(thinking.isRunning || thinking.content) && (
              <div className="ml-11 py-1">
                <ThinkingBlock
                  isRunning={thinking.isRunning}
                  content={thinking.content}
                />
              </div>
            )}

            {/* Streaming message */}
            {streamContent && (
              <MessageBubble content={streamContent} isUser={false} isStreaming={true} />
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-border bg-surface">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="relative flex items-center gap-2 rounded-2xl border border-border bg-white shadow-sm focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/20 transition-all duration-150">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isLoading ? "Agent đang xử lý..." : "Hỏi agent bất cứ điều gì..."}
              rows={1}
              className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none min-h-[44px] max-h-[200px]"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="flex-shrink-0 w-9 h-9 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-colors duration-150"
            >
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <p className="text-xs text-text-tertiary text-center mt-2">
            Nhấn <kbd className="px-1 py-0.5 rounded bg-surface-alt border border-border text-[10px] font-mono">Enter</kbd> để gửi, <kbd className="px-1 py-0.5 rounded bg-surface-alt border border-border text-[10px] font-mono">Shift+Enter</kbd> xuống dòng
          </p>
        </div>
      </div>
    </div>
  );
}


