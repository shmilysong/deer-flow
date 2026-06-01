import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type {
  EnvSettingsResponse,
  EnvSettingsUpdateRequest,
  EnvSettingsUpdateResponse,
  VerifyResponse,
  DeleteResponse,
} from "./types";

export async function loadEnvSettings(): Promise<EnvSettingsResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings`);
  return response.json() as Promise<EnvSettingsResponse>;
}

export async function updateEnvSetting(
  data: EnvSettingsUpdateRequest,
): Promise<EnvSettingsUpdateResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/env-settings`, {
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

export async function deleteEnvSetting(
  provider: string,
): Promise<DeleteResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/${encodeURIComponent(provider)}`,
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
): Promise<VerifyResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/${encodeURIComponent(provider)}/verify`,
    { method: "POST" },
  );
  return response.json() as Promise<VerifyResponse>;
}
