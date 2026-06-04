# DeerFlow Distillation Data Collection System

Zero-intrusion side-channel collection of full-chain LLM inference data from DeerFlow, providing high-quality business-grounded training data for distillation.

## Architecture Overview

The system instruments the DeerFlow agent lifecycle at 6 collection points (P1-P6):

| Point | Hook Location | Data Captured |
|-------|--------------|---------------|
| **P1** | `before_model` / `abefore_model` (middleware) | Agent input: user query, system prompt, history context, RAG context |
| **P2** | `after_model` / `aafter_model` (middleware) | Model output: raw response, token usage, finish reason, thinking content |
| **P3** | `wrap_tool_call` / `awrap_tool_call` (before) | Tool invocation: tool name, parameters, call ID |
| **P4** | `wrap_tool_call` / `awrap_tool_call` (after) | Tool result: return value, error, latency |
| **P5** | `after_model` / `aafter_model` (middleware) | Intermediate state: step count, message count, accumulated tokens |
| **P6** | `after_agent` / `aafter_agent` (middleware) | Final response: total duration, total LLM/tool calls, resolution status |

Records are buffered in memory (configurable via `buffer_size`) and flushed asynchronously to daily JSONL files. All exceptions are caught and logged at DEBUG level -- a collector failure will never crash the agent.

## Quick Installation

Add the following 3 lines to `backend/app/gateway/app.py` (already present in the standard deployment):

```python
# Data collection system (zero-injection, monkey-patch based)
try:
    from deerflow_extensions.data_collection.startup import install_data_collection
    install_data_collection()
except ImportError:
    pass
```

Place the import block near the top of `app.py`, before the lifespan handler. The `try/except ImportError` ensures DeerFlow runs normally even if the `deerflow_extensions` package is not installed.

## Configuration

### YAML file

Create a `data_collection.yaml` anywhere accessible to the process:

```yaml
data_collection:
  enabled: true
  output_dir: /data/deerflow/training_logs
  buffer_size: 500
  flush_interval_sec: 5.0
  max_file_size_mb: 100
  collect_agent_input: true
  collect_model_output: true
  collect_tool_calls: true
  collect_intermediate_state: false
  collect_final_response: true
```

Pass the path to `install_data_collection(config_path="data_collection.yaml")`.

### Environment variables

Override individual settings without a YAML file:

| Variable | Config Key | Example |
|----------|-----------|---------|
| `DATA_COLLECTION_ENABLED` | enabled | `true` |
| `DATA_COLLECTION_OUTPUT_DIR` | output_dir | `/custom/path` |
| `DATA_COLLECTION_BUFFER_SIZE` | buffer_size | `1000` |
| `DATA_COLLECTION_FLUSH_INTERVAL` | flush_interval_sec | `10.0` |
| `DATA_COLLECTION_ROLE_EXTRACT_MODE` | role_extract_mode | `auto` |

### role_extract_mode configuration

The `role_extract_mode` setting controls how user messages are identified from LangGraph message objects:

| Mode | Description |
|------|-------------|
| `auto` (default) | Recognizes both `role="user"` and `type="human"` (LangGraph HumanMessage) |
| `human` | Only recognizes `type="human"` (LangGraph HumanMessage format) |
| `user` | Only recognizes `role="user"` (traditional format) |

For most DeerFlow deployments, `auto` is recommended as it handles both LangGraph's HumanMessage and dict-style messages correctly.

### Configuration priority

1. Standalone YAML file → 2. DeerFlow `config.yaml` → 3. Environment variables → 4. `DEFAULT_CONFIG` defaults

## Data Directory Structure

All collected data is written under the `output_dir` (default: `/data/deerflow/training_logs/`):

