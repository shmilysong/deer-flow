# 移动端侧栏

## 说明

在移动端设备上提供一个浮动在左上角的汉堡菜单按钮，点击后打开侧栏导航。仅在移动端且侧栏关闭时显示，避免干扰已打开的侧栏操作。

## 目录结构

```
mobile-sidebar/
└── mobile-sidebar-trigger.tsx  # 移动端浮动汉堡按钮组件
```

## 核心文件说明

### mobile-sidebar-trigger.tsx

客户端组件（`"use client"`），使用 shadcn/ui Sidebar 系统提供侧栏控制：

- **可见性控制**：通过 `useSidebar()` 获取 `isMobile`（是否移动端）和 `openMobile`（侧栏是否打开），仅在 `isMobile && !openMobile` 时渲染
- **交互**：点击触发 `toggleSidebar()` 切换侧栏开闭
- **定位**：`fixed top-3 left-3` 固定于左上角，`z-50` 确保浮于所有内容之上
- **样式**：`bg-background/80 backdrop-blur-sm` 毛玻璃效果，hover 时提升透明度，过渡动画 200ms
- **无障碍**：`aria-label="Open sidebar"` 为屏幕阅读器提供说明

按钮使用 `PanelLeftOpenIcon` 图标（lucide-react），尺寸 `size-4`，按钮整体 `size-8`。

## 使用方式

在布局或页面中引入组件即可自动生效：

```typescript
import { MobileSidebarTrigger } from "@/extensions/mobile-sidebar/mobile-sidebar-trigger";

// 在页面布局中渲染（通常放在侧栏组件附近）
<MobileSidebarTrigger />
```

组件内部自行判断是否显示，无需额外配置。

## 依赖

- shadcn/ui Sidebar（`useSidebar` hook，含 `isMobile`、`openMobile`、`toggleSidebar`）
- lucide-react（PanelLeftOpenIcon 图标）
- clsx + tailwind-merge（`cn()` 工具函数）
