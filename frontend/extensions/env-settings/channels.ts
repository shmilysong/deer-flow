/**
 * @deprecated Channel metadata is now sourced from the upstream `/api/channels/*`
 * endpoints via `adapters/channel-adapter.ts`. This file is kept as a reference
 * for the four managed channel IDs and their mapping.
 *
 * Do NOT import `CHANNELS` or `getChannelMeta` in new code — use the adapter
 * which provides credential fields dynamically from the server response.
 */
export interface CredentialField {
  key: string;
  label: string;
}

export interface ChannelMeta {
  id: string;
  name: string;
  envPrefix: string;
  credentialFields: CredentialField[];
}

export const CHANNELS: ChannelMeta[] = [
  {
    id: "wecom",
    name: "企业微信",
    envPrefix: "WECOM",
    credentialFields: [
      { key: "bot_id", label: "Bot ID" },
      { key: "bot_secret", label: "Bot Secret" },
    ],
  },
  {
    id: "feishu",
    name: "飞书",
    envPrefix: "FEISHU",
    credentialFields: [
      { key: "app_id", label: "App ID" },
      { key: "app_secret", label: "App Secret" },
    ],
  },
  {
    id: "dingtalk",
    name: "钉钉",
    envPrefix: "DINGTALK",
    credentialFields: [
      { key: "client_id", label: "Client ID" },
      { key: "client_secret", label: "Client Secret" },
    ],
  },
  {
    id: "wechat",
    name: "微信（个人）",
    envPrefix: "WECHAT",
    credentialFields: [
      { key: "bot_token", label: "Bot Token" },
    ],
  },
];

export function getChannelMeta(id: string): ChannelMeta | undefined {
  return CHANNELS.find((c) => c.id === id);
}