```
/data/deerflow/training_logs/
├── raw/                    # Reserved for future raw passthrough
├── daily/
│   └── train_data_YYYYMMDD.jsonl   # Current day's buffered records
├── archive/
│   └── train_data_YYYYMMDD_HHMMSS.jsonl  # Rotated files (>max_file_size_mb)
├── aggregated/
│   └── YYYYMMDD/
│       ├── train_data.jsonl         # Cleaned & aggregated training data
│       └── stats.json               # Pipeline statistics
└── flagged/
    └── YYYYMMDD/
        └── flagged_data.jsonl       # Error & short-reply records for Bad Case analysis
```

- **daily/**: Incremental raw JSONL, one file per day. Automatically rotates to `archive/` when exceeding `max_file_size_mb`.
- **aggregated/**: Output of `clean_and_aggregate.py`. Contains clean, deduplicated, session-merged training samples in OpenAI messages format.
- **flagged/**: Tagged records (errors, short replies) routed for Bad Case analysis. Preserved in full for downstream analysis pipelines.

## Daily Pipeline

Schedule `clean_and_aggregate.py` via cron to transform daily raw logs into training-ready datasets:

```cron
# Run daily at 03:00 UTC
0 3 * * * cd /path/to/deerflow && python -m deerflow_extensions.data_collection.scripts.clean_and_aggregate
```

The pipeline performs:
1. Filter incomplete records (missing session_id / user_query / raw_response)
2. Deduplicate by (user_query + raw_response) MD5 hash
3. Tag short responses (< 5 chars) and error cases for Bad Case analysis
4. Route tagged records to `flagged/YYYYMMDD/flagged_data.jsonl`
5. Aggregate clean samples into OpenAI messages-format training samples
6. Write `train_data.jsonl` and `stats.json` (with enhanced `flagged` block) to `aggregated/YYYYMMDD/`

## Format Validation

Use `validate_format.py` to verify aggregated data is compatible with LlamaFactory and other fine-tuning frameworks:

```bash
python -m deerflow_extensions.data_collection.scripts.validate_format \
    /data/deerflow/training_logs/aggregated/20260428/train_data.jsonl
```

Validation rules:
- **Rule1**: `messages` field must be a non-empty list
- **Rule2**: Each message must have a valid role (`system`/`user`/`assistant`/`tool`)
- **Rule3**: At least one `user` and one `assistant` message required
- **Rule4**: `tool_calls` only allowed on `assistant` messages
- **Rule5**: `tool_calls` entries must have valid `function.arguments` (JSON string)
- **Rule6**: Every `tool_call_id` in `tool` messages must have a matching assistant `tool_calls` entry
- **Rule7**: Each line must be valid JSON

Export to other formats:

```bash
python -c "
from deerflow_extensions.data_collection.scripts import export_dataset
export_dataset(
    '/data/deerflow/training_logs/aggregated/20260428/train_data.jsonl',
    '/data/deerflow/training_logs/aggregated/20260428/train_data_sharegpt.jsonl',
    format='sharegpt'
)
"
```

Supported formats: `llamafactory_messages` (pass-through), `sharegpt`, `alpaca_simple`.

## Uninstallation

Delete the 3-line import block from `backend/app/gateway/app.py`:

```python
# Data collection system (zero-injection, monkey-patch based)
try:
    from deerflow_extensions.data_collection.startup import install_data_collection
    install_data_collection()
except ImportError:
    pass
```

No other files are modified. The data collection directory and accumulated logs can be removed separately.

## Caveats

- Integration testing requires a running DeerFlow environment (LangGraph agent, FastAPI gateway) to validate end-to-end data flow.
- The monkey-patch (`install_data_collection`) must be called before any agent middleware chain is built -- importing at module level in `app.py` is the safest approach.
- If the package is not installed, the `try/except ImportError` guarantees zero impact on DeerFlow operations.
- Collected data lives on local disk; set up external backup/offload for production deployments.
- The collector uses thread-safe buffering with `threading.Lock` to support concurrent writes from multiple sessions.
- Middleware methods support both sync and async execution paths for full LangGraph compatibility.

WING
