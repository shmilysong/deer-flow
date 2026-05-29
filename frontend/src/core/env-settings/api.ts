import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import type {
  EnvSettingsResponse,
  EnvSettingsUpdateRequest,
  EnvSettingsUpdateResponse,
  VerifyResponse,
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
    throw new Error(errorData.detail || "Failed to save API Key");
  }
  return response.json() as Promise<EnvSettingsUpdateResponse>;
}

export async function verifyDeepseekKey(): Promise<VerifyResponse> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/env-settings/deepseek/verify`,
    { method: "POST" },
  );
  return response.json() as Promise<VerifyResponse>;
}
