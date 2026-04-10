import { Agent } from "@/lib/api/types";

const DEFAULT_AGENT_ZH_NAMES: Record<string, string> = {
  agent_planner: "玄机策士",
  agent_research: "玄览探微",
  agent_writer: "翰墨执笔",
  agent_analyst: "洞玄析理",
  agent_reviewer: "鉴衡司议",
  agent_judge: "衡断天平"
};

const ROLE_FALLBACK_ZH_NAMES: Record<string, string> = {
  planner: "策士",
  research: "探微者",
  writer: "执笔者",
  analyst: "析理者",
  reviewer: "鉴衡者",
  judge: "衡断者"
};

export function getAgentDisplayName(agent: Agent, isChinese: boolean): string {
  if (!isChinese) {
    return agent.name;
  }
  const byId = DEFAULT_AGENT_ZH_NAMES[agent.agent_id];
  if (byId) {
    return byId;
  }
  const byRole = ROLE_FALLBACK_ZH_NAMES[agent.role.toLowerCase()];
  if (byRole) {
    return `${byRole}·${agent.name}`;
  }
  return agent.name;
}

