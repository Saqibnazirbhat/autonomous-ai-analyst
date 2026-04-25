"""@data-engineer: raw creditcard.csv -> validated data/clean.parquet."""
import os
import pandas as pd

RAW = "data/creditcard.csv/creditcard.csv"
OUT = "data/clean.parquet"
EXPECTED_COLS = ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount", "Class"]


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    assert df.shape == (284807, 31), f"shape mismatch: {df.shape}"
    assert list(df.columns) == EXPECTED_COLS, f"columns mismatch: {list(df.columns)}"
    return df


def coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["Time"] + [f"V{i}" for i in range(1, 29)] + ["Amount"]:
        df[col] = df[col].astype("float64")
    df["Class"] = df["Class"].astype("int8")
    return df


def validate(df: pd.DataFrame) -> None:
    assert df.isnull().sum().sum() == 0, "nulls present"
    assert set(df["Class"].unique()) == {0, 1}, f"class values: {set(df['Class'].unique())}"
    assert df.shape == (284807, 31), f"shape mismatch: {df.shape}"


def save_parquet(df: pd.DataFrame, path: str) -> None:
    df.to_parquet(path, compression="snappy", index=False)


def main() -> None:
    df = load_raw(RAW)
    df = coerce_dtypes(df)
    validate(df)
    save_parquet(df, OUT)
    reloaded = pd.read_parquet(OUT)
    validate(reloaded)
    dtype_ok = all(reloaded[c].dtype == "float64" for c in EXPECTED_COLS[:-1]) and reloaded["Class"].dtype == "int8"
    size_mb = os.path.getsize(OUT) / (1024 * 1024)
    class_counts = reloaded["Class"].value_counts().to_dict()
    print(f"rows={len(reloaded)}")
    print(f"class_balance={class_counts}")
    print(f"dtype_check_pass={dtype_ok}")
    print(f"parquet_size_mb={size_mb:.2f}")


if __name__ == "__main__":
    main()
