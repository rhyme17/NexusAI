"use client";

import { BusMessage } from "@/lib/api/types";
import { getDecisionActor, getDecisionReason, getEventField, getFailureCode, getFailureMessage } from "@/lib/api/event-observability";
import { useI18n } from "@/lib/i18n/language-context";

interface EventInsightsProps {
  latestClaim: BusMessage | undefined;
  handoffCount: number;
  latestDecision: BusMessage | undefined;
  latestFailure: BusMessage | undefined;
}

export function EventInsights({ latestClaim, handoffCount, latestDecision, latestFailure }: EventInsightsProps) {
  const { isChinese, text } = useI18n();
  return (
    <section className="nexus-panel p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionEventInsights}</h3>

      <div className="grid gap-2 md:grid-cols-4">
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
          <p className="text-[#8a867d]">{isChinese ? "最新持有者" : "Latest Owner"}</p>
          <p className="mt-1 font-semibold text-[#141413]">{getEventField(latestClaim, ["agent_id", "to_agent_id"])}</p>
        </div>
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
          <p className="text-[#8a867d]">{isChinese ? "交接次数" : "Handoffs"}</p>
          <p className="mt-1 font-semibold text-[#141413]">{handoffCount}</p>
        </div>
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
          <p className="text-[#8a867d]">{isChinese ? "最新决策" : "Latest Decision"}</p>
          <p className="mt-1 font-semibold text-[#141413]">{getDecisionActor(latestDecision)}</p>
        </div>
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
          <p className="text-[#8a867d]">{isChinese ? "最近失败" : "Latest Failure"}</p>
          <p className="mt-1 font-semibold text-[#141413]">{getFailureCode(latestFailure)}</p>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2">
          <p className="text-[#8a867d]">{isChinese ? "决策原因" : "Decision Reason"}</p>
          <p className="mt-1 text-[#3e3a35]">{getDecisionReason(latestDecision)}</p>
        </div>
        <div className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2">
          <p className="text-[#8a867d]">{isChinese ? "失败信息" : "Failure Message"}</p>
          <p className="mt-1 text-[#3e3a35]">{getFailureMessage(latestFailure)}</p>
        </div>
      </div>
    </section>
  );
}

