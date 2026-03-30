import os
import sys

from dotenv import load_dotenv

from analyzer.services.pipeline import create_default_pipeline
from analyzer.utils.logging import log

load_dotenv()


def get_job_url() -> str:
    return os.getenv("JOB_URL", "").strip()


def run_batch() -> int:
    job_url = get_job_url()

    if not job_url:
        log("Aucun JOB_URL fourni : analyzer est un job batch one-shot et se termine sans erreur.", "INFO")
        return 0

    try:
        log("Démarrage du batch analyzer.", "INFO")
        pipeline = create_default_pipeline()
        artifacts = pipeline.run(job_url=job_url, cv_path="/data/resume_europass.txt")
        pipeline.write_output(artifacts.job_json, output_path="/output/job_data.json")

        if artifacts.fallback_reason:
            log("Analyse terminée en mode dégradé avec génération locale du JSON.", "WARN")
            print("⚠️ Analyse terminée en mode fallback")
        else:
            log("Analyse terminée avec succès.", "INFO")
            print("✅ Analyse terminée")

        return 0
    except Exception as error:
        log(f"Échec du batch analyzer : {error}", "ERREUR")
        raise


def main():
    return run_batch()


if __name__ == "__main__":
    sys.exit(main())