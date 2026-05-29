import type { LucideIcon } from "lucide-react";

export interface SettingsExtension {
  id: string;
  label: string;
  icon: LucideIcon;
  component: React.ComponentType;
}

const _extensions: SettingsExtension[] = [];

export function registerSettingsExtension(ext: SettingsExtension): void {
  if (_extensions.some((e) => e.id === ext.id)) return;
  _extensions.push(ext);
}

export function getSettingsExtensions(): SettingsExtension[] {
  return [..._extensions];
}

export function clearSettingsExtensions(): void {
  _extensions.length = 0;
}
