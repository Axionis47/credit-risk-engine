"""Download and preprocess Kaggle credit datasets."""

from credit_scoring.config.settings import load_settings
from credit_scoring.data.download import DataDownloader
from credit_scoring.data.synthetic import generate_enrichment_for_existing, generate_full_dataset


def main():
    settings = load_settings()
    downloader = DataDownloader(settings.data.output_dir, seed=settings.data.random_seed)

    print("Attempting to download Kaggle data...")
    borrowers = downloader.download_and_preprocess()

    if borrowers.empty:
        print("No Kaggle data available. Generating fully synthetic dataset...")
        datasets = generate_full_dataset(settings.data)
        borrowers = datasets["borrowers"]
        transactions = datasets["transactions"]
        payments = datasets["payments"]
    else:
        # Subsample to n_borrowers for manageable training times
        max_n = settings.data.n_borrowers
        if len(borrowers) > max_n:
            print(f"Subsampling from {len(borrowers)} to {max_n} borrowers...")
            borrowers = borrowers.sample(max_n, random_state=settings.data.random_seed).reset_index(drop=True)
        print(f"Loaded {len(borrowers)} borrowers from Kaggle data")
        enrichment = generate_enrichment_for_existing(borrowers, settings.data)
        transactions = enrichment["transactions"]
        payments = enrichment["payments"]

    output_dir = settings.data.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    borrowers.to_parquet(output_dir / "borrowers.parquet", index=False)
    transactions.to_parquet(output_dir / "transactions.parquet", index=False)
    payments.to_parquet(output_dir / "payments.parquet", index=False)

    print(f"\nData saved to {output_dir}/")
    print(f"  borrowers.parquet: {len(borrowers)} rows")
    print(f"  transactions.parquet: {len(transactions)} rows")
    print(f"  payments.parquet: {len(payments)} rows")
    print(f"  Default rate: {borrowers['is_default'].mean():.3f}")
    print(f"  Fraud rate: {borrowers['is_fraud'].mean():.3f}")


if __name__ == "__main__":
    main()
