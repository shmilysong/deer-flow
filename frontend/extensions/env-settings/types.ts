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

export interface EnvSettingsResponse {
  providers: Record<string, ProviderInfo>;
}

export interface EnvSettingsUpdateRequest {
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
