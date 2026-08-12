export interface StreamEvent {
  type: "token" | "tool_start" | "tool_end" | "plan" | "reflection" | "done" | "error" | "reset";
  content?: string;
  tool?: string;
  input?: any;
  output?: string;
  message?: string;
  status?: "start" | "end";
  run_id?: string;
}

export function streamChat(
  threadId: string,
  message: string,
  onEvent: (event: StreamEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const url = new URL(`${apiUrl}/chat/stream`);

  const body = JSON.stringify({ thread_id: threadId, message });
  const controller = new AbortController();

  fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const reader = response.body?.getReader();
      if (!reader) return;

      const decoder = new TextDecoder();
      let buffer = "";

      const processLine = (line: string) => {
        const clean = line.replace(/\r$/, "");
        if (!clean.startsWith("data:")) return;
        const payload = clean.slice(5).trim();
        if (!payload) return;
        try {
          const event = JSON.parse(payload) as StreamEvent;
          onEvent(event);
        } catch {}
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n")) !== -1) {
          processLine(buffer.slice(0, idx));
          buffer = buffer.slice(idx + 1);
        }
      }
      if (buffer) processLine(buffer);
    })
    .catch((err) => {
      if (err instanceof DOMException && err.name === "AbortError") return;
      onError?.(err);
    });

  return () => controller.abort();
}
