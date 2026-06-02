import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  loadEnvSettings,
  updateEnvSetting,
  deleteEnvSetting,
  verifyProviderKey,
} from "./api";
import type { EnvSettingsUpdateRequest } from "./types";

export function useEnvSettings() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["envSettings"],
    queryFn: () => loadEnvSettings(),
  });
  return { settings: data, isLoading, error };
}

export function useUpdateEnvSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: EnvSettingsUpdateRequest) => updateEnvSetting(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["envSettings"] });
    },
  });
}

export function useDeleteEnvSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) => deleteEnvSetting(provider),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["envSettings"] });
    },
  });
}

export function useVerifyProviderKey() {
  return useMutation({
    mutationFn: ({ provider, apiKey, baseUrl }: { provider: string; apiKey?: string; baseUrl?: string }) =>
      verifyProviderKey(provider, apiKey, baseUrl),
  });
}
