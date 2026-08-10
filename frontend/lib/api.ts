const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface ThreadInfo {
  thread_id: string;
  created_at: string;
  last_message: string;
}

export interface ThreadMessage {
  role: string;
  content: string;
  timestamp: string;
}

export interface ThreadDetail {
  thread_id: string;
  messages: ThreadMessage[];
}

export async function listThreads(): Promise<ThreadInfo[]> {
  const res = await fetch(`${API_URL}/threads`);
  if (!res.ok) return [];
  return res.json();
}

export async function getThread(threadId: string): Promise<ThreadDetail | null> {
  const res = await fetch(`${API_URL}/threads/${threadId}`);
  if (!res.ok) return null;
  return res.json();
}
