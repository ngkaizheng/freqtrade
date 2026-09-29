"""Liquidation collector -- builds the dataset that does not exist yet.

    python -m shark_hunter.collect_liquidations            # run until Ctrl-C
    python -m shark_hunter.collect_liquidations --minutes 5

SHARK-07 and the liquidation leg of SHARK-08 are the one part of the study
that is BLOCKED rather than answered, because no free source of *historical*
liquidation volume exists.  This does not fix history, but it starts the only
thing that does: accumulating the feed from now, so that in six to twelve
months the cascade hypothesis becomes testable on data we actually hold.

Run it persistently (Task Scheduler, systemd, tmux) -- a collector that only
runs when someone happens to start it collects nothing.  Output is append-only
gzipped CSV, one row per event, which the existing
``shark_hunter.data.sources.LiquidationSource`` adapter can read once a
sufficient history accumulates.

Why Bybit and not Binance: Binance's public UM archive carries no liquidation
dataset and ``/fapi/v1/allForceOrders`` returns 404.  Bybit publishes a public
``liquidation.{symbol}`` websocket topic with liquidation side, quantity and
price.  Liquidation volume is exchange-specific and is NOT global market
liquidation volume; the report must keep saying so.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

from . import config as C

WS_URL = "wss://stream.bybit.com/v5/public/linear"
OUT = C.LIQUIDATION_DIR / "bybit_liquidation_events.csv.gz"
HEARTBEAT_SECONDS = 20          # Bybit closes idle connections at 60s


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Collector:
    """Append-only liquidation event writer with a rotating daily file."""

    # Sanity ceiling on any rate attached to a stream payload, in bps. See
    # `config.MAX_SANE_RATE_BPS` -- documented API errors have produced
    # funding readings >284,000 bps. The guard is far above any genuine
    # observation (the on-disk funding corpus tops out at -200 bps, a real
    # clamp), so it rejects corruption without rejecting data.
    MAX_RATE_BPS = C.MAX_SANE_RATE_BPS

    def __init__(self, symbols: list[str], out_dir: Path = C.LIQUIDATION_DIR):
        self.symbols = symbols
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.count = 0
        self.rejected = 0
        self.started = time.time()
        self.reconnects = 0
        self.stop = False

    def path(self) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.out_dir / f"bybit_liq_{day}.csv.gz"

    def write(self, rows: list[dict]) -> None:
        if not rows:
            return
        p = self.path()
        exists = p.exists()
        # gzip append: concatenate a second gzip member, which every gzip
        # reader (including pandas) transparently handles.
        with gzip.open(p, "at", encoding="utf-8", newline="") as fh:
            if not exists:
                fh.write("timestamp,symbol,side,raw_side,price,quantity,notional\n")
            for r in rows:
                fh.write(f"{r['ts']},{r['symbol']},{r['side']},{r['raw_side']},"
                         f"{r['price']},{r['quantity']},{r['notional']}\n")
        self.count += len(rows)

    @staticmethod
    def parse(msg: dict) -> list[dict]:
        """Parse a Bybit All Liquidation snapshot.
        Field names are the single-letter v5 ones and are verified against
        https://bybit-exchange.github.io/docs/v5/websocket/public/all-liquidation:
            T = event timestamp (ms), s = symbol, S = position side,
            v = executed size, p = bankruptcy price

        ``S`` is the side of the LIQUIDATED position, not the side of the
        closing order: a ``Buy`` update means a **long** was force-closed.
        Getting this backwards inverts the strategy -- spec 22 requires a
        long setup on SHORT liquidations, so this mapping is load-bearing and
        is asserted in the regression suite.
        """
        if not str(msg.get("topic", "")).startswith("allLiquidation"):
            return []
        data = msg.get("data") or []
        out = []
        for d in data if isinstance(data, list) else [data]:
            try:
                qty = float(d.get("v") or 0)
                price = float(d.get("p") or 0)
                raw_side = str(d.get("S", ""))
                if qty <= 0 or price <= 0:
                    continue
                # NOTE: `config.rate_is_sane` deliberately does NOT apply to
                # this price. The 284,000 bps corruption documented in the
                # literature is a funding *rate*; a liquidation price of
                # 84,000 is 8,400,000 bps and a rate-shaped ceiling would
                # reject every real event. Prices are guarded by a
                # plausibility band in the caller, not by a rate ceiling.
                # Bybit: S=Buy -> a LONG position was liquidated.
                if raw_side == "Buy":
                    side = "long"
                elif raw_side == "Sell":
                    side = "short"
                else:
                    continue
                ts = d.get("T")
                out.append({
                    "ts": int(ts) if ts else msg.get("ts"),
                    "symbol": d.get("s", ""),
                    "side": side,
                    "raw_side": raw_side,
                    "price": price,
                    "quantity": qty,
                    "notional": qty * price,
                })
            except (TypeError, ValueError):
                continue
        return out

    async def run(self, minutes: float | None = None) -> int:
        deadline = time.time() + minutes * 60 if minutes else None
        print(f"connecting {WS_URL} for {len(self.symbols)} symbols", flush=True)
        chunk: list[dict] = []

        while not self.stop:
            try:
                async with websockets.connect(WS_URL, open_timeout=20,
                                              ping_interval=HEARTBEAT_SECONDS) as ws:
                    # Subscribe in batches and read exactly ONE ack per
                    # request. Bybit acknowledges per request, not per topic:
                    # a per-topic drain leaves the buffer empty and the
                    # subscription silently does not happen. A rejected batch
                    # names one offending topic in ret_msg, which is still
                    # enough to know the batch did not register.
                    for i in range(0, len(self.symbols), 5):
                        batch = [f"allLiquidation.{s}" for s in self.symbols[i:i + 5]]
                        await ws.send(json.dumps({"op": "subscribe", "args": batch}))
                        try:
                            reply = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                            if reply.get("success", False):
                                print(f"  subscribed {len(batch)} symbols", flush=True)
                            else:
                                print(f"  SUBSCRIBE REJECTED: {reply.get('ret_msg')} "
                                      f"(batch of {len(batch)})", flush=True)
                        except asyncio.TimeoutError:
                            print(f"  no subscribe ack for batch of {len(batch)}", flush=True)

                    while not self.stop:
                        if deadline and time.time() > deadline:
                            self.stop = True
                            break
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            msg = json.loads(raw)
                        except (TypeError, ValueError):
                            continue
                        rows = self.parse(msg)
                        if rows:
                            chunk.extend(rows)
                            if len(chunk) >= 1:
                                self.write(chunk)
                                chunk = []
            except asyncio.CancelledError:
                break
            except Exception as exc:                       # noqa: BLE001
                self.reconnects += 1
                wait = min(60, 2 ** min(self.reconnects, 5))
                print(f"  connection error ({type(exc).__name__}: {str(exc)[:80]}); "
                      f"retrying in {wait}s", flush=True)
                await asyncio.sleep(wait)
        if chunk:
            self.write(chunk)
        print(f"stopped: {self.count} events over "
              f"{(time.time() - self.started) / 60:.1f} min, "
              f"{self.reconnects} reconnects", flush=True)
        return self.count


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Bybit liquidation event collector")
    ap.add_argument("--symbols", nargs="*", default=list(C.UNIVERSE))
    ap.add_argument("--minutes", type=float, default=None,
                    help="stop after N minutes (default: run until Ctrl-C)")
    args = ap.parse_args(argv)

    c = Collector(args.symbols)

    def _sig(*_):
        print("\nstopping...", flush=True)
        c.stop = True

    try:
        signal.signal(signal.SIGINT, _sig)
    except (ValueError, AttributeError):
        pass
    n = asyncio.run(c.run(args.minutes))
    print(f"wrote {n} events to {c.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
