"""Run the full training pipeline."""

from credit_scoring.config.settings import load_settings
from credit_scoring.models.training import TrainingPipeline
from credit_scoring.utils.logging import setup_logging


def main():
    settings = load_settings()
    setup_logging(settings.log_level, json_output=False)

    pipeline = TrainingPipeline(settings)
    results = pipeline.run()

    print(f"\nFinal Results:")
    print(f"  PD Ensemble AUC: {results.get('pd_auc', 0):.4f}")
    print(f"  PD Ensemble KS:  {results.get('pd_ks', 0):.4f}")
    print(f"  PD Ensemble Gini:{results.get('pd_gini', 0):.4f}")


if __name__ == "__main__":
    main()
