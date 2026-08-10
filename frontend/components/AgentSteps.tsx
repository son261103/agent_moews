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
    <div className="mt-2 w-full rounded-lg bg-gray-50 p-3 text-sm">
      {plan.length > 0 && (
        <div className="mb-2">
          <p className="font-semibold text-gray-600">Plan:</p>
          {plan.map((p, i) => (
            <p key={i} className="ml-2 text-gray-500">
              {i + 1}. {p}
            </p>
          ))}
        </div>
      )}
      {toolCalls.map((tc, i) => (
        <div key={i} className="mb-1 flex items-center gap-2">
          <span className={tc.status === "running" ? "animate-spin" : "text-green-500"}>
            {tc.status === "running" ? "⏳" : "✓"}
          </span>
          <span className="font-medium">{tc.tool}</span>
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
