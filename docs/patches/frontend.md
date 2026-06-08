# 前端补丁

## A6：`next.config.js` — 路由层重写 `/` 和 `/login` → `/ads-login`

**文件**: `frontend/next.config.js`
**风险**: ✅ 低（`{beforeFiles, afterFiles, fallback}` 为 Next.js 标准 API 格式，不是侵入性改动）

在 `async rewrites()` 中，返回格式从扁平数组改为标准对象格式：

```javascript
return {
  beforeFiles: [
    { source: "/", destination: "/ads-login" },
    { source: "/login", destination: "/ads-login" },
    { source: "/login/:path*", destination: "/ads-login/:path*" },
  ],
  afterFiles: [
    // ... 原有 API proxy rewrites
  ],
  fallback: [],
};
```

**为什么没有更小侵入的方案**:
- `beforeFiles` 是 Next.js 官方路由文档推荐的路径替换方式。扁平数组（`rewrites()` 返回数组）等价于 `afterFiles`，路由优先级低于页面组件，无法覆盖 `/` 和 `/login` 这类已存在的页面路由。
- `redirects()` 返回扁平数组不改格式，但触发 301/302 导致地址栏 URL 变化，用户体验差。
- `{beforeFiles, afterFiles, fallback}` 不是侵入性更改——它是 Next.js 的**完整 API 格式**，扁平数组只是它的简化糖。

---

## A7：`frontend/middleware.ts` — Next.js Middleware 内联（路由保护 + 重写）

**文件**: `frontend/middleware.ts`
**风险**: ✅ 低

之前该文件只有 1 行 re-export：`export { middleware, config } from "./extensions/ads_auth/middleware-handler";`

现在内联为完整 37 行 middleware，包含：

1. **公开路径跳过**: `/_next`、`/favicon.ico`、`/images`、`/ads-login` 直接 `next()`
2. **主页预检（2026-05-29 新增）**: `/` → 先检查 `access_token` cookie，有则 302 到 `/workspace`，无则 rewrite 到 `/ads-login`
3. **登录页重写**: `/login` → rewrite 到 `/ads-login`
4. **Token 守卫**: 无 `access_token` cookie 时 redirect 到 `/login?next=原路径`

**注意**: `next.config.js` 的 `beforeFiles` 优先级高于 middleware，所以第 2、3 步在实际运行中不会被触发（请求到 `/` 已在路由层被改写）。保留它们是为了**文档对称性和回退安全性**——如果未来去掉了 `beforeFiles`，middleware 仍能兜底。

---

## A8：`frontend/src/core/auth/types.ts` — 登录 URL 路由到 ADS

**文件**: `frontend/src/core/auth/types.ts`
**行号**: L29
**风险**: ✅ 极低

**改动**:
```diff
 export function buildLoginUrl(returnPath: string): string {
-  return `/login?next=${encodeURIComponent(returnPath)}`;
+  return `/ads-login?next=${encodeURIComponent(returnPath)}`;
 }
```

**原因**: `buildLoginUrl` 被客户端代码调用，生成跳转到登录页的 URL。原值 `/login` 会被 `next.config.js` 的 `beforeFiles` rewrite 到 `/ads-login`，但在某些客户端路由场景下，直接输出 `/ads-login` 更可靠（避免客户端 router 绕开 rewrite）。

---

---

## S1：`settings-dialog.tsx` — 4 处 EXTENSION SLOT 插槽

**文件**: `frontend/src/components/workspace/settings/settings-dialog.tsx`
**风险**: ✅ 低（扩展插槽模式，不修改原有行为，向后兼容）

### S1a — Props 中增加扩展插槽（L42-L51）

```typescript
type SettingsDialogProps = React.ComponentProps<typeof Dialog> & {
  defaultSection?: SettingsSection;
  // --- EXTENSION SLOT: begin ---
  additionalSections?: Array<{
    id: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    component: React.ComponentType;
  }>;
  hiddenSectionIds?: string[];
  // --- EXTENSION SLOT: end ---
};
```

