"""Brutal/extreme test cases for tag-routing pipeline.

Covers: empty inputs, all-error, all-short, all-duplicate, mixed, boundary,
idempotency, error_breakdown accuracy, double-tag scenarios.

WING
"""

from deerflow_extensions.data_collection.scripts.clean_and_aggregate import DataCleaner


def make(session_id="s1", user_query="Hello", raw_response="Hi there!", sample_type="agent_input",
         create_time="2026-01-01T00:00:00", system_prompt="", tool_calls=None, error=None,
         call_id=None, result=None, response_type="text"):
    d = {"session_id": session_id, "user_query": user_query, "raw_response": raw_response,
         "sample_type": sample_type, "create_time": create_time, "system_prompt": system_prompt}
    if tool_calls is not None: d["tool_calls"] = tool_calls
    if error is not None: d["error"] = error
    if call_id is not None: d["call_id"] = call_id
    if result is not None: d["result"] = result
    if response_type: d["response_type"] = response_type
    return d


class TestEmptyAndExtremeInputs:
    """空输入和极端输入测试"""

    def test_empty_list(self):
        clean, flagged = DataCleaner.process([])
        assert clean == []
        assert flagged == []

    def test_all_empty_records(self):
        samples = [make(user_query="", session_id="") for _ in range(10)]
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 0

    def test_all_errors(self):
        samples = [
            make(error="ToolTimeout", user_query="q1", raw_response="longer_r1"),
            make(error="ToolTimeout", user_query="q2", raw_response="longer_r2"),
            make(error="ToolTimeout", user_query="q3", raw_response="longer_r3"),
            make(error="APIError", user_query="q4", raw_response="longer_r4"),
            make(error="APIError", user_query="q5", raw_response="longer_r5"),
            make(error="ConnectionError", user_query="q6", raw_response="longer_r6"),
            make(error="", user_query="q7", raw_response="longer_r7"),
            make(error=None, user_query="q8", raw_response="longer_r8"),
        ]
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 2  # only the two without error
        assert len(flagged) == 6

    def test_all_short_replies(self):
        samples = [make(user_query=f"q{i}", raw_response="ok") for i in range(20)]
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 0
        assert len(flagged) == 20
        assert all(r.get("short_reply") for r in flagged)

    def test_all_duplicates(self):
        samples = [make(user_query="same", raw_response="Same response text here") for _ in range(50)]
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 1

    def test_mixed_1000_records(self):
        """1000 条混合数据：正常(500) + 错误(200) + 短回复(200) + 空记录(100)"""
        samples = []
        for i in range(500):
            samples.append(make(user_query=f"q{i}", raw_response=f"This is a long response {i}", session_id=f"s{i}"))
        for i in range(200):
            samples.append(make(user_query=f"eq{i}", raw_response=f"error resp {i}", session_id=f"es{i}", error="ToolTimeout"))
        for i in range(200):
            samples.append(make(user_query=f"sq{i}", raw_response="ok", session_id=f"ss{i}"))
        for i in range(100):
            samples.append(make(user_query="", raw_response="", session_id=f"empty{i}"))
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 500
        assert len(flagged) == 400  # 200 error + 200 short reply


class TestBoundaryValues:
    """边界值测试"""

    def test_short_reply_exactly_5(self):
        samples = [make(raw_response="Hello")]
        result = DataCleaner.tag_short_response(samples)
        assert "short_reply" not in result[0]

    def test_short_reply_4_chars(self):
        samples = [make(raw_response="Hell")]
        result = DataCleaner.tag_short_response(samples)
        assert result[0]["short_reply"] is True

    def test_short_reply_1_char(self):
        samples = [make(raw_response="x")]
        result = DataCleaner.tag_short_response(samples)
        assert result[0]["short_reply"] is True

    def test_short_reply_0_chars(self):
        samples = [make(raw_response="")]
        result = DataCleaner.tag_short_response(samples)
        assert result[0]["short_reply"] is True

    def test_min_chars_0(self):
        """min_chars=0 时所有记录都有非空回复"""
        samples = [make(raw_response="Hi")]
        result = DataCleaner.tag_short_response(samples, min_chars=0)
        assert "short_reply" not in result[0]

    def test_min_chars_max(self):
        """极短回复在自定义高阈值下被标记"""
        samples = [make(raw_response="A perfectly normal reply that is long enough")]
        result = DataCleaner.tag_short_response(samples, min_chars=1000)
        assert result[0]["short_reply"] is True


