import json
import sys
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from pathlib import Path

INPUT_PATH = "orderbook_mock.json"
OUTPUT_PATH = "data/testdata.orderbook.parquet"

def build_schema(symbols: list[str]) -> pa.Schema:
    return pa.schema([
        ("datetime", pa.timestamp("ns", tz="Asia/Kolkata")),
        *[(symbol, pa.string()) for symbol in symbols],
    ])


def convert(input_path: str, output_path: str) -> None:
    input_file  = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        print(f"Error: input file not found: {input_file}")
        sys.exit(1)

    with input_file.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        print("Error: expected a top-level JSON object with symbols as keys")
        sys.exit(1)

    symbols = list(raw.keys())

    # Collect all unique timestamps across all symbols
    all_timestamps = sorted({
        ts
        for symbol_ticks in raw.values()
        for ts in symbol_ticks.keys()
    })

    # Build DataFrame: rows = timestamps, columns = symbols, missing = ""
    df = pd.DataFrame(index=all_timestamps, columns=symbols, dtype=str)
    df.index.name = "datetime"

    for symbol, ticks in raw.items():
        for ts, tick in ticks.items():
            df.at[ts, symbol] = json.dumps(tick)

    df = df.reset_index()
    df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize("Asia/Kolkata")

    schema = build_schema(symbols)
    table  = pa.Table.from_pandas(df, schema=schema, preserve_index=False)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_file)

    print(f"Done: {len(df)} timestamps x {len(symbols)} symbols -> {output_file}")


if __name__ == "__main__":
    convert(INPUT_PATH, OUTPUT_PATH)