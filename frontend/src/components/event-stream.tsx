import { useEffect, useMemo, useState } from "react";

import { BusMessage, MESSAGE_TYPE_OPTIONS, MessageType } from "@/lib/api/types";
import { sortEventsByTimestampDesc } from "@/lib/api/event-observability";
import { getEventConnectionCopy, getUserFacingErrorMessage } from "@/lib/errors";
import { useI18n } from "@/lib/i18n/language-context";

const PAYLOAD_PREVIEW_KEYS: Record<string, string[]> = {
  TaskFailed: ["error_code", "error_category", "user_message"],
  Decision: ["decided_by", "reason"],
  TaskHandoff: ["from_agent_id", "to_agent_id", "reason"],
  TaskUpdate: ["workflow_event", "status", "failure_policy"],
  Vote: ["agent_id", "confidence"],
  TaskResult: ["summary", "mode"]
};

function renderPayloadPreview(event: BusMessage): string | null {
  const keys = PAYLOAD_PREVIEW_KEYS[event.type];
  if (!keys) {
    return null;
  }

  const parts = keys
    .map((key) => {
      const value = event.payload[key];
      if (value === undefined || value === null) {
        return null;
      }
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return `${key}=${String(value)}`;
      }
      return `${key}=${JSON.stringify(value)}`;
    })
    .filter((item): item is string => item !== null);

  return parts.length > 0 ? parts.join(" | ") : null;
}

interface EventStreamProps {
  events: BusMessage[];
  error: Error | string | null;
  connectionState: "idle" | "connecting" | "connected" | "reconnecting";
  selectedTypes: MessageType[];
  from: string;
  to: string;
  onToggleType: (type: MessageType) => void;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  onRefresh: () => void;
}

