import os
import sys

from dotenv import load_dotenv

from agent.services.pipeline import run_agent_pipeline
from agent.utils.logging import log

load_dotenv()


def get_job_url() -> str:
    return os.getenv("JOB_URL", "").strip()


def main() -> int:
    job_url = get_job_url()

    if not job_url:
        log("Aucun JOB_URL fourni : agent est un job batch one-shot et se termine sans erreur.", "INFO")
        return 0

    try:
        log("Démarrage de l'agent autonome.", "INFO")
        result = run_agent_pipeline(job_url)

        recommendation = result.recommendation
        score = result.fit_score

        if recommendation == "apply":
            print(f"✅ Recommandation : POSTULER (score : {score}/100)")
        elif recommendation == "skip":
            print(f"⏭️  Recommandation : PASSER (score : {score}/100)")
        else:
            print(f"⚠️  Recommandation : INCERTAINE (score : {score}/100)")

        return 0

    except FileNotFoundError as error:
        log(str(error), "ERREUR")
        return 1
    except RuntimeError as error:
        log(f"Échec de l'agent : {error}", "ERREUR")
        return 1
    except Exception as error:
        log(f"Erreur inattendue : {error}", "ERREUR")
        raise


if __name__ == "__main__":
    sys.exit(main())
