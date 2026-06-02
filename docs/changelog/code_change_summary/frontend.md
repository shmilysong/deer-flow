# 前端变更

## 二、前端文档与工具

### 5. `frontend/AGENTS.md`

```diff
@@ -49,7 +49,6 @@ src/
 ├── core/                   # Core business logic
 │   ├── api/                # API client & data fetching
 │   ├── artifacts/          # Artifact management
-│   ├── citations/          # Citation handling
 │   ├── config/              # App configuration
 │   ├── i18n/               # Internationalization
```

- **第 52 行**：删除目录树中的 `citations/` 一行。

---

### 6. `frontend/CLAUDE.md`

```diff
@@ -30,7 +30,7 @@ Frontend (Next.js) ──▶ LangGraph SDK ──▶ LangGraph Backend (lead_age
                                               └── Tools & Skills
 ```
 
-The frontend is a stateful chat application. Users create **threads** (conversations), send messages, and receive streamed AI responses. The backend orchestrates agents that can produce **artifacts** (files/code), **todos**, and **citations**.
+The frontend is a stateful chat application. Users create **threads** (conversations), send messages, and receive streamed AI responses. The backend orchestrates agents that can produce **artifacts** (files/code) and **todos**.
 
 ### Source Layout (`src/`)
```

- **第 33 行**：「and **citations**」删除。

---

### 8. `frontend/src/components/workspace/settings/account-settings-page.tsx` — ADS 账号适配

**原因**: ADS 统一认证登录后，user.email 固定为 "admin@example.com"、system_role 为 "user"（占位值），原生修改密码 API 不可用。隐藏不正确的字段和不可用的功能。

**改动**:
1. 隐藏 email/role 显示区（注释保留），改为只显示从 email 前缀提取的账号名
2. 隐藏"修改密码"表单（注释保留），因为 ADS 密码由统一认证管理

---

### 7. `frontend/README.md`

```diff
@@ -89,7 +89,6 @@ src/
 ├── core/                   # Core business logic
 │   ├── api/                # API client & data fetching
 │   ├── artifacts/          # Artifact management
-│   ├── citations/          # Citation handling
 │   ├── config/              # App configuration
 │   ├── i18n/               # Internationalization
