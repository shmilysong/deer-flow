"use client";

import { PanelLeftOpenIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSidebar } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

export function MobileSidebarTrigger() {
  const { isMobile, openMobile, toggleSidebar } = useSidebar();

  if (!isMobile || openMobile) return null;

  return (
    <Button
      variant="ghost"
      size="icon"
      className={cn(
        "fixed top-3 left-3 z-50",
        "bg-background/80 backdrop-blur-sm",
        "rounded-lg size-8",
        "hover:bg-background/95",
        "transition-all duration-200",
      )}
      onClick={toggleSidebar}
      aria-label="Open sidebar"
    >
      <PanelLeftOpenIcon className="size-4" />
    </Button>
  );
}
