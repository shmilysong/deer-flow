/**
 * Channel Adapter — bridges the env-settings extension to the upstream
 * `/api/channels/*` endpoints (channel_connections).
 *
 * Responsibilities:
 *   - Map ChannelProvider → extension's AdaptedChannelInfo
 *   - Filter to the 4 channels the extension manages
 *   - Provide save/delete/verify with the same contract the hooks expect
 *
 * This is the ONLY integration point with upstream API types.
 * If upstream response shapes change, only this file needs updating.
 */
import {
  configureChannelProvider,
  disconnectChannelProvider,
  listChannelConnections,
  listChannelProviders,
} from "@/core/channels/api";
import type { ChannelProvider, ChannelRuntimeConfigValues } from "@/core/channels/types";

// ── Types ────────────────────────────────────────────────────────────────────

/** Mirrors the extension's ChannelInfo but sourced from upstream. */
export interface AdaptedChannelInfo {
  id: string;
  name: string;
  enabled: boolean;
  running: boolean;
  configured: boolean;
  connectionStatus: string;
  /** Masked credential values (upstream returns asterisks for passwords). */
  credentials: Record<string, string>;
  /** Form fields definition sourced from upstream credential_fields. */
  credentialFields: Array<{ key: string; label: string }>;
  /** Error reason when the provider is unavailable. */
  error: string;
}

/** Mirror of the old ChannelSettingsResponse for drop-in compat. */
export interface AdaptedChannelSettingsResponse {
  channels: Record<string, AdaptedChannelInfo>;
}

