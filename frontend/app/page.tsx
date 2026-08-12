"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ThreadSidebar from "@/components/ThreadSidebar";

export default function Home() {
  const [currentThreadId, setCurrentThreadId] = useState("default");
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="flex h-full">
      <ThreadSidebar
        currentThreadId={currentThreadId}
        onSelectThread={setCurrentThreadId}
        onNewThread={() => setCurrentThreadId(`thread-${Date.now()}`)}
        refreshKey={refreshKey}
      />
      <main className="flex-1 min-w-0">
        <ChatWindow
          key={currentThreadId}
          threadId={currentThreadId}
          onThreadUpdated={() => setRefreshKey((k) => k + 1)}
        />
      </main>
    </div>
  );
}
