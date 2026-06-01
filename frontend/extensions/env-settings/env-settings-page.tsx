"use client";

import {
  AlertCircleIcon,
  CheckCircle2Icon,
  EyeIcon,
  EyeOffIcon,
  KeyIcon,
  Loader2Icon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SettingsSection } from "@/components/workspace/settings/settings-section";

import {
  useEnvSettings,
  useUpdateEnvSetting,
  useDeleteEnvSetting,
  useVerifyProviderKey,
} from "./hooks";
import { PROVIDERS, getProviderMeta } from "./providers";
import type { ProviderInfo } from "./types";

export function EnvSettingsPage() {
  const { settings, isLoading, error } = useEnvSettings();
  const updateMutation = useUpdateEnvSetting();
  const deleteMutation = useDeleteEnvSetting();
  const verifyMutation = useVerifyProviderKey();

  const [selectedProviderId, setSelectedProviderId] = useState(PROVIDERS[0]?.id ?? "");
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [model, setModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const providerMeta = useMemo(
    () => getProviderMeta(selectedProviderId),
    [selectedProviderId],
  );

  const providerInfo: ProviderInfo | undefined = useMemo(
    () => settings?.providers?.[selectedProviderId],
    [settings, selectedProviderId],
  );

  const handleProviderChange = useCallback((value: string) => {
    setSelectedProviderId(value);
    setApiKey("");
    setCustomModel("");
    setUseCustomModel(false);
    setBaseUrl("");
    setStatusMessage(null);
  }, []);

  const handleSave = useCallback(async () => {
    if (!apiKey.trim()) return;
    setStatusMessage(null);
    try {
      const result = await updateMutation.mutateAsync({
        provider: selectedProviderId,
        api_key: apiKey.trim(),
        base_url: baseUrl || undefined,
        model: useCustomModel ? customModel.trim() : (model || undefined),
      });
      setApiKey("");
      setStatusMessage({ type: "success", text: result.message });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "保存失败",
      });
    }
  }, [apiKey, baseUrl, customModel, model, selectedProviderId, updateMutation, useCustomModel]);

  const handleVerify = useCallback(async () => {
    setStatusMessage(null);
    try {
      const result = await verifyMutation.mutateAsync(selectedProviderId);
      setStatusMessage({
        type: result.valid ? "success" : "error",
        text: result.message,
      });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "验证失败",
      });
    }
  }, [selectedProviderId, verifyMutation]);

  const handleDelete = useCallback(async () => {
    setDeleteConfirmOpen(false);
    setStatusMessage(null);
    try {
      const result = await deleteMutation.mutateAsync(selectedProviderId);
      setApiKey("");
      setModel("");
      setCustomModel("");
      setBaseUrl("");
      setStatusMessage({ type: "success", text: result.message });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "清除失败",
      });
    }
  }, [selectedProviderId, deleteMutation]);

  const providerModels = useMemo(
    () => providerMeta?.defaultModels ?? [],
    [providerMeta],
  );

  return (
    <>
      <SettingsSection
        title={
          <div className="flex items-center gap-2">
            <KeyIcon className="size-5" />
            <span>API Keys 配置</span>
          </div>
        }
        description="管理 AI 模型 API Key。此处仅管理凭据，模型注册请在 config.yaml 中配置。"
      >
        {isLoading ? (
          <div className="text-muted-foreground flex items-center gap-2 py-8 text-sm">
            <Loader2Icon className="size-4 animate-spin" />
            加载中...
          </div>
        ) : error ? (
          <div className="text-destructive py-4 text-sm">
            加载失败: {error.message}
          </div>
        ) : (
          <div className="space-y-5 py-2">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium whitespace-nowrap">选择服务商</span>
              <Select
                value={selectedProviderId}
                onValueChange={handleProviderChange}
              >
                <SelectTrigger className="w-full max-w-xs">
                  <SelectValue placeholder="选择服务商" />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {providerMeta && (
              <div className="rounded-lg border p-4 space-y-4">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span>当前厂商: {providerMeta.name}</span>
                  {providerInfo?.key_exists && (
                    <span className="text-muted-foreground text-xs font-normal">
                      (已配置)
                    </span>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm">API 密钥 *</label>
                  {providerInfo?.key_exists && (
                    <div className="text-muted-foreground text-xs mb-1">
                      当前:{" "}
                      <code className="bg-muted rounded px-1 py-0.5">
                        {providerInfo.key_masked || "****"}
                      </code>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1 max-w-md">
                      <Input
                        type={showKey ? "text" : "password"}
                        placeholder={
                          providerInfo?.key_exists
                            ? "输入新 Key 替换现有密钥"
                            : `输入 ${providerMeta.name} API Key`
                        }
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        className="pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowKey(!showKey)}
                        className="text-muted-foreground hover:text-foreground absolute right-3 top-1/2 -translate-y-1/2"
                      >
                        {showKey ? (
                          <EyeOffIcon className="size-4" />
                        ) : (
                          <EyeIcon className="size-4" />
                        )}
                      </button>
                    </div>
                    <Button
                      onClick={handleSave}
                      disabled={!apiKey.trim() || updateMutation.isPending}
                    >
                      {updateMutation.isPending && (
                        <Loader2Icon className="mr-1 size-4 animate-spin" />
                      )}
                      保存
                    </Button>
                    <Button
                      variant="outline"
                      onClick={handleVerify}
                      disabled={verifyMutation.isPending}
                    >
                      {verifyMutation.isPending ? (
                        <Loader2Icon className="size-4 animate-spin" />
                      ) : (
                        "验证连通性"
                      )}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm">选择模型</label>
                  {useCustomModel ? (
                    <div className="flex items-center gap-2 max-w-md">
                      <Input
                        placeholder="输入自定义模型名"
                        value={customModel}
                        onChange={(e) => setCustomModel(e.target.value)}
                        className="flex-1"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setUseCustomModel(false);
                          setCustomModel("");
                        }}
                      >
                        取消自定义
                      </Button>
                    </div>
                  ) : (
                    <Select
                      value={model}
                      onValueChange={(v) => {
                        if (v === "__custom__") {
                          setUseCustomModel(true);
                        } else {
                          setModel(v);
                        }
                      }}
                    >
                      <SelectTrigger className="w-full max-w-md">
                        <SelectValue placeholder="选择模型（可选）" />
                      </SelectTrigger>
                      <SelectContent>
                        {providerModels.length === 0 ? (
                          <SelectItem value="__no_models__" disabled>
                            无预置模型，请选择自定义输入
                          </SelectItem>
                        ) : (
                          providerModels.map((m) => (
                            <SelectItem key={m} value={m}>
                              {m}
                            </SelectItem>
                          ))
                        )}
                        <SelectItem value="__custom__">
                          ✏️ 输入自定义模型名...
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm">请求地址 (可选)</label>
                  <div className="text-muted-foreground text-xs">
                    默认: {providerMeta.defaultBaseUrl}
                  </div>
                  <Input
                    placeholder={providerMeta.defaultBaseUrl}
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="max-w-md"
                  />
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setDeleteConfirmOpen(true)}
                    disabled={!providerInfo?.key_exists || deleteMutation.isPending}
                  >
                    {deleteMutation.isPending ? (
                      <Loader2Icon className="size-4 animate-spin" />
                    ) : (
                      <Trash2Icon className="mr-1 size-4" />
                    )}
                    清除 Key
                  </Button>
                </div>

                {statusMessage && (
                  <div
                    className={`flex items-center gap-1.5 text-sm ${
                      statusMessage.type === "success"
                        ? "text-green-600 dark:text-green-400"
                        : "text-destructive"
                    }`}
                  >
                    {statusMessage.type === "success" ? (
                      <CheckCircle2Icon className="size-4" />
                    ) : (
                      <AlertCircleIcon className="size-4" />
                    )}
                    {statusMessage.text}
                  </div>
                )}
              </div>
            )}

            {!providerMeta && (
              <div className="text-muted-foreground py-4 text-sm">
                暂无可用厂商
              </div>
            )}
          </div>
        )}
      </SettingsSection>

      {deleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-background rounded-lg border p-6 shadow-lg max-w-sm w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">确认清除</h3>
              <button
                type="button"
                onClick={() => setDeleteConfirmOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <XIcon className="size-4" />
              </button>
            </div>
            <p className="text-muted-foreground text-sm mb-6">
              确定清除 {providerMeta?.name ?? "该厂商"} 的全部配置？操作不可撤销。
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>
                取消
              </Button>
              <Button variant="destructive" onClick={handleDelete}>
                确认清除
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