**原因**: 新增 `additionalSections`（外部注入的页面配置）和 `hiddenSectionIds`（隐藏内置页面）两个可选 props，第三方扩展可通过该接口向设置弹窗注入自定义设置页面。

### S1b — 解构赋值带默认值（L54-L56）

```typescript
  // --- EXTENSION SLOT: begin ---
  const { defaultSection = "appearance", additionalSections = [], hiddenSectionIds = [], ...dialogProps } = props;
  // --- EXTENSION SLOT: end ---
```

**原因**: 将新 props 从 props 中解构出来，并设置安全的默认值（空数组），确保未传值时行为不变。

### S1c — sections 数组合并扩展页面（L69-L117）

```typescript
  const sections = useMemo(
    () => [
      // --- EXTENSION SLOT: begin ---
      ...[
        { id: "account", ... },
        { id: "appearance", ... },
        // ... 内置 sections
        { id: "about", ... },
      ].filter((s) => !hiddenSectionIds.includes(s.id)),
      ...additionalSections.map((s) => ({
        id: s.id,
        label: s.label,
        icon: s.icon,
      })),
      // --- EXTENSION SLOT: end ---
    ],
    [
      // ... 原有依赖
      // --- EXTENSION SLOT: begin ---
      hiddenSectionIds.join(","),
      additionalSections,
      // --- EXTENSION SLOT: end ---
    ],
  );
```

**改动要点**:
1. 内置 sections 数组用 spread `...[array].filter(...)` 包起来，通过 `hiddenSectionIds` 过滤
2. 在末尾追加 `...additionalSections.map(...)`，将扩展页面添加到侧边栏导航
3. `useMemo` 的依赖数组中增加 `hiddenSectionIds.join(",")` 和 `additionalSections`

**原因**: 将内置 sections 和扩展 sections 合并为一个渲染数组。使用 `filter` 隐藏可被扩展隐藏的内置页面。

### S1d — 渲染区域增加扩展页面（L171-L173）

```typescript
              {/* --- EXTENSION SLOT: begin --- */}
              {additionalSections?.map((s) => activeSection === s.id ? <s.component /> : null)}
              {/* --- EXTENSION SLOT: end --- */}
```

**原因**: 在 `activeSection` 匹配时渲染扩展组件。原有条件渲染模式不变，扩展组件通过 `additionalSections` 数组匹配渲染。

---

## S2：`registry.ts` — SettingsExtension 注册表（新文件）

**文件**: `frontend/src/core/settings-extensions/registry.ts`
**风险**: ✅ 极低（全新文件，不影响现有代码）

```typescript
import type { LucideIcon } from "lucide-react";

export interface SettingsExtension {
  id: string;
  label: string;
  icon: LucideIcon;
  component: React.ComponentType;
}

const _extensions: SettingsExtension[] = [];

export function registerSettingsExtension(ext: SettingsExtension): void {
  if (_extensions.some((e) => e.id === ext.id)) return;
  _extensions.push(ext);
}

export function getSettingsExtensions(): SettingsExtension[] {
  return [..._extensions];
}

export function clearSettingsExtensions(): void {
  _extensions.length = 0;
}
```

**配套文件**: `frontend/src/core/settings-extensions/index.ts`（re-export）

**原因**: 提供类型安全的正向注册机制：
- `registerSettingsExtension()` — 扩展模块调用，将自身注册到中央列表（id 去重）
- `getSettingsExtensions()` — 返回当前所有已注册扩展的快照
- `clearSettingsExtensions()` — 测试场景中清空注册表

---

## S3：`workspace-nav-menu.tsx` — 集成扩展注册表

**文件**: `frontend/src/components/workspace/workspace-nav-menu.tsx`
**风险**: ✅ 低

### S3a — import 扩展注册表 + 扩展模块（L30-L35）

```typescript
import { getSettingsExtensions } from "@/core/settings-extensions";
// --- EXTENSION IMPORT: begin ---
import "@/core/env-settings/extension";
// --- EXTENSION IMPORT: end ---
```

**原因**: 
- `getSettingsExtensions` — 获取已注册的扩展列表并传入 `SettingsDialog`
- `import "@/core/env-settings/extension"` — side-effect import，触发 `registerSettingsExtension()` 注册 env-settings 扩展页面

