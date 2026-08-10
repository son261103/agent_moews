const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function listThreads() {
  const res = await fetch(`${API_URL}/threads`);
  if (!res.ok) return [];
  return res.json();
}

export async function getThread(threadId: string) {
  const res = await fetch(`${API_URL}/threads/${threadId}`);
  if (!res.ok) return null;
  return res.json();
}
