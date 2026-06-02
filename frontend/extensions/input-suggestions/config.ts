import {
  MonitorIcon,
  BugIcon,
  GitMergeIcon,
  FileTextIcon,
  FileCodeIcon,
  SearchIcon,
  BarChart3Icon,
} from "lucide-react";
import { registerInputSuggestion } from "./registry";

registerInputSuggestion({
  id: "product-consult",
  label: "产品咨询",
  prompt: "咨询关于ADS桌面云的[具体问题]",
  icon: MonitorIcon,
  group: "main",
});

registerInputSuggestion({
  id: "tech-support",
  label: "技术支持",
  prompt: "排查[具体技术问题]的原因和解决方案",
  icon: BugIcon,
  group: "main",
});

registerInputSuggestion({
  id: "deployment",
  label: "关联模板",
  prompt: "使用终端关联模板 skill，处理[关联场景]的终端配置",
  icon: GitMergeIcon,
  group: "main",
});

registerInputSuggestion({
  id: "ops-report",
  label: "运维报告",
  prompt: "生成关于[主题]的系统运维分析报告",
  icon: FileTextIcon,
  group: "create",
});

registerInputSuggestion({
  id: "config-script",
  label: "配置脚本",
  prompt: "生成[场景]的ADS批量配置脚本",
  icon: FileCodeIcon,
  group: "create",
});

registerInputSuggestion({
  id: "knowledge-search",
  label: "知识检索",
  prompt: "从知识库检索[主题]的相关资料并总结",
  icon: SearchIcon,
  group: "create",
});

registerInputSuggestion({
  id: "data-analysis",
  label: "数据分析",
  prompt: "分析[数据文件/主题]并生成可视化图表",
  icon: BarChart3Icon,
  group: "create",
});