### S3b — 将扩展透传到 SettingsDialog（L70-L80）

```typescript
  const extensions = getSettingsExtensions();

  return (
    <>
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        defaultSection={settingsDefaultSection}
        additionalSections={extensions}
        hiddenSectionIds={[]}
      />
```

**原因**: 
- `getSettingsExtensions()` 获取所有已注册的扩展页面列表
- 通过 `additionalSections` prop 传递给 `SettingsDialog`
- `hiddenSectionIds` 设为空数组（不隐藏任何内置页面）

---

## S4：`account-settings-page.tsx` — ADS 账号字段隐藏

**文件**: `frontend/src/components/workspace/settings/account-settings-page.tsx`
**风险**: ✅ 极低（仅注释隐藏代码，不删除，恢复时删除注释块即可）

### S4a — 隐藏 email/role 显示

原代码显示 `user.email`（固定为 `admin@example.com`）和 `user.system_role`（固定为 `user`），均为 ADS 占位值。改为只显示从 email 前缀提取的 ADS 账号名。

```typescript
{/*
// 🚫 以下两行被隐藏——原因：
//    当前使用 ADS 统一认证登录，返回的 email 为固定的
//    "admin@example.com", system_role 为 "user"，均为占位值
//    不反映实际 ADS 账号信息，显示出来会误导用户。
//    改为只显示 ADS 账号名（从 email 前缀提取）。
// ================================================================
*/}
<span className="text-muted-foreground text-sm">账号</span>
<span className="text-sm font-medium">
  {user?.email ? user.email.replace(/@.*$/, "") : "—"}
</span>
```

### S4b — 隐藏修改密码表单

ADS 密码由统一认证管理，DeerFlow 原生 change-password API 不可用。整个 `SettingsSection` 包裹在 JSX 注释块中。

```typescript
{/*
// 🚫 修改密码表单被隐藏——原因：
//    ADS 密码由统一认证管理，DeerFlow 原生 change-password API 不可用。
// ==================================================================
*/}
<SettingsSection
  title={t.settings.account.changePasswordTitle}
  ...
```

**原因**: ADS 统一认证登录后，user.email 固定为 "admin@example.com"、system_role 为 "user"（占位值），原生修改密码 API 不可用。隐藏不正确的字段和不可用的功能。

**验证命令**:
```bash
# 确认 email/role 被注释隐藏（输出不应显示 email/role 翻译 key）
grep -c "t\.settings\.account\.email\|t\.settings\.account\.role" \
  frontend/src/components/workspace/settings/account-settings-page.tsx
# 应输出 0（已隐藏）

# 确认"账号"行可见
grep -c "账号" frontend/src/components/workspace/settings/account-settings-page.tsx
# 应输出 1（从 email 前缀提取的账号名）

# 确认修改密码表单被注释包裹
grep -c "修改密码表单被隐藏" \
  frontend/src/components/workspace/settings/account-settings-page.tsx
# 应输出 1
```

**恢复方法**: 删除 `{/*` 注释开始标记和 `*/}` 注释结束标记之间的代码块，并删掉新加的"账号"行。

---

## A9：`frontend/extensions/ads_auth/LoginPage.tsx` — loading 转圈（2026-05-29 新增）

**文件**: `frontend/extensions/ads_auth/LoginPage.tsx`
**风险**: ✅ 极低（扩展目录）

**改动**: 新增 `isLoading` 状态变量，初始化时全屏居中显示 `Loader2Icon` 旋转动画。fetch `/auth/me` 确认未认证后才隐藏 loading、渲染表单。

**原因**: 消除已登录用户首次渲染时闪现登录表单的问题（与 middleware 预检配合，双层保障）。

---

## A10：`frontend/src/core/auth/server.ts` — E2E 后门 NODE_ENV 门控（2026-05-29 新增）

**文件**: `frontend/src/core/auth/server.ts`
**行号**: L13
**风险**: ✅ 极低

**改动**:
```typescript
// 修改前：
if (process.env.DEER_FLOW_AUTH_DISABLED === "1") {
// 修改后：
if (process.env.NODE_ENV === "test" && process.env.DEER_FLOW_AUTH_DISABLED === "1") {
```

