export interface ProviderMeta {
  id: string;
  name: string;
  envPrefix: string;
  defaultBaseUrl: string;
  defaultModels: string[];
}

export const PROVIDERS: ProviderMeta[] = [
  {
    id: "deepseek",
    name: "DeepSeek",
    envPrefix: "DEEPSEEK",
    defaultBaseUrl: "https://api.deepseek.com",
    defaultModels: ["deepseek-chat", "deepseek-reasoner"],
  },
  {
    id: "moonshot",
    name: "Kimi",
    envPrefix: "MOONSHOT",
    defaultBaseUrl: "https://api.moonshot.cn/v1",
    defaultModels: ["kimi-k2.5", "kimi-k2.5-thinking"],
  },
  {
    id: "volcengine",
    name: "Doubao",
    envPrefix: "VOLCENGINE",
    defaultBaseUrl: "https://ark.cn-beijing.volces.com/api/v3",
    defaultModels: ["doubao-seed-1-8-251228", "doubao-pro-32k-250315"],
  },
  {
    id: "dashscope",
    name: "Qwen",
    envPrefix: "DASHSCOPE",
    defaultBaseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    defaultModels: ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
  },
  {
    id: "minimax",
    name: "MiniMax",
    envPrefix: "MINIMAX",
    defaultBaseUrl: "https://api.minimax.io/v1",
    defaultModels: ["MiniMax-M2.5", "MiniMax-M2.5-highspeed", "MiniMax-M2.7"],
  },
  {
    id: "zhipuai",
    name: "GLM",
    envPrefix: "ZHIPUAI",
    defaultBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    defaultModels: ["glm-4-plus", "glm-4-air", "glm-4-flash"],
  },
  {
    id: "siliconflow",
    name: "硅基流动",
    envPrefix: "SILICONFLOW",
    defaultBaseUrl: "https://api.siliconflow.cn/v1",
    defaultModels: [
      "Qwen/Qwen2.5-72B-Instruct-128K",
      "deepseek-ai/DeepSeek-V3",
      "deepseek-ai/DeepSeek-R1",
    ],
  },
];

export function getProviderMeta(id: string): ProviderMeta | undefined {
  return PROVIDERS.find((p) => p.id === id);
}
