"""Phase A2 tests: recovery parsing, the capability matrix, and the holdout guard.

No test here touches the network. The archive client is exercised through a
stubbed transport, so the suite is deterministic and runs offline.
"""

from __future__ import annotations

import io
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from tools.strategy_factory_v2 import holdout as H
from tools.strategy_factory_v2.ingest import (
    ABSENT,
    AVAILABLE,
    UNKNOWN,
    capability_matrix,
)
from tools.strategy_factory_v2.recovery import (
    KLINE_COLUMNS,
    METRICS_COLUMNS,
    BinanceArchive,
    DatasetSpec,
    RecoveryError,
    parse_kline,
    parse_metrics,
    parse_reference_kline,
)


# ---------------------------------------------------------------------------
# Synthetic archive builders
# ---------------------------------------------------------------------------


def _zip_bytes(name: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(name, text)
    return buffer.getvalue()


def _kline_csv(rows: int = 5, header: bool = True) -> str:
    lines = []
    if header:
        lines.append(",".join(KLINE_COLUMNS))
    base = 1_580_515_200_000
    for i in range(rows):
        values = [
            base + i * 3_600_000,
            100.0 + i,
            101.0 + i,
            99.0 + i,
            100.5 + i,
            10.0 + i,
            base + (i + 1) * 3_600_000 - 1,
            1000.0 + i,
            100 + i,
            6.0 + i,   # taker_buy_volume
            600.0 + i, # taker_buy_quote_volume
            0,
        ]
        lines.append(",".join(str(v) for v in values))
    return "\n".join(lines) + "\n"


def _metrics_csv(rows: int = 6, header: bool = True, unordered: bool = True) -> str:
    lines = []
    if header:
        lines.append(",".join(METRICS_COLUMNS))
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    stamps = [base + timedelta(minutes=5 * i) for i in range(rows)]
    if unordered:
        stamps = list(reversed(stamps))
    for stamp in stamps:
        values = [
            stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "BTCUSDT",
            1_000_000.0 + stamp.minute,
            5_000_000_000.0 + stamp.minute,
            1.05,
            2.10,
            0.95,
            1.02,
        ]
        lines.append(",".join(str(v) for v in values))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def test_parse_kline_handles_the_headered_format() -> None:
    blob = _zip_bytes("BTCUSDT-1h-2024-01.csv", _kline_csv(header=True))
    frame = parse_kline(blob, "BTCUSDT", "1h", "k")
    assert len(frame) == 5
    assert bool(frame["csv_had_header"].all())
    assert frame["date"].is_monotonic_increasing
    assert frame["date"].dt.tz is not None


def test_parse_kline_handles_the_headerless_format() -> None:
    # Binance published klines positionally with no header for the early years.
    blob = _zip_bytes("BTCUSDT-1h-2020-01.csv", _kline_csv(header=False))
    frame = parse_kline(blob, "BTCUSDT", "1h", "k")
    assert len(frame) == 5
    assert not bool(frame["csv_had_header"].any())
    assert frame["date"].is_monotonic_increasing
    assert frame["close"].notna().all()


def test_parse_kline_derives_taker_sell_exactly() -> None:
    blob = _zip_bytes("x.csv", _kline_csv(rows=3, header=True))
    frame = parse_kline(blob, "BTCUSDT", "1h", "k")
    expected = frame["volume"] - frame["taker_buy_volume"]
    assert (frame["taker_sell_volume"] - expected).abs().max() < 1e-12
    # The derived leg must never go negative: taker buy cannot exceed volume.
    assert (frame["taker_sell_volume"] >= 0).all()


def test_parse_kline_rejects_a_file_without_usable_columns() -> None:
    blob = _zip_bytes("x.csv", "a,b,c\n1,2,3\n")
    try:
        parse_kline(blob, "BTCUSDT", "1h", "bad")
    except RecoveryError as error:
        assert "missing kline columns" in str(error)
        return
    raise AssertionError("a file without the required columns must be rejected")


def test_parse_metrics_sorts_an_unsorted_source() -> None:
    # The published files are not in chronological order.
    blob = _zip_bytes("BTCUSDT-metrics-2024-01-01.csv", _metrics_csv(rows=8, unordered=True))
    frame = parse_metrics(blob, "BTCUSDT", "k")
    assert len(frame) == 8
    assert frame["timestamp"].is_monotonic_increasing, "metrics must be sorted on ingest"
    assert frame["open_interest"].notna().all()


def test_parse_metrics_preserves_the_irregular_grid() -> None:
    # 288 irregular samples per day is not a clean 5-minute grid. Snapping it to
    # one would assert a precision the source does not have.
    blob = _zip_bytes("m.csv", _metrics_csv(rows=10))
    frame = parse_metrics(blob, "BTCUSDT", "k")
    gaps = frame["timestamp"].diff().dt.total_seconds().div(60).dropna().unique()
    assert set(gaps.tolist()) == {5.0}


def test_parse_reference_kline_keeps_the_close_as_the_price() -> None:
    blob = _zip_bytes("i.csv", _kline_csv(rows=4, header=True))
    frame = parse_reference_kline(blob, "BTCUSDT", "1h", "k", "index_price")
    assert "index_price" in frame.columns
    assert frame["index_price"].notna().all()
    assert frame["index_price"].iloc[0] == 100.5


# ---------------------------------------------------------------------------
# Archive client (stubbed transport -- no network)
# ---------------------------------------------------------------------------


class _StubArchive(BinanceArchive):
    """Serves a canned page sequence instead of contacting S3."""

    def __init__(self, payloads, sidecars=None):
        super().__init__(retries=1, backoff=0.0)
        self.payloads = list(payloads)
        self.sidecars = sidecars or {}
        self.requested: list[str] = []
        self._cursor = 0

    def _get(self, url):
        self.requested.append(url)
        if url.endswith(".CHECKSUM"):
            key = url.split("/data.binance.vision/")[-1][: -len(".CHECKSUM")]
            if key in self.sidecars:
                return self.sidecars[key].encode()
            raise RecoveryError("no sidecar")
        if self._cursor >= len(self.payloads):
            raise RecoveryError("stub exhausted")
        payload = self.payloads[self._cursor]
        self._cursor += 1
        return payload


def _page(keys, truncated):
    contents = "".join(
        f"<Contents><Key>{k}</Key><LastModified>2024-01-01T00:00:00.000Z</LastModified>"
        f"<ETag>&quot;x&quot;</ETag><Size>10</Size></Contents>"
        for k in keys
    )
    truncated_flag = "true" if truncated else "false"
    return f"<?xml version='1.0'?><ListBucketResult>{contents}<IsTruncated>{truncated_flag}</IsTruncated></ListBucketResult>"


def test_list_follows_pagination() -> None:
    # Without the marker the result silently truncates, which is how a coverage
    # report ends up claiming 500 days when 2215 exist.
    page_one = _page(["data/x/a-1.zip", "data/x/a-2.zip"], truncated=True)
    page_two = _page(["data/x/a-3.zip"], truncated=False)
    client = _StubArchive([page_one.encode(), page_two.encode()])
    files = client.list("data/x/")
    assert [f.key for f in files] == ["data/x/a-1.zip", "data/x/a-2.zip", "data/x/a-3.zip"]
    assert any("marker=" in url for url in client.requested), "the marker must be followed"


def test_list_parses_entries_whose_fields_differ() -> None:
    # An entry without an ETag must still be listed. A strict whole-block regex
    # drops it, and the page count then drives an early stop.
    xml = (
        "<ListBucketResult><Contents><Key>data/x/a-1.zip</Key>"
        "<LastModified>2024-01-01T00:00:00.000Z</LastModified><Size>10</Size></Contents>"
        "<IsTruncated>false</IsTruncated></ListBucketResult>"
    )
    files = _StubArchive([xml.encode()]).list("data/x/")
    assert [f.key for f in files] == ["data/x/a-1.zip"]


def test_fetch_verified_raises_on_checksum_mismatch() -> None:
    import hashlib

    payload = b"PK\x03\x04not-really-a-zip"
    client = _StubArchive([payload], sidecars={"data/x/a.zip": f"{'0' * 64}  a.zip"})
    with tempfile.TemporaryDirectory() as tmp:
        destination = Path(tmp) / "a.zip"
        try:
            client.fetch_verified("data/x/a.zip", destination)
        except RecoveryError as error:
            assert "checksum mismatch" in str(error)
            assert not destination.exists(), "an unverified file must not be kept"
            return
    raise AssertionError("a checksum mismatch must raise and the file must not be trusted")


def test_fetch_verified_records_a_missing_sidecar_rather_than_passing() -> None:
    import hashlib

    payload = b"PK\x03\x04not-really-a-zip"
    client = _StubArchive([payload], sidecars={})
    with tempfile.TemporaryDirectory() as tmp:
        record = client.fetch_verified("data/x/a.zip", Path(tmp) / "a.zip")
    assert record["checksum_status"] == "checksum_unavailable"
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()


def test_dataset_prefix_for_metrics_has_no_interval_folder() -> None:
    # ``metrics`` is published per symbol only; there is no interval folder and
    # no monthly tree, so a spec that assumes one silently finds nothing.
    metrics = DatasetSpec(kind="metrics", symbol="BTCUSDT", interval="5m", start="2020-01-01", end="2026-01-01")
    assert metrics.prefix == "data/futures/um/daily/metrics/BTCUSDT/"
    klines = DatasetSpec(kind="klines", symbol="BTCUSDT", interval="1h", start="2020-01-01", end="2026-01-01")
    assert klines.prefix == "data/futures/um/monthly/klines/BTCUSDT/1h/"


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------


def _isolated_canonical(function, *args, **kwargs):
    """Run ``function`` against an empty canonical tree.

    The matrix reads the real ``user_data/data/binance_v2/canonical`` directory,
    which a recovery run may be filling concurrently. Without this the tests
    would assert against whatever the downloader happened to have written.
    """

    import tools.strategy_factory_v2.ingest as ingest_module

    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "canonical"
        original = ingest_module.CANONICAL_DIR
        ingest_module.CANONICAL_DIR = empty
        try:
            return function(*args, **kwargs)
        finally:
            ingest_module.CANONICAL_DIR = original


def test_capability_matrix_keeps_unknown_distinct_from_absent() -> None:
    matrix = _isolated_canonical(
        capability_matrix,
        ["BTCUSDT"],
        {
            "open_interest": {"BTCUSDT": True},   # published remotely, not ingested
            "index_price": {"BTCUSDT": False},   # probed and confirmed absent
            "mark_price": {},                    # never probed at all
        },
    )
    row = matrix.iloc[0]
    # Published remotely but not fetched yet -> UNKNOWN, never ABSENT.
    assert row["open_interest_status"] == UNKNOWN
    # Probed and confirmed not published -> ABSENT.
    assert row["index_price_status"] == ABSENT
    # Never probed -> UNKNOWN.
    assert row["mark_price_status"] == UNKNOWN


def test_capability_matrix_reports_no_rows_for_unavailable_fields() -> None:
    row = _isolated_canonical(capability_matrix, ["BTCUSDT"], {}).iloc[0]
    assert row["open_interest_rows"] == 0
    assert row["open_interest_start"] == ""
    assert row["open_interest_status"] in (UNKNOWN, ABSENT, AVAILABLE)


def test_capability_matrix_requires_both_index_and_mark_for_basis() -> None:
    import tools.strategy_factory_v2.ingest as ingest_module

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "canonical"
        (root / "index_price").mkdir(parents=True)
        (root / "mark_price").mkdir(parents=True)
        stamps = pd.date_range("2024-01-01", periods=10, freq="1h", tz="UTC")
        pd.DataFrame({"timestamp": stamps, "index_price": 100.0}).to_feather(
            root / "index_price" / "BTCUSDT_1h.feather"
        )
        original = ingest_module.CANONICAL_DIR
        ingest_module.CANONICAL_DIR = root
        try:
            only_index = capability_matrix(["BTCUSDT"], {})
            # mark is missing, so basis must not be reported as available.
            assert only_index.iloc[0]["basis_status"] == ABSENT
            pd.DataFrame({"timestamp": stamps, "mark_price": 100.1}).to_feather(
                root / "mark_price" / "BTCUSDT_1h.feather"
            )
            both = capability_matrix(["BTCUSDT"], {})
            assert both.iloc[0]["basis_status"] == AVAILABLE
        finally:
            ingest_module.CANONICAL_DIR = original


def test_capability_matrix_reports_available_once_a_dataset_is_ingested() -> None:
    import tools.strategy_factory_v2.ingest as ingest_module

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "canonical"
        (root / "open_interest").mkdir(parents=True)
        stamps = pd.date_range("2024-01-01", periods=10, freq="5min", tz="UTC")
        pd.DataFrame({"timestamp": stamps, "open_interest": 1000.0}).to_feather(
            root / "open_interest" / "BTCUSDT_5m.feather"
        )
        original = ingest_module.CANONICAL_DIR
        ingest_module.CANONICAL_DIR = root
        try:
            row = capability_matrix(["BTCUSDT"], {}).iloc[0]
        finally:
            ingest_module.CANONICAL_DIR = original
    assert row["open_interest_status"] == AVAILABLE
    assert int(row["open_interest_rows"]) == 10
    assert str(row["open_interest_start"]).startswith("2024-01-01")


# ---------------------------------------------------------------------------
# Holdout guard
# ---------------------------------------------------------------------------


def _partition() -> H.DataPartition:
    return H.DataPartition(
        development_start="2021-01-01 00:00:00+00:00",
        development_end="2025-05-01 00:00:00+00:00",
        validation_start="2025-05-01 00:00:00+00:00",
        validation_end="2025-11-18 00:00:00+00:00",
        holdout_start="2025-11-19 00:00:00+00:00",
        holdout_end="2026-08-31 00:00:00+00:00",
        latest_complete_day="2026-08-31",
    )


def _frame(start: str, periods: int) -> pd.DataFrame:
    return pd.DataFrame(
        {"date": pd.date_range(start, periods=periods, freq="1h", tz="UTC"), "close": 1.0}
    )


def test_development_frame_ending_before_the_boundary_is_accepted() -> None:
    frame = _frame("2025-11-01", periods=100)  # ends 2025-11-05
    H.assert_development_window(frame, _partition())


def test_development_frame_crossing_the_boundary_is_refused() -> None:
    frame = _frame("2025-11-18", periods=48)  # runs into the holdout
    try:
        H.assert_development_window(frame, _partition(), context="unit-test")
    except H.HoldoutViolation as error:
        assert "FINAL HOLDOUT" in str(error)
        assert "unit-test" in str(error)
        return
    raise AssertionError("a frame reaching into the holdout must be refused")


def test_split_for_development_can_never_return_the_holdout() -> None:
    frame = _frame("2025-01-01", periods=24 * 240)  # Jan-Aug 2025, inside development
    parts = H.split_for_development(frame, _partition())
    assert set(parts) == {H.DEVELOPMENT, H.VALIDATION}
    boundary = pd.Timestamp(_partition().holdout_start)
    for name, part in parts.items():
        if part.empty:
            continue
        assert part["date"].max() < boundary, f"{name} reached into the holdout"
    assert len(parts[H.DEVELOPMENT]) + len(parts[H.VALIDATION]) == len(frame)


def test_open_holdout_demands_a_justification_and_a_frozen_spec() -> None:
    frame = _frame("2025-11-19", periods=48)
    with tempfile.TemporaryDirectory() as tmp:
        lock = Path(tmp) / "lock.json"
        for justification, spec_version in (("", "spec"), ("why", ""), ("  ", "  ")):
            try:
                H.open_holdout(frame, _partition(), justification, spec_version, lock_path=lock)
            except H.HoldoutViolation:
                continue
            raise AssertionError(
                f"opening the holdout with justification={justification!r} "
                f"spec_version={spec_version!r} must be refused"
            )
        # A complete request is allowed, and the access is logged.
        allowed = H.open_holdout(
            frame, _partition(), "unit test", "test-spec", lock_path=lock
        )
        assert len(allowed) == 48
        logged = json.loads(lock.read_text(encoding="utf-8"))["access_log"]
        assert len(logged) == 1
        assert logged[0]["spec_version"] == "test-spec"


def test_open_holdout_never_writes_to_the_production_lock() -> None:
    # A test that appends to the real access log makes the boundary's own audit
    # trail say something untrue. This pins the injection point.
    production = Path("user_data/data/binance_v2/FINAL_HOLDOUT_DO_NOT_TOUCH.json")
    before = production.read_bytes() if production.exists() else None
    with tempfile.TemporaryDirectory() as tmp:
        H.open_holdout(
            _frame("2025-11-19", periods=4),
            _partition(),
            "unit test",
            "test-spec",
            lock_path=Path(tmp) / "lock.json",
        )
    after = production.read_bytes() if production.exists() else None
    assert before == after, "the production holdout lock was modified by a test"


def test_latest_complete_day_is_derived_from_the_data_not_the_clock() -> None:
    # A series reaching 23:00 on its final day: that day is complete.
    frame = pd.DataFrame(
        {"date": pd.date_range("2024-01-01 00:00", periods=72, freq="1h", tz="UTC")}
    )
    assert H.latest_complete_day(frame) == "2024-01-03"
    # A trailing fragment must not be reported as a complete day.
    fragment = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-10 00:00", "2024-01-11 03:00"], utc=True)}
    )
    assert H.latest_complete_day(fragment) == "2024-01-10"