**原因**: E2E 测试后门不应在非测试环境生效。NODE_ENV 门控后即使环境变量泄露也不影响生产。

---

---

## A11：`workspace-content.tsx` — 移动端侧栏触发按钮接入

**文件**: `frontend/src/app/workspace/workspace-content.tsx`
**行号**: L4, L29
**风险**: ✅ 极低（2 行：1 行 import + 1 行 JSX，其余代码在 `extensions/` 目录）

**改动**:

```diff
 import { cookies } from "next/headers";
 import { Toaster } from "sonner";
+import { MobileSidebarTrigger } from "../../../extensions/mobile-sidebar/mobile-sidebar-trigger";
 import { QueryClientProvider } from "@/components/query-client-provider";
 ...
       <SidebarProvider className="h-screen" defaultOpen={initialSidebarOpen}>
+        <MobileSidebarTrigger />
         <WorkspaceSidebar />
         <SidebarInset className="min-w-0">{children}</SidebarInset>
       </SidebarProvider>
```

**原因**: 移动端（`< 768px`）左侧栏以 Sheet 抽屉形式渲染，关闭后无触发按钮。`MobileSidebarTrigger` 在移动端显示浮动汉堡按钮，点击调用 `toggleSidebar()` 打开 Sheet。

**配套扩展文件**（全在 `frontend/extensions/mobile-sidebar/`，零侵入）：
- `frontend/extensions/mobile-sidebar/mobile-sidebar-trigger.tsx` — 浮动汉堡按钮组件

**恢复方法**: 删除 import 行和 JSX 行，删除 `frontend/extensions/mobile-sidebar/` 目录。

**验证命令**:

```bash
# 确认 import 存在
grep -n "MobileSidebarTrigger" frontend/src/app/workspace/workspace-content.tsx

# 确认扩展组件存在
ls frontend/extensions/mobile-sidebar/mobile-sidebar-trigger.tsx
```

---

## A12：`query-client-provider.tsx` — TanStack Query 缓存配置（2026-04-17）

**文件**: `frontend/src/components/query-client-provider.tsx`
**行号**: L7-L14
**风险**: ✅ 极低（纯配置修改，不改任何逻辑）

**改动**:

```diff
- const queryClient = new QueryClient();
+ const queryClient = new QueryClient({
+   defaultOptions: {
+     queries: {
+       gcTime: 1000 * 60 * 3,      // 3 分钟
+       staleTime: 1000 * 60,        // 1 分钟
+       refetchOnWindowFocus: false,
+     },
+   },
+ });
```

**原因**: 
- 默认 `gcTime`（5 分钟）和 `staleTime`（0 秒）导致前端频繁请求后端 API，增加服务器负载和内存占用
- 对非实时数据（如模型列表、设置）没必要每次 focus 都重新请求
- 此项已在 `docs/operations/OPERATIONS.md` 中作为内存优化配置记录

---

## 验证命令

