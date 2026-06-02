# 输入建议

## 说明

通过注册表模式实现输入建议按钮的自定义系统。这些按钮显示在聊天输入框上方，用户点击后自动填入提示词模板，用于替代 DeerFlow 内置的"小惊喜/写作/研究"等快捷按钮。

## 目录结构

```
input-suggestions/
├── config.ts    # 预注册的输入建议按钮配置
└── registry.ts  # 注册表系统（核心）
```

## 核心文件说明

### registry.ts

注册表系统，提供三个核心 API：

| 函数 | 说明 |
|------|------|
| `registerInputSuggestion(s)` | 注册一个输入建议项，相同 id 重复注册自动忽略 |
| `getInputSuggestions()` | 获取当前所有注册的建议项的副本 |
| `clearInputSuggestions()` | 清空所有注册项（用于测试或重置） |

`InputSuggestion` 类型定义：

```typescript
interface InputSuggestion {
  id: string;          // 唯一标识符
  label: string;       // 按钮显示文本
  prompt: string;      // 点击后填入输入框的提示词模板
  icon: LucideIcon;    // 按钮图标
  group: "main" | "create";  // 分组：主功能区 / 创作区
}
```

### config.ts

预注册 7 个输入建议按钮，分为两组：

**main 组（主功能区）：**

| ID | 标签 | 提示词模板 | 图标 |
|----|------|-----------|------|
| product-consult | 产品咨询 | 咨询关于ADS桌面云的[具体问题] | MonitorIcon |
| tech-support | 技术支持 | 排查[具体技术问题]的原因和解决方案 | BugIcon |
| deployment | 关联模板 | 使用终端关联模板 skill，处理[关联场景]的终端配置 | GitMergeIcon |

**create 组（创作区）：**

| ID | 标签 | 提示词模板 | 图标 |
|----|------|-----------|------|
| ops-report | 运维报告 | 生成关于[主题]的系统运维分析报告 | FileTextIcon |
| config-script | 配置脚本 | 生成[场景]的ADS批量配置脚本 | FileCodeIcon |
| knowledge-search | 知识检索 | 从知识库检索[主题]的相关资料并总结 | SearchIcon |
| data-analysis | 数据分析 | 分析[数据文件/主题]并生成可视化图表 | BarChart3Icon |

每个建议项的 `prompt` 字段使用 `[占位符]` 标记用户需要替换的内容，引导用户填写具体需求。

## 使用方式

要添加自定义输入建议，在项目任意入口处调用：

```typescript
import { registerInputSuggestion } from "./registry";
import { SmileIcon } from "lucide-react";

registerInputSuggestion({
  id: "my-suggestion",
  label: "我的建议",
  prompt: "帮我做[某件事]",
  icon: SmileIcon,
  group: "main",
});
```

通过 `getInputSuggestions()` 获取注册列表供 UI 渲染。

## 依赖

- lucide-react（图标组件）
