"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import MessageBubble, { ToolCall, ThinkingState } from "./MessageBubble";
import { streamChat, StreamEvent } from "@/lib/sse";
import { getThread } from "@/lib/api";

interface Message {
  id: string;
  isUser: boolean;
  content: string;
  toolCalls?: ToolCall[];
  thinking?: ThinkingState;
  isStreaming?: boolean;
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const stopRef = useRef<(() => void) | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Cleanup on unmount / thread change
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
    getThread(threadId).then((thread) => {
      if (cancelled || !thread) return;
      setMessages(
        thread.messages.map((m, i) => ({
          id: `${m.timestamp}-${i}`,
          content: m.content,
          isUser: m.role === "user",
          isStreaming: false,
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
      id: `user-${Date.now()}`,
      content: input.trim(),
      isUser: true,
    };

    const assistantMessageId = `assistant-${Date.now()}`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      content: "",
      isUser: false,
      toolCalls: [],
      thinking: { isRunning: false, content: "" },
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsLoading(true);

    stopRef.current?.();
    stopRef.current = streamChat(
      threadId,
      input.trim(),
      (event: StreamEvent) => {
        setMessages((prev) => {
          const lastIdx = prev.length - 1;
          if (lastIdx < 0 || prev[lastIdx].id !== assistantMessageId) return prev;

          const currentMsg = { ...prev[lastIdx] };
          const toolCalls = [...(currentMsg.toolCalls || [])];
          const thinking = { ...(currentMsg.thinking || { isRunning: false, content: "" }) };

          switch (event.type) {
            case "token":
              currentMsg.content = (currentMsg.content || "") + (event.content || "");
              break;

            case "tool_start": {
              const toolId = event.run_id || `tool-${Date.now()}-${Math.random()}`;
              toolCalls.push({
                id: toolId,
                tool: event.tool || "unknown",
                status: "running",
              });
              break;
            }

            case "tool_end": {
              let updated = false;
              for (let i = 0; i < toolCalls.length; i++) {
                const tc = toolCalls[i];
                const matchById = event.run_id && tc.id === event.run_id;
                const matchByName = !event.run_id && tc.tool === event.tool && tc.status === "running";
                if (matchById || matchByName) {
                  toolCalls[i] = { ...tc, status: "done", output: event.output };
                  updated = true;
                  break;
                }
              }
              if (!updated && event.tool) {
                toolCalls.push({
                  id: event.run_id || `tool-${Date.now()}`,
                  tool: event.tool,
                  status: "done",
                  output: event.output,
                });
              }
              break;
            }

            case "reflection":
              if (event.status === "start") {
                thinking.isRunning = true;
              } else if (event.status === "end") {
                thinking.isRunning = false;
                thinking.content = event.content || "";
              }
              break;

            case "done":
              currentMsg.isStreaming = false;
              thinking.isRunning = false;
              for (let i = 0; i < toolCalls.length; i++) {
                if (toolCalls[i].status === "running") {
                  toolCalls[i] = { ...toolCalls[i], status: "done" };
                }
              }
              setTimeout(() => {
                setIsLoading(false);
                onThreadUpdated?.();
              }, 0);
              break;

            case "error":
              currentMsg.isStreaming = false;
              currentMsg.content = `Lỗi: ${event.message || "Đã xảy ra lỗi không xác định"}`;
              thinking.isRunning = false;
              for (let i = 0; i < toolCalls.length; i++) {
                if (toolCalls[i].status === "running") {
                  toolCalls[i] = { ...toolCalls[i], status: "done" };
                }
              }
              setTimeout(() => {
                setIsLoading(false);
                onThreadUpdated?.();
              }, 0);
              break;
          }

          currentMsg.toolCalls = toolCalls;
          currentMsg.thinking = thinking;

          const next = [...prev];
          next[lastIdx] = currentMsg;
          return next;
        });
      },
      (err) => {
        setMessages((prev) => {
          const lastIdx = prev.length - 1;
          if (lastIdx < 0 || prev[lastIdx].id !== assistantMessageId) return prev;

          const currentMsg = { ...prev[lastIdx] };
          currentMsg.isStreaming = false;
          currentMsg.content = `Lỗi: ${err.message || "Không kết nối được máy chủ"}`;

          const toolCalls = [...(currentMsg.toolCalls || [])];
          for (let i = 0; i < toolCalls.length; i++) {
            if (toolCalls[i].status === "running") {
              toolCalls[i] = { ...toolCalls[i], status: "done" };
            }
          }
          currentMsg.toolCalls = toolCalls;

          const next = [...prev];
          next[lastIdx] = currentMsg;
          return next;
        });
        setTimeout(() => {
          setIsLoading(false);
        }, 0);
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

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Header */}
      <div className="flex-shrink-0 h-14 border-b border-border flex items-center justify-between px-6 bg-surface/80 backdrop-blur-sm z-10">
        <div className="flex items-center gap-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-success" />
          <span className="text-sm font-semibold text-text-primary">Agent Moew</span>
          <span className="text-xs text-text-tertiary font-mono bg-surface-alt px-2 py-0.5 rounded-md border border-border">
            LangGraph + DeepAgents
          </span>
        </div>
        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-text-tertiary">
            <span className="inline-block w-2 h-2 rounded-full bg-accent animate-ping" />
            <span className="font-medium text-accent">Agent đang suy nghĩ & xử lý...</span>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center h-full px-6">
            <div className="w-16 h-16 rounded-2xl bg-panel flex items-center justify-center mb-6 shadow-md">
              <svg className="w-8 h-8 text-text-on-dark" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-text-primary mb-1 tracking-tight">Agent Moew</h2>
            <p className="text-sm text-text-secondary mb-8">AI Agent thông minh tích hợp công cụ & LangGraph</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
              {EXAMPLE_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => handleExampleClick(prompt)}
                  className="text-left p-3.5 rounded-xl border border-border bg-surface hover:bg-surface-alt hover:border-border-strong transition-all duration-150 text-sm text-text-secondary hover:text-text-primary group shadow-xs hover:shadow-sm"
                >
                  <span className="line-clamp-2">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message List */
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-4">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                content={msg.content}
                isUser={msg.isUser}
                isStreaming={msg.isStreaming}
                toolCalls={msg.toolCalls}
                thinking={msg.thinking}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 border-t border-border bg-surface">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="relative flex items-center gap-2 rounded-2xl border border-border bg-white shadow-xs focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20 transition-all duration-150">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isLoading ? "Agent đang suy nghĩ & thực thi công cụ..." : "Hỏi agent bất cứ điều gì..."}
              rows={1}
              className="flex-1 resize-none bg-transparent px-4 py-3 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none min-h-[44px] max-h-[200px]"
              disabled={isLoading}
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="flex-shrink-0 w-9 h-9 mr-1.5 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-all duration-150 shadow-xs"
            >
              <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M5 12h14M12 5l7 7-7 7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <p className="text-[11px] text-text-tertiary text-center mt-2">
            Nhấn <kbd className="px-1 py-0.5 rounded bg-surface-alt border border-border text-[10px] font-mono">Enter</kbd> để gửi, <kbd className="px-1 py-0.5 rounded bg-surface-alt border border-border text-[10px] font-mono">Shift+Enter</kbd> xuống dòng
          </p>
        </div>
      </div>
    </div>
  );
}



