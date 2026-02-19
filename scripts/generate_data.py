"""Generate fully synthetic credit scoring dataset."""

from credit_scoring.config.settings import load_settings
from credit_scoring.data.synthetic import generate_full_dataset


def main():
    settings = load_settings()
    datasets = generate_full_dataset(settings.data)

    output_dir = settings.data.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, df in datasets.items():
        path = output_dir / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"Saved {name}: {len(df)} rows -> {path}")

    borrowers = datasets["borrowers"]
    print(f"\nDefault rate: {borrowers['is_default'].mean():.3f}")
    print(f"Fraud rate: {borrowers['is_fraud'].mean():.3f}")


if __name__ == "__main__":
    main()
