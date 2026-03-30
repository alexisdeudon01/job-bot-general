from typing import Optional

import spacy

from analyzer.domain.models import NLPResult
from analyzer.utils.logging import log


def load_spacy_model():
    log("Initialisation du moteur NLP spaCy...", "INFO")
    for model_name in ("fr_core_news_lg", "fr_core_news_md", "fr_core_news_sm"):
        try:
            model = spacy.load(model_name)
            log(f"Modèle spaCy chargé avec succès : {model_name}", "INFO")
            return model
        except OSError:
            log(f"Modèle spaCy indisponible : {model_name}", "WARN")

    log("Aucun modèle spaCy français installé, utilisation d'un mode dégradé sans NLP avancé.", "WARN")
    return None


class NLPService:
    def __init__(self, model: Optional[object] = None):
        self.model = model if model is not None else load_spacy_model()

    def clean(self, text: str) -> NLPResult:
        log(f"Préparation NLP du texte de l'offre ({len(text)} caractères bruts)...", "INFO")

        if self.model is None:
            words = [word.strip(".,;:!?()[]{}\"'") for word in text.lower().split()]
            clean_tokens = [word for word in words if len(word) > 2]
            result = NLPResult(
                clean_text=" ".join(clean_tokens[:800]),
                entities=[],
                keywords=list(dict.fromkeys(clean_tokens))[:50],
            )
            log(
                f"Mode NLP dégradé terminé : {len(result.keywords)} mots-clés retenus, aucune entité extraite.",
                "WARN",
            )
            return result

        doc = self.model(text.lower())
        clean_tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and len(token.text) > 2]
        entities = [ent.text for ent in doc.ents]
        result = NLPResult(
            clean_text=" ".join(clean_tokens[:800]),
            entities=list(set(entities))[:30],
            keywords=list(set(clean_tokens))[:50],
        )
        log(
            f"NLP terminé : {len(result.keywords)} mots-clés et {len(result.entities)} entités détectés.",
            "INFO",
        )
        return result