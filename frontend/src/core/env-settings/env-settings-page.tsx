"use client";

import { EyeIcon, EyeOffIcon, KeyIcon, Loader2Icon, ShieldCheckIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SettingsSection } from "@/components/workspace/settings/settings-section";
import {
  useEnvSettings,
  useUpdateEnvSetting,
  useVerifyDeepseekKey,
} from "./hooks";

export function EnvSettingsPage() {
  const { settings, isLoading, error } = useEnvSettings();
  const updateMutation = useUpdateEnvSetting();
  const verifyMutation = useVerifyDeepseekKey();
  const [apiKey, setApiKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const handleSave = async () => {
    if (!apiKey.trim()) return;
    setStatusMessage(null);
    try {
      const result = await updateMutation.mutateAsync(apiKey.trim());
      setApiKey("");
      setStatusMessage({ type: "success", text: result.message });
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err instanceof Error ? err.message : "保存失败",
      });
    }
  };

  const handleVerify = async () => {
    setStatusMessage(null);
    try {
      const result = await verifyMutation.mutateAsync();
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
  };

  return (
    <SettingsSection
      title={
        <div className="flex items-center gap-2">
          <KeyIcon className="size-5" />
          <span>API Keys 配置</span>
        </div>
      }
      description="管理 AI 模型 API Key。修改后保存即写入 .env 文件并刷新运行时环境变量。"
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
          <div className="flex items-start gap-3">
            <ShieldCheckIcon className="text-muted-foreground mt-1 size-5 shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="text-sm font-medium">DeepSeek API Key</div>
              {settings?.DEEPSEEK_API_KEY?.exists && (
                <div className="text-muted-foreground text-xs">
                  当前密钥:{" "}
                  <code className="bg-muted rounded px-1 py-0.5">
                    {settings.DEEPSEEK_API_KEY.masked_value || "****"}
                  </code>
                </div>
              )}
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Input
                    type={showKey ? "text" : "password"}
                    placeholder={
                      settings?.DEEPSEEK_API_KEY?.exists
                        ? "输入新 Key 替换现有密钥"
                        : "输入 DeepSeek API Key (sk-...)"
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
              {statusMessage && (
                <div
                  className={`text-sm ${
                    statusMessage.type === "success"
                      ? "text-green-600 dark:text-green-400"
                      : "text-destructive"
                  }`}
                >
                  {statusMessage.text}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </SettingsSection>
  );
}