/** Same shape as the old ChannelUpdateRequest. */
export interface ChannelUpdateInput {
  channel: string;
  credentials: Record<string, string>;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** The four channel types managed by this extension, with fallback display names. */
const MANAGED_CHANNELS = new Set(["wecom", "feishu", "dingtalk", "wechat"]);
const CHANNEL_NAMES: Record<string, string> = {
  wecom: "企业微信",
  feishu: "飞书",
  dingtalk: "钉钉",
  wechat: "微信（个人）",
};

/** Fallback credential fields for each channel, used when upstream has no data. */
const FALLBACK_CREDENTIAL_FIELDS: Record<string, Array<{ key: string; label: string }>> = {
  wecom: [
    { key: "bot_id", label: "Bot ID" },
    { key: "bot_secret", label: "Bot Secret" },
  ],
  feishu: [
    { key: "app_id", label: "App ID" },
    { key: "app_secret", label: "App Secret" },
  ],
  dingtalk: [
    { key: "client_id", label: "Client ID" },
    { key: "client_secret", label: "Client Secret" },
  ],
  wechat: [
    { key: "bot_token", label: "Bot Token" },
  ],
};

function mapProvider(
  p: ChannelProvider,
  connectionStatus: string,
): AdaptedChannelInfo {
  return {
    id: p.provider,
    name: p.display_name,
    enabled: p.enabled,
    running: p.configured && connectionStatus === "connected" && !p.unavailable_reason,
    configured: p.configured,
    connectionStatus,
    credentials: (p.credential_values as Record<string, string>) ?? {},
    credentialFields: (p.credential_fields ?? []).map((f) => ({
      key: f.name,
      label: f.label,
    })),
    error: p.unavailable_reason ?? "",
  };
}

function buildConnectionStatusMap(
  connections: Array<{ provider: string; status: string }>,
): Map<string, string> {
  const map = new Map<string, string>();
  // Keep newest connected status per provider.
  for (const c of connections) {
    const existing = map.get(c.provider);
    if (!existing || c.status === "connected") {
      map.set(c.provider, c.status);
    }
  }
  return map;
}

// ── Adapter functions ────────────────────────────────────────────────────────

/**
 * Load channel settings from upstream `/api/channels/providers`.
 * Filters to the 4 channels managed by this extension.
 */
export async function listChannels(): Promise<AdaptedChannelSettingsResponse> {
  const [providersResult, connections] = await Promise.all([
    listChannelProviders(),
    listChannelConnections(),
  ]);

  const connMap = buildConnectionStatusMap(connections);

  const channels: Record<string, AdaptedChannelInfo> = {};

  // Always populate with all 4 managed channels so the UI has something to show
  // even when upstream returns no configured providers.
  for (const id of MANAGED_CHANNELS) {
    channels[id] = {
      id,
      name: CHANNEL_NAMES[id] ?? id,
      enabled: false,
      running: false,
      configured: false,
      connectionStatus: "",
      credentials: {},
      credentialFields: FALLBACK_CREDENTIAL_FIELDS[id] ?? [],
      error: "",
    };
  }

  // Overlay upstream data on top of the fallback entries.
  for (const p of providersResult.providers) {
    if (!MANAGED_CHANNELS.has(p.provider)) {
      continue;
    }
    const status = connMap.get(p.provider) ?? p.connection_status;
    channels[p.provider] = mapProvider(p, status);
  }
  return { channels };
}

/**
 * Save channel credentials via upstream `/api/channels/{provider}/runtime-config`.
 */
export async function saveChannel(
  input: ChannelUpdateInput,
): Promise<{ success: boolean; message: string }> {
  // Normalize credentials: skip entries where value is the masked placeholder.
  const values: ChannelRuntimeConfigValues = {};
  for (const [key, val] of Object.entries(input.credentials)) {
    if (val && val !== "********") {
      values[key] = val;
    }
  }
  try {
    const result = await configureChannelProvider(
      input.channel as Parameters<typeof configureChannelProvider>[0],
      values,
    );
    const connected = result.connection_status === "connected";
    return {
      success: connected,
      message: connected
        ? `${result.display_name} 配置成功并已连接`
        : `${result.display_name} 配置已保存，等待连接`,
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : "保存失败";
    return { success: false, message: msg };
  }
}

/**
 * Delete channel credentials via upstream `/api/channels/{provider}/runtime-config`.
 */
export async function deleteChannel(
  channel: string,
): Promise<{ success: boolean; message: string }> {
  try {
    await disconnectChannelProvider(
      channel as Parameters<typeof disconnectChannelProvider>[0],
    );
    return { success: true, message: "已清除渠道配置" };
  } catch (err) {
    const msg = err instanceof Error ? err.message : "清除失败";
    return { success: false, message: msg };
  }
}

/**
 * Verify channel connectivity.
 *
 * - Without credentials: check existing connection_status.
 * - With credentials: temporarily save, check result, then roll back
 *   to avoid persisting test-only values.
 */
export async function verifyChannel(
  channel: string,
  credentials?: Record<string, string>,
): Promise<{ valid: boolean; message: string }> {
  if (!credentials || Object.keys(credentials).length === 0) {
    // No new credentials — just query current status via providers.
    const result = await listChannels();
    const info = result.channels[channel];
    if (!info) {
      return { valid: false, message: "未知渠道" };
    }
    return {
      valid: info.running,
      message: info.running ? `${info.name} 连接正常` : `${info.name} 未连接`,
    };
  }

  // Temp save → check → roll back.
  try {
    const result = await configureChannelProvider(
      channel as Parameters<typeof configureChannelProvider>[0],
      credentials as ChannelRuntimeConfigValues,
    );
    const connected = result.connection_status === "connected";
    // Roll back: clear the temp credentials we just wrote.
    await disconnectChannelProvider(
      channel as Parameters<typeof disconnectChannelProvider>[0],
    ).catch(() => {
      /* swallow rollback error — user still saw the result */
    });
    return {
      valid: connected,
      message: connected
        ? `验证通过: ${result.display_name} 连接正常`
        : `验证失败: ${result.display_name} 无法连接`,
    };
  } catch (err) {
    return {
      valid: false,
      message: err instanceof Error ? err.message : "验证失败",
    };
  }
}
