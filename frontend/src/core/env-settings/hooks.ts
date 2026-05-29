import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { loadEnvSettings, updateEnvSetting, verifyDeepseekKey } from "./api";

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
    mutationFn: (apiKey: string) => updateEnvSetting({ DEEPSEEK_API_KEY: apiKey }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["envSettings"] });
    },
  });
}

export function useVerifyDeepseekKey() {
  return useMutation({
    mutationFn: () => verifyDeepseekKey(),
  });
}