def test_latest_complete_day_never_returns_today() -> None:
    now = pd.Timestamp(datetime.now(timezone.utc))
    # Even a series that runs right up to the current moment must yield a day
    # that is already finished.
    stamps = pd.date_range(
        now - pd.Timedelta(days=5), now.floor("D") + pd.Timedelta(hours=1), freq="1h", tz="UTC"
    )
    frame = pd.DataFrame({"date": stamps})
    result = H.latest_complete_day(frame)
    assert result < now.strftime("%Y-%m-%d"), f"{result} is not in the past"


def test_partition_declares_three_disjoint_regions() -> None:
    partition = _partition()
    assert partition.region_of("2021-06-01") == H.DEVELOPMENT
    assert partition.region_of("2025-08-01") == H.VALIDATION
    assert partition.region_of("2026-01-15") == H.FINAL_HOLDOUT
    assert (
        pd.Timestamp(partition.development_end) < pd.Timestamp(partition.validation_start) + pd.Timedelta(seconds=1)
    )
    assert pd.Timestamp(partition.validation_end) < pd.Timestamp(partition.holdout_start)


def test_lock_file_records_the_boundary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lock.json"
        H.write_lock(_partition(), path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["partition"]["holdout_start"] == "2025-11-19 00:00:00+00:00"
        assert any("never" in rule.lower() or "No development" in rule for rule in payload["rules"])


# ---------------------------------------------------------------------------
# The registry must not have moved
# ---------------------------------------------------------------------------


def test_recovering_data_did_not_change_the_preregistered_registry() -> None:
    # Acquiring data unlocks preregistered families. It does not license new
    # hypotheses, and the count is frozen in a test precisely so that the
    # temptation to grow it is visible rather than invisible.
    from tools.strategy_factory_v2.hypotheses import EXPECTED_HYPOTHESIS_COUNT, HYPOTHESES

    assert len(HYPOTHESES) == EXPECTED_HYPOTHESIS_COUNT == 92


def test_recovered_capability_unblocks_oi_families() -> None:
    from tools.strategy_factory_v2.hypotheses import BLOCKED, TESTABLE, HYPOTHESES, status_for

    full = {
        "funding_rate": AVAILABLE,
        "open_interest": AVAILABLE,
        "mark_price": AVAILABLE,
        "index_price": AVAILABLE,
        "taker_buy_volume": AVAILABLE,
        "taker_sell_volume": AVAILABLE,
    }
    still_blocked = [
        h.hypothesis_id
        for h in HYPOTHESES
        if status_for(h, full, ["BTCUSDT", "ETHUSDT"], price_available=True) == BLOCKED
    ]
    assert not still_blocked, still_blocked
    assert all(
        status_for(h, full, ["BTCUSDT", "ETHUSDT"], price_available=True) == TESTABLE
        for h in HYPOTHESES
    )


def test_matrix_to_registry_field_translation_is_complete() -> None:
    # The two modules name the same fields differently. Guessing the mapping
    # left every funding and taker-flow family reported BLOCKED against a fully
    # recovered dataset -- a wrong "no" that reads exactly like a real one.
    from tools.strategy_factory_v2.hypotheses import CANONICAL_FIELDS
    from tools.strategy_factory_v2.ingest import (
        CANONICAL_FIELDS as MATRIX_FIELDS,
        MATRIX_TO_REGISTRY_FIELDS,
        registry_field_status,
    )

    assert set(MATRIX_TO_REGISTRY_FIELDS) == set(MATRIX_FIELDS) - {"basis"}, (
        "every ingested field needs a mapping; 'basis' is the one exception "
        "because it is derived from index and mark rather than fetched"
    )
    covered = {f for fields in MATRIX_TO_REGISTRY_FIELDS.values() for f in fields}
    # These are exactly the names ``available_fields`` consults when it decides
    # whether a hypothesis is testable. ``price``/``volume`` come from the price
    # frame and ``cross_asset`` is the ability to compare two symbols, so none
    # of the three is a dataset column. ``taker_flow`` is the declared name but
    # the gate reads both legs separately, because the imbalance divides by
    # their sum and one leg alone is not usable.
    expected = {
        "funding_rate",
        "open_interest",
        "index_price",
        "mark_price",
        "taker_buy_volume",
        "taker_sell_volume",
    }
    assert covered == expected, f"unmapped: {expected - covered}; unknown: {covered - expected}"

    from tools.strategy_factory_v2.hypotheses import available_fields

    assert available_fields(
        {name: AVAILABLE for name in expected}, price_available=True
    ) >= {"funding_rate", "open_interest", "index_price", "mark_price", "taker_flow"}


def test_registry_field_status_unblocks_a_fully_recovered_matrix() -> None:
    from tools.strategy_factory_v2.hypotheses import BLOCKED, HYPOTHESES, status_for
    from tools.strategy_factory_v2.ingest import registry_field_status

    matrix = pd.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                **{f"{name}_status": AVAILABLE for name in
                   ("price", "funding", "open_interest", "taker_flow", "index_price", "mark_price")},
            }
        ]
    )
    fields = registry_field_status(matrix)
    assert fields["funding_rate"] == AVAILABLE
    assert fields["taker_buy_volume"] == AVAILABLE
    assert fields["taker_sell_volume"] == AVAILABLE
    assert fields["open_interest"] == AVAILABLE
    blocked = [
        h.hypothesis_id
        for h in HYPOTHESES
        if status_for(h, fields, ["BTCUSDT", "ETHUSDT"], price_available=True) == BLOCKED
    ]
    assert not blocked, f"a fully recovered matrix still blocks: {blocked}"
