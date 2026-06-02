import type { LucideIcon } from "lucide-react";

export interface InputSuggestion {
  id: string;
  label: string;
  prompt: string;
  icon: LucideIcon;
  group: "main" | "create";
}

const _suggestions: InputSuggestion[] = [];

export function registerInputSuggestion(s: InputSuggestion): void {
  if (_suggestions.some((e) => e.id === s.id)) return;
  _suggestions.push(s);
}

export function getInputSuggestions(): InputSuggestion[] {
  return [..._suggestions];
}

export function clearInputSuggestions(): void {
  _suggestions.length = 0;
}
