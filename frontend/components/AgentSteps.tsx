"use client";

interface ToolCall {
  tool: string;
  status: "running" | "done";
  output?: string;
}

export default function AgentSteps({
  plan,
  toolCalls,
  isRunning,
}: {
  plan: string[];
  toolCalls: ToolCall[];
  isRunning: boolean;
}) {
  if (!isRunning && toolCalls.length === 0) return null;

  return (
    <div className="mt-2 w-full rounded-lg bg-gray-100 border border-gray-200 p-3 text-sm">
      {isRunning && (
        <div className="mb-2 flex items-center gap-2 text-blue-600">
          <span className="animate-spin">⟳</span>
          <span className="font-medium">Agent đang suy nghĩ...</span>
        </div>
      )}
      {plan.length > 0 && (
        <div className="mb-2">
          <p className="font-semibold text-gray-700">Plan:</p>
          {plan.map((p, i) => (
            <p key={i} className="ml-2 text-gray-600">
              {i + 1}. {p}
            </p>
          ))}
        </div>
      )}
      {toolCalls.map((tc, i) => (
        <div key={i} className="mb-1 flex items-center gap-2">
          <span className={tc.status === "running" ? "animate-spin text-blue-600" : "text-green-600"}>
            {tc.status === "running" ? "⟳" : "✓"}
          </span>
          <span className="font-medium text-gray-800">{tc.tool}</span>
          {tc.output && (
            <span className="text-gray-500 text-xs truncate max-w-[200px]">
              {tc.output}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
