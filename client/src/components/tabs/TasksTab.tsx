import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { Check, ChevronDown, ChevronRight, Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";

type Goal = { id: string; text: string; done: boolean };
type Task = { id: string; title: string; status: "active" | "completed"; goals: Goal[] };

export function TasksTab() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set());
  const [newGoalInputs, setNewGoalInputs] = useState<Record<string, string>>({});

  const { data: tasks = [], isLoading } = useQuery<Task[]>({
    queryKey: ["/api/v1/tasks"],
    staleTime: 5000,
  });

  const addTaskMutation = useMutation({
    mutationFn: (title: string) => apiRequest("POST", "/api/v1/tasks", { title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/tasks"] });
      setNewTaskTitle("");
      toast({ title: "Task added" });
    },
  });

  const updateTaskMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: string; [key: string]: any }) =>
      apiRequest("PATCH", `/api/v1/tasks/${id}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/v1/tasks"] }),
  });

  const deleteTaskMutation = useMutation({
    mutationFn: (id: string) => apiRequest("DELETE", `/api/v1/tasks/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/api/v1/tasks"] });
      toast({ title: "Task removed" });
    },
  });

  function toggleExpand(id: string) {
    setExpandedTasks(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleAddGoal(taskId: string) {
    const text = (newGoalInputs[taskId] || "").trim();
    if (!text) return;
    updateTaskMutation.mutate({ id: taskId, addGoal: text });
    setNewGoalInputs(prev => ({ ...prev, [taskId]: "" }));
  }

  function handleGoalToggle(taskId: string, goalId: string, done: boolean) {
    updateTaskMutation.mutate({ id: taskId, goalId, goalDone: done });
  }

  function handleCompleteTask(taskId: string) {
    updateTaskMutation.mutate({ id: taskId, status: "completed" });
    toast({ title: "Task completed" });
  }

  const activeTasks = tasks.filter(t => t.status === "active");
  const completedTasks = tasks.filter(t => t.status === "completed");

  if (isLoading) return <div className="p-4"><Skeleton className="h-40" /></div>;

  return (
    <div className="h-full w-full overflow-y-auto overflow-x-hidden">
      <div className="p-3 space-y-4">
        <div className="flex items-center gap-2">
          <Input
            value={newTaskTitle}
            onChange={e => setNewTaskTitle(e.target.value)}
            placeholder="New task title…"
            className="h-8 text-xs flex-1"
            data-testid="input-new-task"
            onKeyDown={e => { if (e.key === "Enter" && newTaskTitle.trim()) addTaskMutation.mutate(newTaskTitle.trim()); }}
          />
          <Button
            size="sm"
            className="h-8 text-xs"
            onClick={() => { if (newTaskTitle.trim()) addTaskMutation.mutate(newTaskTitle.trim()); }}
            disabled={addTaskMutation.isPending || !newTaskTitle.trim()}
            data-testid="button-add-task"
          >
            <Plus className="w-3 h-3 mr-1" />
            Add
          </Button>
        </div>

        {activeTasks.length === 0 && completedTasks.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">No tasks yet. Add a task to get started.</p>
        )}

        {activeTasks.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Active</h4>
            {activeTasks.map(task => {
              const isExpanded = expandedTasks.has(task.id);
              const doneCount = task.goals.filter(g => g.done).length;
              return (
                <div key={task.id} className="border border-border rounded-lg overflow-hidden" data-testid={`card-task-${task.id}`}>
                  <div
                    className="flex items-center gap-2 px-2 py-2 cursor-pointer hover:bg-muted/40 transition-colors"
                    onClick={() => toggleExpand(task.id)}
                    data-testid={`task-header-${task.id}`}
                  >
                    {isExpanded
                      ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                      : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />}
                    <span className="text-xs font-medium flex-1 truncate">{task.title}</span>
                    {task.goals.length > 0 && (
                      <span className="text-[10px] text-muted-foreground shrink-0">{doneCount}/{task.goals.length}</span>
                    )}
                    <Badge variant="outline" className="text-[9px] h-4 px-1 shrink-0 text-green-600 border-green-600">active</Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-5 w-5 p-0 shrink-0"
                      onClick={e => { e.stopPropagation(); handleCompleteTask(task.id); }}
                      data-testid={`button-complete-task-${task.id}`}
                      title="Mark complete"
                    >
                      <Check className="w-3 h-3 text-green-500" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-5 w-5 p-0 shrink-0"
                      onClick={e => { e.stopPropagation(); deleteTaskMutation.mutate(task.id); }}
                      data-testid={`button-delete-task-${task.id}`}
                      title="Delete task"
                    >
                      <Trash2 className="w-3 h-3 text-destructive" />
                    </Button>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-border bg-muted/20 px-2 py-2 space-y-1.5">
                      {task.goals.map(goal => (
                        <div key={goal.id} className="flex items-center gap-2" data-testid={`goal-item-${goal.id}`}>
                          <input
                            type="checkbox"
                            checked={goal.done}
                            onChange={e => handleGoalToggle(task.id, goal.id, e.target.checked)}
                            className="rounded w-3.5 h-3.5 cursor-pointer"
                            data-testid={`checkbox-goal-${goal.id}`}
                          />
                          <span className={cn("text-xs flex-1", goal.done && "line-through text-muted-foreground")}>{goal.text}</span>
                        </div>
                      ))}

                      <div className="flex items-center gap-2 pt-1">
                        <Input
                          value={newGoalInputs[task.id] || ""}
                          onChange={e => setNewGoalInputs(prev => ({ ...prev, [task.id]: e.target.value }))}
                          placeholder="Add sub-goal…"
                          className="h-6 text-xs flex-1"
                          data-testid={`input-add-goal-${task.id}`}
                          onKeyDown={e => { if (e.key === "Enter") handleAddGoal(task.id); }}
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-6 text-xs px-2"
                          onClick={() => handleAddGoal(task.id)}
                          disabled={!(newGoalInputs[task.id] || "").trim()}
                          data-testid={`button-add-goal-${task.id}`}
                        >
                          <Plus className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {completedTasks.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Completed ({completedTasks.length})</h4>
            {completedTasks.map(task => (
              <div key={task.id} className="flex items-center gap-2 px-2 py-1.5 rounded border border-border opacity-60" data-testid={`card-task-${task.id}`}>
                <Check className="w-3.5 h-3.5 text-green-500 shrink-0" />
                <span className="text-xs line-through flex-1 truncate">{task.title}</span>
                <Badge variant="secondary" className="text-[9px] h-4 px-1 shrink-0">done</Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-5 w-5 p-0 shrink-0"
                  onClick={() => deleteTaskMutation.mutate(task.id)}
                  data-testid={`button-delete-task-${task.id}`}
                >
                  <Trash2 className="w-3 h-3 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
