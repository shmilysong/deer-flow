import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  loadProviderSettings,
  updateProviderSetting,
  deleteProviderSetting,
  verifyProviderKey,
  loadChannelSettings,
  updateChannel,
  deleteChannel,
  verifyChannel,
} from "./api";
import type { ProviderSettingsUpdateRequest, ChannelUpdateRequest } from "./types";

export function useProviderSettings() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["providerSettings"],
    queryFn: () => loadProviderSettings(),
  });
  return { settings: data, isLoading, error };
}

export function useUpdateProviderSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ProviderSettingsUpdateRequest) => updateProviderSetting(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["providerSettings"] });
    },
  });
}

export function useDeleteProviderSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) => deleteProviderSetting(provider),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["providerSettings"] });
    },
  });
}

export function useVerifyProviderKey() {
  return useMutation({
    mutationFn: ({ provider, apiKey, baseUrl }: { provider: string; apiKey?: string; baseUrl?: string }) =>
      verifyProviderKey(provider, apiKey, baseUrl),
  });
}

export function useChannelSettings() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["channelSettings"],
    queryFn: () => loadChannelSettings(),
  });
  return { settings: data, isLoading, error };
}

export function useUpdateChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChannelUpdateRequest) => updateChannel(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["channelSettings"] });
    },
  });
}

export function useDeleteChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (channel: string) => deleteChannel(channel),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["channelSettings"] });
    },
  });
}

export function useVerifyChannel() {
  return useMutation({
    mutationFn: ({ channel, credentials }: { channel: string; credentials?: Record<string, string> }) =>
      verifyChannel(channel, credentials),
  });
}