class TestErrorEdgeCases:
    """error 字段边界测试"""

    def test_error_none_not_tagged(self):
        samples = [make(error=None)]
        result = DataCleaner.tag_errors(samples)
        assert "has_error" not in result[0]

    def test_error_empty_string_not_tagged(self):
        samples = [make(error="")]
        result = DataCleaner.tag_errors(samples)
        assert "has_error" not in result[0]

    def test_error_whitespace_only_tagged(self):
        samples = [make(error="   ")]
        result = DataCleaner.tag_errors(samples)
        assert result[0]["has_error"] is True

    def test_error_special_chars(self):
        samples = [make(error="Error: ❌ Timeout ⏱️")]
        result = DataCleaner.tag_errors(samples)
        assert result[0]["has_error"] is True
        assert result[0]["error"] == "Error: ❌ Timeout ⏱️"

    def test_error_long_string(self):
        long_err = "x" * 10000
        samples = [make(error=long_err)]
        result = DataCleaner.tag_errors(samples)
        assert result[0]["has_error"] is True


class TestIdempotency:
    """幂等性测试"""

    def test_tag_errors_idempotent(self):
        samples = [make(error="timeout"), make(error=""), make(error=None)]
        r1 = DataCleaner.tag_errors(samples)
        r2 = DataCleaner.tag_errors(r1)
        assert len(r1) == len(r2)
        assert sum(1 for r in r1 if r.get("has_error")) == sum(1 for r in r2 if r.get("has_error"))

    def test_tag_short_response_idempotent(self):
        samples = [make(raw_response="Hi"), make(raw_response="A long enough reply here")]
        r1 = DataCleaner.tag_short_response(samples)
        r2 = DataCleaner.tag_short_response(r1)
        assert sum(1 for r in r1 if r.get("short_reply")) == sum(1 for r in r2 if r.get("short_reply"))

    def test_process_idempotent(self):
        samples = [
            make(error="timeout"),
            make(user_query="q", raw_response="Good reply!"),
            make(user_query="q2", raw_response="ok"),
        ]
        c1, f1 = DataCleaner.process(samples)
        c2, f2 = DataCleaner.process(samples)
        assert len(c1) == len(c2)
        assert len(f1) == len(f2)


class TestDoubleTag:
    """同时命中多标签测试"""

    def test_error_plus_short_reply(self):
        samples = [make(error="timeout", raw_response="err")]
        clean, flagged = DataCleaner.process(samples)
        assert len(clean) == 0
        assert len(flagged) == 1
        assert flagged[0]["has_error"] is True
        assert flagged[0]["short_reply"] is True


class TestErrorBreakdownAccuracy:
    """error_breakdown 统计准确性"""

    def test_breakdown_counts(self):
        """模拟 run_daily_pipeline 中的统计逻辑"""
        samples = []
        for i in range(3):
            samples.append(make(error="ToolTimeout", user_query=f"qt{i}", raw_response=f"resp_timeout_{i}"))
        for i in range(2):
            samples.append(make(error="APIError", user_query=f"qa{i}", raw_response=f"resp_api_{i}"))
        for i in range(1):
            samples.append(make(error="ConnectionError", user_query="qc", raw_response="resp_conn"))
        clean, flagged = DataCleaner.process(samples)

        error_tag_counts = {}
        short_reply_count = 0
        for rec in flagged:
            if rec.get("has_error"):
                et = rec.get("error", "unknown")
                error_tag_counts[et] = error_tag_counts.get(et, 0) + 1
            if rec.get("short_reply"):
                short_reply_count += 1

        assert error_tag_counts == {"ToolTimeout": 3, "APIError": 2, "ConnectionError": 1}
        assert short_reply_count == 0
        assert len(flagged) == 6
        assert len(clean) == 0
