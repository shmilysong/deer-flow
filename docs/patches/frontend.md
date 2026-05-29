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
2. **主页重写**: `/` → rewrite 到 `/ads-login`（与 `next.config.js` beforeFiles 冗余，但不冲突）
3. **登录页重写**: `/login` → rewrite 到 `/ads-login`
4. **Token 守卫**: 无 `ads_token` cookie 时 redirect 到 `/login?next=原路径`

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

### S4a — 隐藏 email/role 显示（L76-L98）

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

### S4b — 隐藏修改密码表单（L103-L148）

ADS 密码由统一认证管理，DeerFlow 原生 change-password API 不可用。整个 `SettingsSection` 包裹在 JSX 注释块中。

**原因**: ADS 统一认证登录后，user.email 固定为 "admin@example.com"、system_role 为 "user"（占位值），原生修改密码 API 不可用。隐藏不正确的字段和不可用的功能。

**恢复方法**: 删除 `{/*` 注释开始标记和 `*/}` 注释结束标记之间的代码块，并删掉新加的"账号"行。

---

## 验证命令

```bash
# === A6: beforeFiles rewrites ===
grep -n "beforeFiles" frontend/next.config.js

# === A7: middleware ts ads_token ===
grep -n "ads_token\|PUBLIC_PATHS" frontend/middleware.ts

# === A8: types.ts buildLoginUrl ===
grep -n "buildLoginUrl\|ads-login" frontend/src/core/auth/types.ts

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
```
