"""Distillation data cleaning and aggregation pipeline.

Transforms daily raw JSONL logs into OpenAI messages-format training data.
"""

import json
import os
import hashlib
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any


class DataCleaner:
    """Cleans raw collected samples through configurable filtering stages."""

    @staticmethod
    def deduplicate(samples: list[dict]) -> list[dict]:
        """Remove duplicate samples based on (user_query + model_response) hash."""
        seen: set[str] = set()
        result: list[dict] = []
        for s in samples:
            user_query = s.get("user_query", "") or ""
            raw_response = s.get("raw_response", "") or ""
            key = user_query + raw_response
            if not key:
                result.append(s)
                continue
            h = hashlib.md5(key.encode("utf-8")).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(s)
        return result

    @staticmethod
    def filter_incomplete(samples: list[dict]) -> list[dict]:
        """Filter out samples missing session_id, user_query, or raw_response."""
        result: list[dict] = []
        for s in samples:
            if not s.get("session_id"):
                continue
            if not s.get("user_query"):
                continue
            if not s.get("raw_response"):
                continue
            result.append(s)
        return result

    @staticmethod
    def tag_short_response(samples: list[dict], min_chars: int = 5) -> list[dict]:
        """Tag samples with short_reply=True instead of discarding."""
        for s in samples:
            raw = s.get("raw_response", "") or ""
            if len(raw) < min_chars:
                s["short_reply"] = True
        return samples

    @staticmethod
    def tag_errors(samples: list[dict]) -> list[dict]:
        """Tag samples with has_error=True for error records instead of discarding."""
        for s in samples:
            if s.get("error"):
                s["has_error"] = True
        return samples

    @classmethod
    def process(cls, samples: list[dict]) -> tuple[list[dict], list[dict]]:
        """Tag and route samples into clean (trainable) and flagged (analysis) streams.

        Returns:
            (clean, flagged):  clean samples for training, flagged samples
            for Bad Case / quality analysis. All flagged records are preserved.
        """
        s = cls.filter_incomplete(samples[:])
        s = cls.deduplicate(s)
        s = cls.tag_short_response(s)
        s = cls.tag_errors(s)

        clean: list[dict] = []
        flagged: list[dict] = []

        for record in s:
            if record.get("has_error") or record.get("short_reply"):
                flagged.append(record)
            else:
                clean.append(record)

        return clean, flagged


class DataAggregator:
    """Aggregates cleaned samples into OpenAI messages-format training data."""

    @staticmethod
    def aggregate_session(samples: list[dict]) -> list[dict]:
        """Group samples by session_id, sort by create_time, build training samples."""
        grouped: dict[str, list[dict]] = defaultdict(list)
        for s in samples:
            sid = s.get("session_id")
            if sid:
                grouped[sid].append(s)

        result: list[dict] = []
        for sid, group in grouped.items():
            group.sort(key=lambda x: x.get("create_time", ""))
            sample = DataAggregator._build_training_sample(group)
            if sample is not None:
                result.append(sample)
        return result

    @staticmethod
    def _build_training_sample(samples: list[dict]) -> dict | None:
        """Convert a list of same-session raw samples into OpenAI messages format.

        Returns None if fewer than 2 messages are produced.
        """
        messages: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}

        for s in samples:
            sample_type = s.get("sample_type", "")

            if sample_type == "agent_input":
                system_prompt = (s.get("system_prompt") or "").strip()
                user_query = (s.get("user_query") or "").strip()

                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                if user_query:
                    messages.append({"role": "user", "content": user_query})

                if not metadata:
                    metadata["session_id"] = s.get("session_id", "")
                    metadata["create_time"] = s.get("create_time", "")

            elif sample_type == "model_output":
                raw_response = (s.get("raw_response") or "").strip()
                tool_calls_raw = s.get("tool_calls") or []
                response_type = s.get("response_type", "text")

                if tool_calls_raw and response_type == "tool_calls":
                    assistant_msg: dict[str, Any] = {
                        "role": "assistant",
                        "content": raw_response or None,
                    }
                    openai_tool_calls: list[dict[str, Any]] = []
                    for tc in tool_calls_raw:
                        args = tc.get("arguments", {})
                        if isinstance(args, dict):
                            args = json.dumps(args, ensure_ascii=False, sort_keys=True)
                        openai_tool_calls.append({
                            "id": tc.get("call_id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("tool_name", ""),
                                "arguments": args,
                            },
                        })
                    assistant_msg["tool_calls"] = openai_tool_calls
                    messages.append(assistant_msg)
                else:
                    if raw_response:
                        messages.append({"role": "assistant", "content": raw_response})

            elif sample_type == "tool_call_result":
                result_data = s.get("result")
                content = (
                    json.dumps(result_data, ensure_ascii=False, sort_keys=True)
                    if result_data is not None
                    else ""
                )
                messages.append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": s.get("call_id", ""),
                })

        if len(messages) < 2:
            return None

        return {"messages": messages, "metadata": metadata}