```bash
# === A6: beforeFiles rewrites ===
grep -n "beforeFiles" frontend/next.config.js

# === A7: middleware ts ads_token ===
grep -n "ads_token\|PUBLIC_PATHS" frontend/middleware.ts

# === A8: types.ts buildLoginUrl ===
grep -n "buildLoginUrl\|ads-login" frontend/src/core/auth/types.ts

# === A10: server.ts NODE_ENV gate ===
grep -n "NODE_ENV.*test\|DEER_FLOW_AUTH_DISABLED" frontend/src/core/auth/server.ts

# === A11: workspace-content.tsx MobileSidebarTrigger ===
grep -n "MobileSidebarTrigger" frontend/src/app/workspace/workspace-content.tsx

# === A12: query-client-provider.tsx ===
grep -n "gcTime\|staleTime" frontend/src/components/query-client-provider.tsx

# === S1a: settings-dialog.tsx EXTENSION SLOT ===
grep -c "EXTENSION SLOT" frontend/src/components/workspace/settings/settings-dialog.tsx

# === S1b: settings-dialog.tsx additionalSections ===
grep -n "additionalSections" frontend/src/components/workspace/settings/settings-dialog.tsx | head -5

# === S1c: settings-dialog.tsx hiddenSectionIds ===
grep -n "hiddenSectionIds" frontend/src/components/workspace/settings/settings-dialog.tsx

# === S2: registry.ts ===
grep -c "registerSettingsExtension" frontend/src/core/settings-extensions/registry.ts

# === S3a: workspace-nav-menu.tsx getSettingsExtensions ===
grep -n "getSettingsExtensions" frontend/src/components/workspace/workspace-nav-menu.tsx

# === S3b: workspace-nav-menu.tsx EXTENSION IMPORT ===
grep -n "EXTENSION IMPORT" frontend/src/components/workspace/workspace-nav-menu.tsx

# === S5: 隐藏菜单注释 ===
grep -c "🚫 以下菜单项被隐藏" frontend/src/components/workspace/workspace-nav-menu.tsx

# === IS1: input-box.tsx EXTENSION IMPORT ===
grep -n "EXTENSION IMPORT" frontend/src/components/workspace/input-box.tsx

# === input-suggestions registry ===
grep -c "registerInputSuggestion" frontend/extensions/input-suggestions/registry.ts
```

---

---

## S5：`workspace-nav-menu.tsx` — 隐藏"设置和更多"下拉菜单多余按钮

**文件**: `frontend/src/components/workspace/workspace-nav-menu.tsx`
**行号**: L107-L164
**风险**: ✅ 极低（纯注释隐藏，不删除代码，恢复时删除注释块即可）

### 改动说明

左下角"设置和更多"下拉菜单中，除"设置"按钮外，其余 6 项菜单按钮全部以 `{/* 🚫 ... */}` 注释块隐藏。隐藏的按钮：

1. **分隔线**（L108 后的 `<DropdownMenuSeparator />`）
2. **访问 DeerFlow 官方网站**（L109-L118）
3. **在 Github 上查看 DeerFlow**（L119-L128）
4. **分隔线**（L129 的 `<DropdownMenuSeparator />`）
5. **报告问题**（L130-L139）
6. **联系我们**（L140-L145）
7. **分隔线**（L147 的外部 `<DropdownMenuSeparator />`）
8. **关于 DeerFlow**（L148-L156）

注释块内保留了全部原始代码，并在注释头中说明了隐藏原因和恢复方法。

**同时注释的导入**：
- `BugIcon`、`GlobeIcon`、`InfoIcon`、`MailIcon`（来自 `lucide-react`）
- `DropdownMenuSeparator`（来自 `@/components/ui/dropdown-menu`）
- `GithubIcon`（来自 `./github-icon`）

恢复菜单项时需同时取消这些导入的注释。

### 原因

根据功能自定义需求，左下角"设置和更多"下拉菜单只保留"设置"按钮。官方网站、Github、报告问题、联系我们、关于 DeerFlow 等按钮均隐藏，简化菜单内容。

### 恢复方法

删除 `{/*` 注释开始标记和 `*/}` 注释结束标记之间的代码块。

### 验证命令

```bash
# 确认隐藏按钮的注释标记存在
grep -c "🚫 以下菜单项被隐藏" frontend/src/components/workspace/workspace-nav-menu.tsx
# 应输出 1

# 确认"设置"按钮仍然可见（不会被注释包裹）
grep -c "t.common.settings" frontend/src/components/workspace/workspace-nav-menu.tsx
# 应输出 1（未被注释）
```

---

## IS1：`input-box.tsx` — 输入建议按钮扩展注册

**文件**: `frontend/src/components/workspace/input-box.tsx`
**风险**: ✅ 极低

### IS1a — 顶部增加扩展 import（L64-L68）

```typescript
// --- EXTENSION IMPORT: input suggestions ---
import { getInputSuggestions } from "../../../extensions/input-suggestions/registry";
import "../../../extensions/input-suggestions/config";
// --- EXTENSION IMPORT: end ---
```

**原因**: `getInputSuggestions` 提供从扩展注册表动态获取按钮列表的能力，`config.ts` 的 side-effect import 触发按钮注册。

