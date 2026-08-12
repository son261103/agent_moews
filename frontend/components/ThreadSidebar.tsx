"use client";

import { listThreads, deleteThread } from "@/lib/api";
import useSWR from "swr";

interface Thread {
  thread_id: string;
  last_message: string;
}

export default function ThreadSidebar({
  currentThreadId,
  onSelectThread,
  onNewThread,
  refreshKey,
}: {
  currentThreadId: string;
  onSelectThread: (id: string) => void;
  onNewThread: () => void;
  refreshKey: number;
}) {
  const { data: threads, mutate } = useSWR(["threads", refreshKey], listThreads);

  const handleDelete = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    const ok = await deleteThread(threadId);
    if (ok) {
      mutate();
      if (currentThreadId === threadId) {
        onNewThread();
      }
    }
  };

  return (
    <div className="w-72 bg-panel flex flex-col border-r border-panel-border select-none">
      {/* App Branding & New Chat Button */}
      <div className="p-4 border-b border-panel-border space-y-3">
        <div className="flex items-center gap-2.5 px-1">
          <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center text-white shadow-xs">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-bold text-text-on-dark tracking-wide">Agent Moew</h1>
            <p className="text-[11px] text-text-on-dark-muted/60 font-mono">v1.0 • LangGraph</p>
          </div>
        </div>

        <button
          onClick={onNewThread}
          className="w-full flex items-center justify-center gap-2 rounded-xl border border-panel-border bg-panel-hover hover:bg-panel-active text-text-on-dark py-2.5 text-sm font-medium transition-all duration-150 shadow-xs active:scale-[0.98]"
        >
          <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14m-7-7h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Cuộc trò chuyện mới
        </button>
      </div>

      {/* Thread List */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
        {threads?.map((t: Thread) => {
          const isSelected = currentThreadId === t.thread_id;
          return (
            <div
              key={t.thread_id}
              onClick={() => onSelectThread(t.thread_id)}
              className={`group relative w-full px-3 py-2.5 rounded-xl text-left text-sm cursor-pointer transition-all duration-150 flex items-center justify-between gap-2 ${
                isSelected
                  ? "bg-panel-active text-text-on-dark font-medium shadow-xs"
                  : "text-text-on-dark-muted hover:bg-panel-hover hover:text-text-on-dark"
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate leading-snug text-xs sm:text-sm font-medium">
                  {t.last_message || "Cuộc trò chuyện mới"}
                </p>
                <p className="text-[10px] text-text-on-dark-muted/50 mt-0.5 font-mono">
                  ID: {t.thread_id.slice(0, 8)}
                </p>
              </div>

              {/* Delete Button */}
              <button
                onClick={(e) => handleDelete(e, t.thread_id)}
                title="Xóa cuộc trò chuyện"
                className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/20 hover:text-red-400 text-text-on-dark-muted/40 transition-all duration-150 flex-shrink-0"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          );
        })}

        {/* Empty state */}
        {(!threads || threads.length === 0) && (
          <div className="px-4 py-8 text-center">
            <svg className="w-8 h-8 mx-auto text-text-on-dark-muted/30 mb-2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p className="text-xs text-text-on-dark-muted/50">Chưa có lịch sử trò chuyện</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3.5 border-t border-panel-border bg-panel/50">
        <div className="flex items-center gap-2 text-xs text-text-on-dark-muted/60 font-mono">
          <div className="w-2 h-2 rounded-full bg-success animate-pulse flex-shrink-0" />
          <span className="truncate">Sẵn sàng phản hồi</span>
        </div>
      </div>
    </div>
  );
}

