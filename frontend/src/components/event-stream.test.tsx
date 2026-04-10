import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { BusMessage } from "@/lib/api/types";
import { LanguageProvider } from "@/lib/i18n/language-context";

import { EventStream } from "./event-stream";

const baseEvents: BusMessage[] = [
  {
    message_id: "msg_1",
    type: "TaskRequest",
    sender: "api_gateway",
    receiver: null,
    task_id: "task_1",
    payload: { objective: "first" },
    metadata: {},
    timestamp: "2026-04-07T10:00:00Z"
  },
  {
    message_id: "msg_2",
    type: "TaskResult",
    sender: "agent_writer",
    receiver: null,
    task_id: "task_1",
    payload: { summary: "second" },
    metadata: {},
    timestamp: "2026-04-07T10:00:01Z"
  }
];

describe("EventStream replay", () => {
  it("toggles replay mode and shows replay controls", () => {
    render(
      <LanguageProvider>
        <EventStream
          events={baseEvents}
          error={null}
          connectionState="connected"
          selectedTypes={[]}
          from=""
          to=""
          onToggleType={vi.fn()}
          onFromChange={vi.fn()}
          onToChange={vi.fn()}
          onRefresh={vi.fn()}
        />
      </LanguageProvider>
    );

    fireEvent.click(screen.getByTestId("event-replay-toggle"));

    expect(screen.getByTestId("event-replay-play")).toBeInTheDocument();
    expect(screen.getByTestId("event-replay-seek")).toBeInTheDocument();
  });

  it("renders newest event first when incoming list is unsorted", () => {
    const unsorted: BusMessage[] = [
      {
        ...baseEvents[1],
        timestamp: "2026-04-07T10:00:01Z"
      },
      {
        ...baseEvents[0],
        timestamp: "2026-04-07T10:00:00Z"
      }
    ];

    render(
      <LanguageProvider>
        <EventStream
          events={unsorted}
          error={null}
          connectionState="connected"
          selectedTypes={[]}
          from=""
          to=""
          onToggleType={vi.fn()}
          onFromChange={vi.fn()}
          onToChange={vi.fn()}
          onRefresh={vi.fn()}
        />
      </LanguageProvider>
    );

    const items = screen.getByTestId("event-stream-list").querySelectorAll("li");
    expect(items[0].textContent).toContain("TaskResult");
    expect(items[1].textContent).toContain("TaskRequest");
  });
});

