import { KeyIcon } from "lucide-react";
import { registerSettingsExtension } from "@/core/settings-extensions";

import { EnvSettingsPage } from "./env-settings-page";

registerSettingsExtension({
  id: "api",
  label: "API Keys",
  icon: KeyIcon,
  component: EnvSettingsPage,
});