export function EventStream({
  events,
  error,
  connectionState,
  selectedTypes,
  from,
  to,
  onToggleType,
  onFromChange,
  onToChange,
  onRefresh
}: EventStreamProps) {
  const { isChinese, text } = useI18n();
  const [replayEnabled, setReplayEnabled] = useState(false);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replaySpeedMs, setReplaySpeedMs] = useState(700);
  const [replayCursor, setReplayCursor] = useState(0);
  const activeFilterLabel = selectedTypes.length > 0 ? selectedTypes.join(", ") : isChinese ? "全部事件类型" : "all event types";
  const connectionCopy = getEventConnectionCopy(connectionState, isChinese, Boolean(error));
  const connectionToneClass =
    connectionCopy.tone === "success"
      ? "border-[#9bc5a7] bg-[#edf7ef] text-[#2f5d3e]"
      : connectionCopy.tone === "warning"
        ? "border-[#e6c8ae] bg-[#fff6eb] text-[#8a5f33]"
        : "border-[#ddd7ca] bg-[#fffcf6] text-[#6b6860]";

  const timelineEvents = useMemo(
    () => [...events].sort((left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()),
    [events]
  );

  useEffect(() => {
    if (!replayEnabled) {
      return;
    }
    if (replayCursor >= Math.max(0, timelineEvents.length - 1)) {
      setReplayPlaying(false);
    }
  }, [replayCursor, replayEnabled, timelineEvents.length]);

  useEffect(() => {
    if (!replayEnabled || !replayPlaying || timelineEvents.length === 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      setReplayCursor((previous) => Math.min(previous + 1, timelineEvents.length - 1));
    }, replaySpeedMs);
    return () => window.clearTimeout(timer);
  }, [replayEnabled, replayPlaying, replayCursor, replaySpeedMs, timelineEvents.length]);

  const visibleEvents = replayEnabled
    ? timelineEvents.slice(0, Math.min(replayCursor + 1, timelineEvents.length)).reverse()
    : sortEventsByTimestampDesc(events);

  return (
    <section className="nexus-panel p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wide text-[#8a867d]">{text.sectionEventStream}</h3>
          <p className="mt-1 text-xs text-[#6b6860]">
            {isChinese ? `${visibleEvents.length} 条可见` : `${visibleEvents.length} visible`} • {isChinese ? "过滤" : "filters"}: {activeFilterLabel}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="nexus-button-ghost rounded-lg px-2 py-1 text-xs"
        >
          {isChinese ? "刷新" : "Refresh"}
        </button>
      </div>

      <div className={`mb-3 rounded-xl border p-3 text-xs ${connectionToneClass}`}>
        <p className="font-medium">{connectionCopy.title}</p>
        <p className="mt-1 leading-relaxed">{connectionCopy.detail}</p>
      </div>

      <div className="mb-3 grid gap-2 md:grid-cols-2">
        <label className="text-xs text-[#6b6860]">
          {isChinese ? "开始时间" : "From"}
          <input
            type="datetime-local"
            value={from}
            onChange={(event) => onFromChange(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs"
          />
        </label>
        <label className="text-xs text-[#6b6860]">
          {isChinese ? "结束时间" : "To"}
          <input
            type="datetime-local"
            value={to}
            onChange={(event) => onToChange(event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#d8d2c4] bg-[#fffdf9] px-2 py-1 text-xs"
          />
        </label>
      </div>

      <div className="mb-3 rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-3 text-xs">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="font-medium text-[#3e3a35]">{isChinese ? "回放视图（Phase B）" : "Replay view (Phase B)"}</p>
          <button
            data-testid="event-replay-toggle"
            type="button"
            onClick={() => {
              const next = !replayEnabled;
              setReplayEnabled(next);
              setReplayPlaying(false);
              setReplayCursor(0);
            }}
            className={`rounded px-2 py-1 ${replayEnabled ? "bg-[#141413] text-[#f5f3ec]" : "bg-[#f4efe4] text-[#6b6860]"}`}
          >
            {replayEnabled ? (isChinese ? "退出回放" : "Exit replay") : (isChinese ? "进入回放" : "Enter replay")}
          </button>
        </div>
        {replayEnabled ? (
          <div className="mt-3 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <button
                data-testid="event-replay-play"
                type="button"
                onClick={() => setReplayPlaying((previous) => !previous)}
                disabled={timelineEvents.length === 0}
                className="rounded bg-[#f4efe4] px-2 py-1 text-[#6b6860] disabled:opacity-50"
              >
                {replayPlaying ? (isChinese ? "暂停" : "Pause") : (isChinese ? "播放" : "Play")}
              </button>
              <button
                type="button"
                onClick={() => {
                  setReplayPlaying(false);
                  setReplayCursor(0);
                }}
                className="rounded bg-[#f4efe4] px-2 py-1 text-[#6b6860]"
              >
                {isChinese ? "回到起点" : "Reset"}
              </button>
              <label className="text-[#6b6860]">
                {isChinese ? "速度" : "Speed"}
                <select
                  value={String(replaySpeedMs)}
                  onChange={(event) => setReplaySpeedMs(Number(event.target.value))}
                  className="ml-2 rounded border border-[#d8d2c4] bg-[#fffdf9] px-1 py-0.5"
                >
                  <option value="1000">1.0x</option>
                  <option value="700">1.5x</option>
                  <option value="450">2.0x</option>
                </select>
              </label>
            </div>
            <input
              data-testid="event-replay-seek"
              type="range"
              min={0}
              max={Math.max(0, timelineEvents.length - 1)}
              value={Math.min(replayCursor, Math.max(0, timelineEvents.length - 1))}
              onChange={(event) => {
                setReplayPlaying(false);
                setReplayCursor(Number(event.target.value));
              }}
              className="w-full"
            />
            <p className="text-[#6b6860]">
              {isChinese ? "回放进度" : "Replay progress"}: {timelineEvents.length === 0 ? 0 : Math.min(replayCursor + 1, timelineEvents.length)} / {timelineEvents.length}
            </p>
          </div>
        ) : null}
      </div>

      <div className="mb-3 flex flex-wrap gap-1">
        {MESSAGE_TYPE_OPTIONS.map((type) => {
          const selected = selectedTypes.includes(type);
          return (
            <button
              key={type}
              type="button"
              onClick={() => onToggleType(type)}
              className={`rounded px-2 py-1 text-xs ${
                selected ? "bg-[#d97757] text-white" : "bg-[#f4efe4] text-[#6b6860]"
              }`}
            >
              {type}
            </button>
          );
        })}
      </div>

      {error ? (
        <p className="mb-2 text-xs text-[#c0453a]">
          {getUserFacingErrorMessage(error, {
            isChinese,
            context: connectionState === "reconnecting" ? "websocket" : "events"
          })}
        </p>
      ) : null}
      {visibleEvents.length === 0 ? <p className="text-sm text-[#6b6860]">{isChinese ? "暂未捕获事件。" : "No events captured yet."}</p> : null}
      <ul data-testid="event-stream-list" className="max-h-[34rem] space-y-2 overflow-auto pr-1">
        {visibleEvents.map((event) => (
          <li key={event.message_id} className="rounded-xl border border-[#ddd7ca] bg-[#fffcf6] p-2 text-xs">
            <div className="flex items-center justify-between text-[#3e3a35]">
              <span className="font-semibold">{event.type}</span>
              <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
            </div>
            <p className="mt-1 text-[#8a867d]">{isChinese ? "发送者" : "sender"}: {event.sender}</p>
            <p className="mt-1 text-[#8a867d]">{isChinese ? "接收者" : "receiver"}: {event.receiver ?? (isChinese ? "广播" : "broadcast")}</p>
            {renderPayloadPreview(event) ? (
              <p className="mt-1 text-[#6b6860]">{renderPayloadPreview(event)}</p>
            ) : null}
            <details className="mt-2 rounded-lg border border-[#ddd7ca] bg-[#f7f2e8] p-2">
              <summary className="cursor-pointer text-[#3e3a35]">{isChinese ? "查看 payload" : "Inspect payload"}</summary>
              <pre className="mt-2 overflow-auto text-[11px] text-[#6b6860]">{JSON.stringify(event.payload, null, 2)}</pre>
              <p className="mt-2 text-[#8a867d]">metadata</p>
              <pre className="mt-1 overflow-auto text-[11px] text-[#8a867d]">{JSON.stringify(event.metadata, null, 2)}</pre>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

