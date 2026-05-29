export interface EnvSettingValue {
  exists: boolean;
  masked_value: string;
  configured: boolean;
}

export interface EnvSettingsResponse {
  DEEPSEEK_API_KEY: EnvSettingValue;
}

export interface EnvSettingsUpdateRequest {
  DEEPSEEK_API_KEY: string;
}

export interface EnvSettingsUpdateResponse {
  success: boolean;
  message: string;
}

export interface VerifyResponse {
  valid: boolean;
  message: string;
}