```

- **第 92 行**：删除目录树中的 `citations/` 一行。

---

### 8. `frontend/src/lib/utils.ts`

```diff
@@ -8,5 +8,5 @@ export function cn(...inputs: ClassValue[]) {
 /** Shared class for external links (underline by default). */
 export const externalLinkClass =
   "text-primary underline underline-offset-2 hover:no-underline";
-/** For streaming / loading state when link may be a citation (no underline). */
+/** Link style without underline by default (e.g. for streaming/loading). */
 export const externalLinkClassNoUnderline = "text-primary hover:underline";
```

- **第 11 行**：仅注释修改，导出值未变。

---

## 三、前端组件

### 9. `frontend/src/components/workspace/artifacts/artifact-file-detail.tsx`

```diff
@@ -8,7 +8,6 @@ import {
   SquareArrowOutUpRightIcon,
   XIcon,
 } from "lucide-react";
-import * as React from "react";
 import { useCallback, useEffect, useMemo, useState } from "react";
 ...
@@ -21,7 +20,6 @@ import (
   ArtifactHeader,
   ArtifactTitle,
 } from "@/components/ai-elements/artifact";
-import { createCitationMarkdownComponents } from "@/components/ai-elements/inline-citation";
 import { Select, SelectItem } from "@/components/ui/select";
 ...
@@ -33,12 +31,6 @@ import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
 import { CodeEditor } from "@/components/workspace/code-editor";
 import { useArtifactContent } from "@/core/artifacts/hooks";
 import { urlOfArtifact } from "@/core/artifacts/utils";
-import type { Citation } from "@/core/citations";
-import {
-  contentWithoutCitationsFromParsed,
-  removeAllCitations,
-  useParsedCitations,
-} from "@/core/citations";
 import { useI18n } from "@/core/i18n/hooks";
 ...
@@ -48,9 +40,6 @@ import { cn } from "@/lib/utils";
 
 import { Tooltip } from "../tooltip";
 
-import { SafeCitationContent } from "../messages/safe-citation-content";
-import { useThread } from "../messages/context";
-
 import { useArtifacts } from "./context";
```

```diff
@@ -92,22 +81,13 @@ export function ArtifactFileDetail({
   const previewable = useMemo(() => {
     return (language === "html" && !isWriteFile) || language === "markdown";
   }, [isWriteFile, language]);
-  const { thread } = useThread();
   const { content } = useArtifactContent({
     threadId,
     filepath: filepathFromProps,
     enabled: isCodeFile && !isWriteFile,
   });
 
-  const parsed = useParsedCitations(
-    language === "markdown" ? (content ?? "") : "",
-  );
-  const cleanContent =
-    language === "markdown" && content ? parsed.cleanContent : (content ?? "");
-  const contentWithoutCitations =
-    language === "markdown" && content
-      ? contentWithoutCitationsFromParsed(parsed)
-      : (content ?? "");
+  const displayContent = content ?? "";
 
   const [viewMode, setViewMode] = useState<"code" | "preview">("code");
```

```diff
@@ -219,7 +199,7 @@ export function ArtifactFileDetail({
                 disabled={!content}
                 onClick={async () => {
                   try {
-                    await navigator.clipboard.writeText(contentWithoutCitations ?? "");
+                    await navigator.clipboard.writeText(displayContent ?? "");
                     toast.success(t.clipboard.copiedToClipboard);
 ...
@@ -255,27 +235,17 @@ export function ArtifactFileDetail({
           viewMode === "preview" &&
           language === "markdown" &&
           content && (
-            <SafeCitationContent
-              content={content}
-              isLoading={thread.isLoading}
-              rehypePlugins={streamdownPlugins.rehypePlugins}
-              className="flex size-full items-center justify-center p-4 my-0"
-              renderBody={(p) => (
-                <ArtifactFilePreview
-                  filepath={filepath}
-                  threadId={threadId}
-                  content={content}
-                  language={language ?? "text"}
-                  cleanContent={p.cleanContent}
-                  citationMap={p.citationMap}
-                />
-              )}
+            <ArtifactFilePreview
+              filepath={filepath}
+              threadId={threadId}
+              content={displayContent}
+              language={language ?? "text"}
             />
           )}
         {isCodeFile && viewMode === "code" && (
           <CodeEditor
             className="size-full resize-none rounded-none border-none"
-            value={cleanContent ?? ""}
+            value={displayContent ?? ""}
             readonly
           />
         )}
```

```diff
@@ -295,29 +265,17 @@ export function ArtifactFilePreview({
   threadId,
   content,
   language,
-  cleanContent,
-  citationMap,
 }: {
   filepath: string;
   threadId: string;
   content: string;
   language: string;
-  cleanContent: string;
-  citationMap: Map<string, Citation>;
 }) {
   if (language === "markdown") {
-    const components = createCitationMarkdownComponents({
-      citationMap,
-      syntheticExternal: true,
-    });
     return (
       <div className="size-full px-4">
-        <Streamdown
-          className="size-full"
-          {...streamdownPlugins}
-          components={components}
-        >
-          {cleanContent ?? ""}
+        <Streamdown className="size-full" {...streamdownPlugins}>
+          {content ?? ""}
         </Streamdown>
       </div>
     );
```

- 删除：React 命名空间、inline-citation、core/citations、SafeCitationContent、useThread；parsed/cleanContent/contentWithoutCitations 及引用解析逻辑。
- 新增：`displayContent = content ?? ""`；预览与复制、CodeEditor 均使用 `displayContent`；`ArtifactFilePreview` 仅保留 `content`/`language` 等，去掉 `cleanContent`/`citationMap` 与 `createCitationMarkdownComponents`。

---

### 10. `frontend/src/components/workspace/messages/message-group.tsx`

```diff
@@ -39,9 +39,7 @@ import { useArtifacts } from "../artifacts";
 import { FlipDisplay } from "../flip-display";
 import { Tooltip } from "../tooltip";
 
-import { useThread } from "./context";
-
-import { SafeCitationContent } from "./safe-citation-content";
+import { MarkdownContent } from "./markdown-content";
 
 export function MessageGroup({
```

```diff
@@ -120,7 +118,7 @@ export function MessageGroup({
                 <ChainOfThoughtStep
                   key={step.id}
                   label={
-                    <SafeCitationContent
+                    <MarkdownContent
                       content={step.reasoning ?? ""}
                       isLoading={isLoading}
                       rehypePlugins={rehypePlugins}
@@ -128,12 +126,7 @@ export function MessageGroup({
                   }
                 ></ChainOfThoughtStep>
               ) : (
-                <ToolCall
-                  key={step.id}
-                  {...step}
-                  isLoading={isLoading}
-                  rehypePlugins={rehypePlugins}
-                />
+                <ToolCall key={step.id} {...step} isLoading={isLoading} />
               ),
             )}
           {lastToolCallStep && (
@@ -143,7 +136,6 @@ export function MessageGroup({
                 {...lastToolCallStep}
                 isLast={true}
                 isLoading={isLoading}
-                rehypePlugins={rehypePlugins}
               />
             </FlipDisplay>
           )}
@@ -178,7 +170,7 @@ export function MessageGroup({
               <ChainOfThoughtStep
                 key={lastReasoningStep.id}
                 label={
-                  <SafeCitationContent
+                  <MarkdownContent
                     content={lastReasoningStep.reasoning ?? ""}
                     isLoading={isLoading}
                     rehypePlugins={rehypePlugins}
@@ -201,7 +193,6 @@ function ToolCall({
   result,
   isLast = false,
   isLoading = false,
-  rehypePlugins,
 }: {
   id?: string;
   messageId?: string;
@@ -210,15 +201,10 @@ function ToolCall({
   result?: string | Record<string, unknown>;
   isLast?: boolean;
   isLoading?: boolean;
-  rehypePlugins: ReturnType<typeof useRehypeSplitWordsIntoSpans>;
 }) {
   const { t } = useI18n();
   const { setOpen, autoOpen, autoSelect, selectedArtifact, select } =
     useArtifacts();
-  const { thread } = useThread();
-  const threadIsLoading = thread.isLoading;
-
-  const fileContent = typeof args.content === "string" ? args.content : "";
 
   if (name === "web_search") {
```

```diff
@@ -364,42 +350,27 @@ function ToolCall({
       }, 100);
     }
 
-    const isMarkdown =
-      path?.toLowerCase().endsWith(".md") ||
-      path?.toLowerCase().endsWith(".markdown");
-
     return (
-      <>
-        <ChainOfThoughtStep
-          key={id}
-          className="cursor-pointer"
-          label={description}
-          icon={NotebookPenIcon}
-          onClick={() => {
-            select(
-              new URL(
-                `write-file:${path}?message_id=${messageId}&tool_call_id=${id}`,
-              ).toString(),
-            );
-            setOpen(true);
-          }}
-        >
-          {path && (
-            <ChainOfThoughtSearchResult className="cursor-pointer">
-              {path}
-            </ChainOfThoughtSearchResult>
-          )}
-        </ChainOfThoughtStep>
-        {isMarkdown && (
-          <SafeCitationContent
-            content={fileContent}
-            isLoading={threadIsLoading && isLast}
-            rehypePlugins={rehypePlugins}
-            loadingOnly
-            className="mt-2 ml-8"
-          />
+      <ChainOfThoughtStep
+        key={id}
+        className="cursor-pointer"
+        label={description}
+        icon={NotebookPenIcon}
+        onClick={() => {
+          select(
+            new URL(
+              `write-file:${path}?message_id=${messageId}&tool_call_id=${id}`,
+            ).toString(),
+          );
+          setOpen(true);
+        }}
+      >
+        {path && (
+          <ChainOfThoughtSearchResult className="cursor-pointer">
+            {path}
+          </ChainOfThoughtSearchResult>
         )}
-      </>
+      </ChainOfThoughtStep>
     );
   } else if (name === "bash") {
```

- 两处 `SafeCitationContent` → `MarkdownContent`；ToolCall 去掉 `rehypePlugins` 及内部 `useThread`/`fileContent`；write_file 分支去掉 markdown 预览块（`isMarkdown` + `SafeCitationContent`），仅保留 `ChainOfThoughtStep` + path。

---

### 11. `frontend/src/components/workspace/messages/message-list-item.tsx`

```diff
@@ -12,7 +12,6 @@ import {
 } from "@/components/ai-elements/message";
 import { Badge } from "@/components/ui/badge";
 import { resolveArtifactURL } from "@/core/artifacts/utils";
-import { removeAllCitations } from "@/core/citations";
 import {
   extractContentFromMessage,
   extractReasoningContentFromMessage,
@@ -24,7 +23,7 @@ import { humanMessagePlugins } from "@/core/streamdown";
 import { cn } from "@/lib/utils";
 
 import { CopyButton } from "../copy-button";
-import { SafeCitationContent } from "./safe-citation-content";
+import { MarkdownContent } from "./markdown-content";
 ...
@@ -54,11 +53,11 @@ export function MessageListItem({
       >
         <div className="flex gap-1">
           <CopyButton
-            clipboardData={removeAllCitations(
+            clipboardData={
               extractContentFromMessage(message) ??
               extractReasoningContentFromMessage(message) ??
               ""
-            )}
+            }
           />
         </div>
       </MessageToolbar>
@@ -154,7 +153,7 @@ function MessageContent_({
   return (
     <AIElementMessageContent className={className}>
       {filesList}
-      <SafeCitationContent
+      <MarkdownContent
         content={contentToParse}
         isLoading={isLoading}
         rehypePlugins={[...rehypePlugins, [rehypeKatex, { output: "html" }]]}
```

- 删除 `removeAllCitations` 与 `SafeCitationContent` 引用；复制改为原始内容；渲染改为 `MarkdownContent`。

---

### 12. `frontend/src/components/workspace/messages/message-list.tsx`

```diff
@@ -26,7 +26,7 @@ import { StreamingIndicator } from "../streaming-indicator";
 
 import { MessageGroup } from "./message-group";
 import { MessageListItem } from "./message-list-item";
-import { SafeCitationContent } from "./safe-citation-content";
+import { MarkdownContent } from "./markdown-content";
 import { MessageListSkeleton } from "./skeleton";
 ...
@@ -69,7 +69,7 @@ export function MessageList({
             const message = group.messages[0];
             if (message && hasContent(message)) {
               return (
-                <SafeCitationContent
+                <MarkdownContent
                   key={group.id}
                   content={extractContentFromMessage(message)}
                   isLoading={thread.isLoading}
@@ -89,7 +89,7 @@ export function MessageList({
             return (
               <div className="w-full" key={group.id}>
                 {group.messages[0] && hasContent(group.messages[0]) && (
-                  <SafeCitationContent
+                  <MarkdownContent
                     content={extractContentFromMessage(group.messages[0])}
                     isLoading={thread.isLoading}
                     rehypePlugins={rehypePlugins}
```

- 三处：import 与两处渲染均由 `SafeCitationContent` 改为 `MarkdownContent`，props 不变。

---

### 13. `frontend/src/components/workspace/messages/subtask-card.tsx`

```diff
@@ -29,7 +29,7 @@ import { cn } from "@/lib/utils";
 
 import { FlipDisplay } from "../flip-display";
 
-import { SafeCitationContent } from "./safe-citation-content";
+import { MarkdownContent } from "./markdown-content";
 ...
@@ -153,7 +153,7 @@ export function SubtaskCard({
               <ChainOfThoughtStep
                 label={
                   task.result ? (
-                    <SafeCitationContent
+                    <MarkdownContent
                       content={task.result}
                       isLoading={false}
                       rehypePlugins={rehypePlugins}
```

- import 与一处渲染：`SafeCitationContent` → `MarkdownContent`。

---

### 14. 新增 `frontend/src/components/workspace/messages/markdown-content.tsx`

（当前工作区新增，未在 git 中）

```ts
"use client";

import type { ImgHTMLAttributes } from "react";
import type { ReactNode } from "react";

import {
  MessageResponse,
  type MessageResponseProps,
} from "@/components/ai-elements/message";
import { streamdownPlugins } from "@/core/streamdown";

export type MarkdownContentProps = {
  content: string;
  isLoading: boolean;
  rehypePlugins: MessageResponseProps["rehypePlugins"];
  className?: string;
  remarkPlugins?: MessageResponseProps["remarkPlugins"];
  isHuman?: boolean;
  img?: (props: ImgHTMLAttributes<HTMLImageElement> & { threadId?: string; maxWidth?: string }) => ReactNode;
};

/** Renders markdown content. */
export function MarkdownContent({
  content,
  rehypePlugins,
  className,
  remarkPlugins = streamdownPlugins.remarkPlugins,
  img,
}: MarkdownContentProps) {
  if (!content) return null;
  const components = img ? { img } : undefined;
  return (
    <MessageResponse
      className={className}
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
    >
      {content}
    </MessageResponse>
  );
}
```

- 纯 Markdown 渲染组件，无引用解析或 loading 占位逻辑。

---

### 15. 删除 `frontend/src/components/workspace/messages/safe-citation-content.tsx`

- 原约 85 行；提供引用解析、loading、renderBody/loadingOnly、cleanContent/citationMap。已由 `MarkdownContent` 替代，整文件删除。

---

### 16. 删除 `frontend/src/components/ai-elements/inline-citation.tsx`

- 原约 289 行；提供 `createCitationMarkdownComponents` 等，用于将 `[cite-N]`/URL 渲染为可点击引用。仅被 artifact 预览使用，已移除后整文件删除。

---

## 四、前端 core

### 17. 删除 `frontend/src/core/citations/index.ts`

- 原 13 行，导出：`contentWithoutCitationsFromParsed`、`extractDomainFromUrl`、`isExternalUrl`、`parseCitations`、`removeAllCitations`、`shouldShowCitationLoading`、`syntheticCitationFromLink`、`useParsedCitations`、类型 `Citation`/`ParseCitationsResult`/`UseParsedCitationsResult`。整文件删除。

---

### 18. 删除 `frontend/src/core/citations/use-parsed-citations.ts`

- 原 28 行，`useParsedCitations(content)` 与 `UseParsedCitationsResult`。整文件删除。

---

### 19. 删除 `frontend/src/core/citations/utils.ts`

- 原 226 行，解析 `<citations>`/`[cite-N]`、buildCitationMap、removeAllCitations、contentWithoutCitationsFromParsed 等。整文件删除。

---

### 20. `frontend/src/core/i18n/locales/types.ts`

```diff
@@ -115,12 +115,6 @@ export interface Translations {
     startConversation: string;
   };
 
-  // Citations
-  citations: {
-    loadingCitations: string;
-    loadingCitationsWithCount: (count: number) => string;
-  };
-
   // Chats
   chats: {
```

- 删除 `Translations.citations` 及其两个字段。

---

### 21. `frontend/src/core/i18n/locales/zh-CN.ts`

```diff
@@ -164,12 +164,6 @@ export const zhCN: Translations = {
     startConversation: "开始新的对话以查看消息",
   },
 
-  // Citations
-  citations: {
-    loadingCitations: "正在整理引用...",
-    loadingCitationsWithCount: (count: number) => `正在整理 ${count} 个引用...`,
-  },
-
   // Chats
   chats: {
```

- 删除 `citations` 命名空间。

---

### 22. `frontend/src/core/i18n/locales/en-US.ts`

```diff
@@ -167,13 +167,6 @@ export const enUS: Translations = {
     startConversation: "Start a conversation to see messages here",
   },
 
-  // Citations
-  citations: {
-    loadingCitations: "Organizing citations...",
-    loadingCitationsWithCount: (count: number) =>
-      `Organizing ${count} citation${count === 1 ? "" : "s"}...`,
-  },
-
   // Chats
   chats: {
```

- 删除 `citations` 命名空间。

---

## ADS 统一认证系统 — 前端模块

**前端扩展目录** `frontend/extensions/ads_auth/`:

| 文件 | 说明 |
|------|------|
| `middleware-handler.ts` | Next.js 认证网关核心逻辑 |
| `LoginPage.tsx` | ADS 登录页（FlickeringGrid 背景） |
| `LoginLayout.tsx` | 简版布局 |

**前端桥接文件（3 个，各 1 行 re-export）**:

| 文件 | re-export |
|------|-----------|
| `frontend/middleware.ts` | `extensions/ads_auth/middleware-handler` |
| `frontend/src/app/ads-login/page.tsx` | `extensions/ads_auth/LoginPage` |
| `frontend/src/app/ads-login/layout.tsx` | `extensions/ads_auth/LoginLayout` |

---

## ADS 主页替换：用 ADS 登录页替换着陆页

**动机**: 用户打开 `http://localhost:2026/` 时看到营销着陆页，需额外点击才能进入登录流程。直接用 ADS 登录页替换主页。

**方案**: `next.config.js` `beforeFiles` rewrites

- `/` → rewrite 到 `/ads-login`
- `/login` → rewrite 到 `/ads-login`
- `/login/:path*` → rewrite 到 `/ads-login/:path*`

`beforeFiles` 在 Next.js 路由层运行，优先级高于页面路由和 middleware，确保 `/` 和 `/login` 永远不会被原有页面组件处理。

**暴力测试结果**:

| 测试项 | 结果 |
|--------|------|
| 连续 20 次访问 `/` | 全部 200 ✅ |
| 并发 10 个请求 `/` | 全部 200 ✅ |
| 80 次 4 路径交替（循环检测） | 19111ms，无循环 ✅ |
| `/login` 直接访问 | 200，内容为 ADS 登录页 ✅ |
| `/ads-login` 直接访问 | 200 ✅ |
| 后端回归（setup-status / login-local / me） | 200 / 410 / 401 ✅ |

**改动文件**: `frontend/next.config.js` — 新增 `beforeFiles` rewrites + 保留原有 API proxy rewrites

---

## SettingsDialog 扩展架构

**动机**: 为第三方扩展提供向 SettingsDialog 注入自定义设置页面的能力，无需修改核心组件。采用 EXTENSION SLOT 标记 + 注册表模式，支持任意数量的扩展页面。

### 核心改动

**S1：`settings-dialog.tsx` — 4 处 EXTENSION SLOT 插槽**

| 位置 | 行号 | 改动 |
|------|------|------|
| Props 定义 | L42-L51 | 增加 `additionalSections` 和 `hiddenSectionIds` 两个可选 props |
| 解构赋值 | L54-L56 | 从 props 中解构新字段，带默认值 |
| sections 数组合并 | L69-L117 | 内置 sections 用 `hiddenSectionIds` 过滤后，追加 `additionalSections` |
| 渲染区域 | L171-L173 | 匹配 `activeSection` 时渲染扩展组件 |

**S2：`registry.ts` — SettingsExtension 注册表（新文件）**

- `frontend/src/core/settings-extensions/registry.ts` — 类型定义 + 注册/获取/清空
- `frontend/src/core/settings-extensions/index.ts` — re-export

**S3：`workspace-nav-menu.tsx` — 集成扩展注册表**

| 位置 | 行号 | 改动 |
|------|------|------|
| import | L30-L35 | 增加 `getSettingsExtensions` + `import "@/core/env-settings/extension"` |
| 透传 | L70-L80 | `getSettingsExtensions()` → `additionalSections` prop |

### 配套模块（前端核心，非补丁）

**`frontend/src/core/env-settings/`**（5 个文件）:

| 文件 | 说明 |
|------|------|
| `types.ts` | API 类型定义 |
| `api.ts` | `fetch` 封装 |
| `hooks.ts` | TanStack Query hooks |
| `env-settings-page.tsx` | 设置页面 UI |
| `extension.ts` | 注册入口，`registerSettingsExtension()` |

### 详细补丁

详细补丁记录见 `@./docs/patches/settings-dialog-ext/frontend.md`（补丁标签 S1-S3）。

---

## 2026-05-29: 首屏闪屏修复 + ADS JWT 安全加固

### `frontend/middleware.ts` — 中间件认证预检

**改动**: `/` 路径处理逻辑从无条件 rewrite 改为先检查 `access_token` cookie。有 cookie 则 302 到 `/workspace`，无 cookie 才 rewrite 到 `/ads-login`。同时 cookie 名从 `ads_token` 统一为 `access_token`。

**原因**: 消除已登录用户闪现登录页的问题；统一各层 cookie 命名。

### `frontend/extensions/ads_auth/LoginPage.tsx` — loading 转圈

**改动**: 新增 `isLoading` 状态，初始化时全屏居中显示 Loader2Icon 旋转动画，fetch 确认未认证后才渲染登录表单。

**原因**: 已登录用户首次渲染时不闪现登录表单（与 middleware 预检双层保障）。

### `frontend/src/core/auth/server.ts` — E2E 后门门控

**改动**: `DEER_FLOW_AUTH_DISABLED` 外层包裹 `NODE_ENV === "test"` 条件。

**原因**: 安全加固——E2E 测试后门仅在测试环境生效。

---

## 2026-06-01: API Keys 配置界面优化

### 前端文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/core/env-settings/types.ts` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/src/core/env-settings/api.ts` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/src/core/env-settings/hooks.ts` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/src/core/env-settings/providers.ts` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/src/core/env-settings/env-settings-page.tsx` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/src/core/env-settings/extension.ts` | 删除 | 迁至 `extensions/env-settings/` |
| `frontend/extensions/env-settings/` (6 个文件) | 新建 | 独立扩展目录，零侵入官方源码 |
| `frontend/src/components/workspace/workspace-nav-menu.tsx` | 修改 | import 路径指向 `extensions/env-settings/extension` |

### 新增能力

- 支持 7 个国产大模型厂商管理：硅基流动、DeepSeek、Kimi、Doubao、千问、MiniMax、GLM
- 服务商下拉选择器
- 模型下拉选择（预置 + 自定义输入）
- 自定义请求地址（可选）
- Key 连通性验证
- 一键清除厂商全部配置
- `.env` 文件缺失时正常降级

---

## 2026-06-02: API Keys 配置界面优化 — 前端 Bug 修复

### `frontend/extensions/env-settings/env-settings-page.tsx`

**改动**:
1. **保存按钮增加 model 强制检查**：
   ```tsx
   disabled={
     !apiKey.trim() ||
     (useCustomModel ? !customModel.trim() : !model) ||
     updateMutation.isPending
   }
   ```
2. **"选择模型"标签改为必填**：`选择模型` → `选择模型 *`
3. **placeholder 去掉"可选"字样**：`选择模型（可选）` → `选择模型`

**原因**: 后端已要求 model 必填（`min_length=1`），前端需同步。空 model 提交会被后端返回 422，用户体验差。
