"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import ThreadSidebar from "@/components/ThreadSidebar";

export default function Home() {
  const [currentThreadId, setCurrentThreadId] = useState("default");

  return (
    <div className="flex h-full">
      <ThreadSidebar
        currentThreadId={currentThreadId}
        onSelectThread={setCurrentThreadId}
        onNewThread={() => setCurrentThreadId(`thread-${Date.now()}`)}
      />
      <main className="flex-1">
        <ChatWindow key={currentThreadId} threadId={currentThreadId} />
      </main>
    </div>
  );
}
