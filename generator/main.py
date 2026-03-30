import sys

from generator.services.pipeline import run_generation_pipeline
from generator.utils.logging import log


def main() -> None:
    try:
        outcome = run_generation_pipeline()

        if outcome.get("status") == "skipped":
            sys.exit(0)

        if outcome.get("success_count", 0) > 0:
            print("✅ CV Europass générés")
            return

        log("Aucun provider n'a pu générer de CV.", "ERREUR")
        sys.exit(1)
    except FileNotFoundError as error:
        log(str(error), "ERREUR")
        sys.exit(1)
    except Exception as error:
        log(f"Échec global du batch generator : {error}", "ERREUR")
        raise


if __name__ == "__main__":
    main()