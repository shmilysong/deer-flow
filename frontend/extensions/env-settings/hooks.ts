import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  loadProviderSettings,
  updateProviderSetting,
  deleteProviderSetting,
  verifyProviderKey,
} from "./api";
import {
  listChannels,
  saveChannel,
  deleteChannel,
  verifyChannel,
} from "./adapters/channel-adapter";
import type { ProviderSettingsUpdateRequest, ChannelUpdateInput } from "./types";

export const channelProviderQueryKey = ["channelProviders"] as const;
export const channelConnectionsQueryKey = ["channelConnections"] as const;

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
    queryKey: [...channelProviderQueryKey, ...channelConnectionsQueryKey],
    queryFn: () => listChannels(),
  });
  return { settings: data, isLoading, error };
}

export function useUpdateChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChannelUpdateInput) => saveChannel(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: channelProviderQueryKey });
      void queryClient.invalidateQueries({ queryKey: channelConnectionsQueryKey });
    },
  });
}

export function useDeleteChannel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (channel: string) => deleteChannel(channel),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: channelProviderQueryKey });
      void queryClient.invalidateQueries({ queryKey: channelConnectionsQueryKey });
    },
  });
}

export function useVerifyChannel() {
  return useMutation({
    mutationFn: ({ channel, credentials }: { channel: string; credentials?: Record<string, string> }) =>
      verifyChannel(channel, credentials),
  });
}
