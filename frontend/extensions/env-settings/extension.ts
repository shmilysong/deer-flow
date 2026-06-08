import { KeyIcon, MessageSquareIcon } from "lucide-react";

import { registerSettingsExtension } from "@/core/settings-extensions";

import { ProviderSettingsPage } from "./provider-settings-page";
import { ChannelSettingsPage } from "./channel-settings-page";

registerSettingsExtension({
  id: "api",
  label: "API Keys",
  icon: KeyIcon,
  component: ProviderSettingsPage,
});

registerSettingsExtension({
  id: "channels",
  label: "渠道配置",
  icon: MessageSquareIcon,
  component: ChannelSettingsPage,
});
