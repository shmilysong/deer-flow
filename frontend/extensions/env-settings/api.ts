import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  ProviderSettingsResponse,
  ProviderSettingsUpdateRequest,
  EnvSettingsUpdateResponse,
  VerifyResponse,
  DeleteResponse,
  ChannelSettingsResponse,
  ChannelUpdateRequest,
} from "./types";

export async function loadProviderSettings(): Promise<ProviderSettingsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings/providers`);
  return response.json() as Promise<ProviderSettingsResponse>;
}

export async function updateProviderSetting(
  data: ProviderSettingsUpdateRequest,
): Promise<EnvSettingsUpdateResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings/providers`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail ?? "Failed to save API Key");
  }
  return response.json() as Promise<EnvSettingsUpdateResponse>;
}

export async function deleteProviderSetting(
  provider: string,
): Promise<DeleteResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/providers/${encodeURIComponent(provider)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail ?? "Failed to delete API Key");
  }
  return response.json() as Promise<DeleteResponse>;
}

export async function verifyProviderKey(
  provider: string,
  apiKey?: string,
  baseUrl?: string,
): Promise<VerifyResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/providers/${encodeURIComponent(provider)}/verify`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey, base_url: baseUrl }),
    },
  );
  return response.json() as Promise<VerifyResponse>;
}

export async function loadChannelSettings(): Promise<ChannelSettingsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings/channels`);
  return response.json() as Promise<ChannelSettingsResponse>;
}

export async function updateChannel(
  data: ChannelUpdateRequest,
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings/channels`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail ?? "保存失败");
  }
  return response.json();
}

export async function deleteChannel(
  channel: string,
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/channels/${encodeURIComponent(channel)}`,
    { method: "DELETE" },
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail ?? "清除失败");
  }
  return response.json();
}

export async function verifyChannel(
  channel: string,
  credentials?: Record<string, string>,
): Promise<{ valid: boolean; message: string }> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/channels/${encodeURIComponent(channel)}/verify`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credentials }),
    },
  );
  return response.json();
}
