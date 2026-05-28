# 部署脚本变更

## 1. 修改 `deerflow_extensions/entrypoint.sh`

**entrypoint.sh 改动**:

| 文件 | 说明 |
|------|------|
| `deerflow_extensions/entrypoint.sh` | sitecustomize 符号链接改为指向 `deerflow_extensions/sitecustomize.py`（合并加载器） |

## 2. 新增 `deerflow_extensions/sitecustomize.py`

- 合并加载 `data_collection` + `ads_auth` 两个扩展
