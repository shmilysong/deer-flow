# 技能与 Demo 变更

## 23. `skills/public/github-deep-research/SKILL.md`

```diff
@@ -147,5 +147,5 @@ Save report as: `research_{topic}_{YYYYMMDD}.md`
 3. **Triangulate claims** - 2+ independent sources
 4. **Note conflicting info** - Don't hide contradictions
 5. **Distinguish fact vs opinion** - Label speculation clearly
-6. **Cite inline** - Reference sources near claims
+6. **Reference sources** - Add source references near claims where applicable
 7. **Update as you go** - Don't wait until end to synthesize
```

- 第 150 行：一条措辞修改。

---

## 24. `skills/public/market-analysis/SKILL.md`

```diff
@@ -15,7 +15,7 @@ This skill generates professional, consulting-grade market analysis reports in M
 - Follow the **"Visual Anchor → Data Contrast → Integrated Analysis"** flow per sub-chapter
 - Produce insights following the **"Data → User Psychology → Strategy Implication"** chain
 - Embed pre-generated charts and construct comparison tables
-- Generate inline citations formatted per **GB/T 7714-2015** standards
+- Include references formatted per **GB/T 7714-2015** where applicable
 - Output reports entirely in Chinese with professional consulting tone
 ...
@@ -36,7 +36,7 @@ The skill expects the following inputs from the upstream agentic workflow:
 | **Analysis Framework Outline** | Defines the logic flow and general topics for the report | Yes |
 | **Data Summary** | The source of truth containing raw numbers and metrics | Yes |
 | **Chart Files** | Local file paths for pre-generated chart images | Yes |
-| **External Search Findings** | URLs and summaries for inline citations | Optional |
+| **External Search Findings** | URLs and summaries for inline references | Optional |
 ...
@@ -87,7 +87,7 @@ The report **MUST NOT** stop after the Conclusion — it **MUST** include Refere
 - **Tone**: McKinsey/BCG — Authoritative, Objective, Professional
 - **Language**: All headings and content strictly in **Chinese**
 - **Number Formatting**: Use English commas for thousands separators (`1,000` not `1，000`)
-- **Data Citation**: **Bold** important viewpoints and key numbers
+- **Data emphasis**: **Bold** important viewpoints and key numbers
 ...
@@ -109,11 +109,9 @@ Every insight must connect **Data → User Psychology → Strategy Implication**
    treating male audiences only as a secondary gift-giving segment."
 ```
 
-### Citations & References
-- **Inline**: Use `[\[Index\]](URL)` format (e.g., `[\[1\]](https://example.com)`)
-- **Placement**: Append citations at the end of sentences using information from External Search Findings
-- **Index Assignment**: Sequential starting from **1** based on order of appearance
-- **References Section**: Formatted strictly per **GB/T 7714-2015**
+### References
+- **Inline**: Use markdown links for sources (e.g. `[Source Title](URL)`) when using External Search Findings
+- **References section**: Formatted strictly per **GB/T 7714-2015**
 ...
@@ -183,7 +181,7 @@ Before considering the report complete, verify:
 - [ ] All headings are in Chinese with proper numbering (no "Chapter/Part/Section")
 - [ ] Charts are embedded with `![Description](path)` syntax
 - [ ] Numbers use English commas for thousands separators
-- [ ] Inline citations use `[\[N\]](URL)` format
+- [ ] Inline references use markdown links where applicable
 - [ ] References section follows GB/T 7714-2015
```

- 多处：核心能力、输入表、Data Citation、Citations & References 小节与检查项，改为「references / 引用」表述并去掉 `[\[N\]](URL)` 格式要求。

---

## 25. `frontend/public/demo/threads/.../user-data/outputs/research_deerflow_20260201.md`

```diff
@@ -1,12 +1,3 @@
-<citations>
-{"id": "cite-1", "title": "DeerFlow GitHub Repository", "url": "https://github.com/bytedance/deer-flow", "snippet": "..."}
-...（共 7 条 JSONL）
-</citations>
 # DeerFlow Deep Research Report
 
 - **Research Date:** 2026-02-01
```

- 删除文件开头的 `<citations>...</citations>` 整块（9 行），正文从 `# DeerFlow Deep Research Report` 开始。

---

## 26. `frontend/public/demo/threads/.../thread.json`

- **主要变更**：某条 `write_file` 的 `args.content` 中，将原来的「`<citations>...\n</citations>\n# DeerFlow Deep Research Report\n\n...`」改为「`# DeerFlow Deep Research Report\n\n...`」，即去掉 `<citations>...</citations>` 块，保留其后全文。
- **其他**：一处 `present_files` 的 `filepaths` 由单行数组改为多行格式；文件末尾增加/统一换行。
- 消息顺序、结构及其他字段未改。
