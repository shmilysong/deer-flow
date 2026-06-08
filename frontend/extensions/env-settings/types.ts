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
  bot_id_exists: boolean;
  bot_id_masked: string;
  bot_secret_exists: boolean;
  error: string;
}

export interface ChannelSettingsResponse {
  channels: Record<string, ChannelInfo>;
}

export interface ChannelUpdateRequest {
  channel: string;
  bot_id: string;
  bot_secret: string;
}