def run_daily_pipeline(date_str: str | None = None) -> dict[str, Any]:
    """Execute the full ETL pipeline for a given date.

    Loads → cleans → aggregates → writes training data + stats.

    Args:
        date_str: Date string in YYYYMMDD format. Defaults to current UTC date.

    Returns:
        Dictionary with pipeline statistics (raw_count, cleaned_count, etc.).

    Raises:
        FileNotFoundError: if the daily JSONL file does not exist.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    date_str = str(date_str)

    base_dir = "/data/deerflow/training_logs"
    input_path = os.path.join(base_dir, "daily", f"train_data_{date_str}.jsonl")
    output_dir = os.path.join(base_dir, "aggregated", date_str)
    output_path = os.path.join(output_dir, "train_data.jsonl")
    stats_path = os.path.join(output_dir, "stats.json")

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Daily log file not found: {input_path}")

    raw_samples: list[dict] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw_samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    raw_count = len(raw_samples)

    cleaner = DataCleaner()
    clean_samples, flagged_samples = cleaner.process(raw_samples)
    cleaned_count = len(clean_samples)
    flagged_count = len(flagged_samples)

    aggregator = DataAggregator()
    training_samples = aggregator.aggregate_session(clean_samples)
    train_sample_count = len(training_samples)

    categories: dict[str, int] = defaultdict(int)
    for s in clean_samples:
        st = s.get("sample_type", "unknown")
        categories[st] += 1

    os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for ts in training_samples:
            f.write(json.dumps(ts, ensure_ascii=False) + "\n")

    if flagged_samples:
        flagged_output_dir = os.path.join(base_dir, "flagged", date_str)
        flagged_output_path = os.path.join(flagged_output_dir, "flagged_data.jsonl")
        os.makedirs(flagged_output_dir, exist_ok=True)
        with open(flagged_output_path, "w", encoding="utf-8") as f:
            for rec in flagged_samples:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    error_tag_counts: dict[str, int] = {}
    short_reply_count = 0
    for rec in flagged_samples:
        if rec.get("has_error"):
            error_type = rec.get("error", "unknown")
            error_tag_counts[error_type] = error_tag_counts.get(error_type, 0) + 1
        if rec.get("short_reply"):
            short_reply_count += 1

    stats = {
        "date": date_str,
        "raw_count": raw_count,
        "cleaned_count": cleaned_count,
        "flagged_count": flagged_count,
        "train_sample_count": train_sample_count,
        "categories": dict(categories),
        "flagged": {
            "total": flagged_count,
            "short_reply": short_reply_count,
            "error_count": sum(error_tag_counts.values()),
            "error_breakdown": error_tag_counts,
        },
    }
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return stats


if __name__ == "__main__":
    import sys

    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        result = run_daily_pipeline(date_arg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)
