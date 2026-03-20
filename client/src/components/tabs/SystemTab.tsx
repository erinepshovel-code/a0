import { Settings } from "lucide-react";

export function SystemTab() {
  return (
    <div className="h-full w-full overflow-y-auto overflow-x-hidden px-3 py-3">
      <div className="flex items-center gap-2 text-muted-foreground text-sm">
        <Settings className="w-4 h-4" />
        <span>System configuration</span>
      </div>
    </div>
  );
}
