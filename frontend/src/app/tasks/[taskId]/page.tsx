import { TaskWorkspace } from "@/components/task-workspace";

export default function TaskDetailRoutePage({
  params
}: {
  params: { taskId: string };
}) {
  return <TaskWorkspace taskId={params.taskId} />;
}

