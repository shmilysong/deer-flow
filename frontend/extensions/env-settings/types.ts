export interface ProviderInfo {
  id: string;
  name: string;
  default_base_url: string;
  default_models: string[];
  key_exists: boolean;
  key_masked: string;
  base_url: string;
  model: string;
}

export interface ProviderSettingsResponse {
  providers: Record<string, ProviderInfo>;
}

export interface ProviderSettingsUpdateRequest {
  provider: string;
  api_key: string;
  base_url?: string;
  model?: string;
}

export interface EnvSettingsUpdateResponse {
  success: boolean;
  message: string;
}

export interface VerifyResponse {
  valid: boolean;
  message: string;
}

export interface DeleteResponse {
  success: boolean;
  message: string;
}

export interface ChannelInfo {
  id: string;
  name: string;
  enabled: boolean;
  running: boolean;
  credentials: Record<string, string>;
  error: string;
}

export interface ChannelSettingsResponse {
  channels: Record<string, ChannelInfo>;
}

/** Input shape for saveChannel mutation (matches adapter contract). */
export interface ChannelUpdateInput {
  channel: string;
  credentials: Record<string, string>;
}