### IS1b — SuggestionList 改为动态注册模式

**代码位置**: SuggestionList 组件内（L920-L1010）

原有的硬编码按钮（小惊喜/写作/研究/收集/学习/网页/图片/视频/技能）通过 JSX 注释块保留，替换为从扩展注册表动态加载的模式：

```typescript
const allSuggestions = getInputSuggestions();
const mainSuggestions = allSuggestions.filter(s => s.group === "main");
const createSuggestions = allSuggestions.filter(s => s.group === "create");
```

**配套扩展文件**（全在 `frontend/extensions/`，零侵入）：
- `frontend/extensions/input-suggestions/registry.ts` — 注册表
- `frontend/extensions/input-suggestions/config.ts` — 7 个业务按钮配置

**原因**: 
- 旧代码从 `t.inputBox.suggestions`（i18n 硬编码）渲染按钮，无法自定义
- 新代码从扩展注册表动态加载按钮，只需修改 config.ts 即可增删改
- 旧按钮中的"小惊喜"触发已禁用的 `surprise-me` 技能

**恢复方法**: 
1. 删除 `--- EXTENSION IMPORT ---` 注释块内的 2 行 import
2. 删除 SuggestionList 中的新代码
3. 取消 JSX 注释块，恢复旧代码
4. 取消注释已注释的 import：`SparklesIcon`、`ConfettiButton`、`DropdownMenuSeparator`

---

## WS: env-settings 渠道配置

**文件**: `frontend/extensions/env-settings/`
**风险**: ✅ 极低（扩展目录，零侵入）

### WS1 — api.ts 路径拆分 + 新增渠道 API

1. 现有 4 个函数的 URL 路径从 `/api/env-settings` 改为 `/api/env-settings/providers`
2. 新增 4 个渠道 API 函数：`loadChannelSettings`、`updateChannel`、`deleteChannel`、`verifyChannel`

### WS2 — types.ts 新增渠道类型

新增 `ChannelInfo`、`ChannelSettingsResponse`、`ChannelUpdateRequest` 三个接口。

### WS3 — hooks.ts 新增渠道 hooks

新增 `useChannelSettings`、`useUpdateChannel`、`useDeleteChannel`、`useVerifyChannel` 四个 hooks（原有 hooks 名称不变）。

### WS4 — channel-settings-page.tsx（新文件）

独立的"渠道配置"标签页，包含 WeCom Bot ID/Secret 配置表单、安全重启逻辑、审计日志。

### WS5 — extension.ts 双注册

注册两个扩展：`id:"api"`（API Keys）+ `id:"channels"`（渠道配置）。

### WS6 — 多渠道扩展（2026-06-08）

**文件**: `frontend/extensions/env-settings/`
**风险**: ✅ 极低（扩展目录，零侵入）

将渠道配置从 WeCom 专用改为多渠道（企业微信/飞书/钉钉/微信）通用界面。

#### WS6a — channels.ts 新建渠道元数据

新增文件，定义 4 个国内 IM 渠道的 `ChannelMeta` 元数据（`credentialFields` 凭据字段列表），前端据此动态渲染输入表单。

#### WS6b — types.ts 凭据字典化

`ChannelInfo.bot_id_exists`/`bot_id_masked`/`bot_secret_exists` 合并为 `credentials: Record<string, string>`，`ChannelUpdateRequest` 同理，新增 `ChannelVerifyRequest`。

#### WS6c — api.ts verifyChannel 签名更新

`verifyChannel(channel, botId, botSecret)` → `verifyChannel(channel, credentials)`。

#### WS6d — hooks.ts 适配

`useVerifyChannel` mutation 参数改为 `{ channel, credentials }`。

#### WS6e — channel-settings-page.tsx 多渠道重构

- 新增渠道选择器（Select 下拉框，从 `CHANNELS` 元数据渲染）
- 凭据表单根据 `selectedMeta.credentialFields` 动态渲染
- 眼睛按钮按 `field.key` 独立控制
- 删除确认弹窗引用 `selectedMeta.name`
- 切换渠道时重置 formValues/showFields
