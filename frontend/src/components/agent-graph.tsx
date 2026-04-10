import { Agent, Task } from "@/lib/api/types";
import { getAgentDisplayName } from "@/lib/agents/display-name";
import { useI18n } from "@/lib/i18n/language-context";

interface AgentGraphProps {
  agents: Agent[];
  selectedTask: Task | null;
}

export function AgentGraph({ agents, selectedTask }: AgentGraphProps) {
  const { isChinese, text } = useI18n();
  const highlightedAgentIds = new Set([
    ...(selectedTask?.assigned_agent_ids ?? []),
    ...(selectedTask?.current_agent_id ? [selectedTask.current_agent_id] : [])
  ]);

  return (
    <section className="nexus-panel p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionAgentGraph}</h3>
      <p className="mb-3 text-xs text-[#6b6860]">
        {selectedTask
          ? isChinese
            ? `当前高亮与 ${selectedTask.task_id} 相关的 Agent`
            : `Highlighting agents related to ${selectedTask.task_id}`
          : isChinese
            ? "请选择任务以高亮已分配与当前持有者 Agent。"
            : "Select a task to highlight assigned and current owner agents."}
      </p>
      {agents.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂无 Agent。" : "No agents available."}</p> : null}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {agents.map((agent) => (
          <div
            key={agent.agent_id}
            className={`rounded border p-3 text-xs ${
              highlightedAgentIds.has(agent.agent_id)
                ? "border-[#d97757] bg-[#fff4ef]"
                : "border-[#ddd7ca] bg-[#fffcf6]"
            }`}
          >
            <p className="font-semibold text-[#141413]">{getAgentDisplayName(agent, isChinese)}</p>
            <p className="text-[#6b6860]">{agent.agent_id}</p>
            <p className="mt-1 text-[#8a867d]">{isChinese ? "角色" : "role"}: {agent.role}</p>
            <p className="mt-1 text-[#8a867d]">{isChinese ? "状态" : "status"}: {agent.status}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              {agent.skills.length > 0 ? (
                agent.skills.map((skill) => (
                  <span key={skill} className="rounded-full border border-[#d8d2c4] bg-[#f5f1e7] px-2 py-0.5 text-[11px] text-[#6b6860]">
                    {skill}
                  </span>
                ))
              ) : (
                <span className="text-[#8a867d]">{isChinese ? "未标记技能" : "No skills tagged"}</span>
              )}
            </div>
            {selectedTask?.current_agent_id === agent.agent_id ? (
              <p className="mt-2 text-[11px] font-medium text-[#c96544]">{isChinese ? "当前持有者" : "Current owner"}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

