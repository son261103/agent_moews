"use client";

import { listThreads } from "@/lib/api";
import useSWR from "swr";

interface Thread {
  thread_id: string;
  last_message: string;
}

export default function ThreadSidebar({
  currentThreadId,
  onSelectThread,
  onNewThread,
}: {
  currentThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
}) {
  const { data: threads } = useSWR("threads", listThreads);

  return (
    <div className="w-72 bg-panel flex flex-col border-r border-panel-border">
      {/* Header */}
      <div className="p-4 border-b border-panel-border">
        <button
          onClick={onNewThread}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-panel-border bg-panel-hover hover:bg-panel-active text-text-on-dark py-2.5 text-sm font-medium transition-colors duration-150"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14m-7-7h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Cuộc trò chuyện mới
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto py-2">
        {threads?.map((t: Thread) => (
          <button
            key={t.thread_id}
            onClick={() => onSelectThread(t.thread_id)}
            className={`w-full px-4 py-3 text-left text-sm transition-colors duration-100 border-l-2 ${
              currentThreadId === t.thread_id
                ? "bg-panel-active border-accent text-text-on-dark"
                : "border-transparent text-text-on-dark-muted hover:bg-panel-hover hover:text-text-on-dark"
            }`}
          >
            <p className="font-medium truncate leading-snug">{t.last_message}</p>
            <p className="text-xs text-text-on-dark-muted/60 mt-1 font-mono">{t.thread_id.slice(0, 8)}</p>
          </button>
        ))}

        {/* Empty state */}
        {(!threads || threads.length === 0) && (
          <div className="px-4 py-8 text-center">
            <svg className="w-8 h-8 mx-auto text-text-on-dark-muted/40 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="text-xs text-text-on-dark-muted/50">Chưa có cuộc trò chuyện</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-panel-border">
        <div className="flex items-center gap-2 text-xs text-text-on-dark-muted/50">
          <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
          <span>Agent Moew</span>
        </div>
      </div>
    </div>
  );
}
