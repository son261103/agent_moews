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
    <div className="w-64 border-r bg-gray-50 flex flex-col">
      <div className="p-4 border-b">
        <button
          onClick={onNewThread}
          className="w-full rounded-lg bg-blue-600 py-2 text-white text-sm font-medium"
        >
          + New Thread
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads?.map((t: Thread) => (
          <button
            key={t.thread_id}
            onClick={() => onSelectThread(t.thread_id)}
            className={`w-full px-4 py-3 text-left text-sm hover:bg-gray-100 border-b ${
              currentThreadId === t.thread_id ? "bg-blue-50" : ""
            }`}
          >
            <p className="font-medium truncate">{t.last_message}</p>
            <p className="text-gray-500 text-xs mt-1">{t.thread_id.slice(0, 8)}</p>
          </button>
        ))}
        {(!threads || threads.length === 0) && (
          <p className="p-4 text-gray-400 text-sm text-center">No threads yet</p>
        )}
      </div>
    </div>
  );
}
