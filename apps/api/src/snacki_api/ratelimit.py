"""Limite de débit en mémoire, par fenêtre glissante (menace T04, ASVS V6.1.1).

Suffisant pour une instance ; Cloud Run en lance au plus 2 (max-instances=2, J5), la limite
réelle est donc au pire doublée. La clé est l'adresse du client : à partir de J4, l'API n'est
appelée que par le serveur web, qui transmettra l'adresse d'origine (à brancher à J4-J5).
"""

import threading
import time
from collections import OrderedDict, deque

MAX_KEYS = 10_000  # mémoire bornée : les clés les plus anciennes sont oubliées


class RateLimiter:
    def __init__(self, rules: dict[str, list[tuple[int, int]]]) -> None:
        """rules : {nom: [(nombre maximal, fenêtre en secondes), …]}"""
        self._rules = rules
        self._hits: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def hit(self, rule: str, key: str) -> int:
        """Enregistre un appel. Renvoie 0 s'il est autorisé, sinon le délai d'attente en s."""
        now = time.monotonic()
        longest = max(window for _, window in self._rules[rule])
        with self._lock:
            hits = self._hits.setdefault((rule, key), deque())
            self._hits.move_to_end((rule, key))
            while hits and hits[0] <= now - longest:
                hits.popleft()
            for limit, window in self._rules[rule]:
                recent = [t for t in hits if t > now - window]
                if len(recent) >= limit:
                    return max(1, int(recent[0] + window - now) + 1)
            hits.append(now)
            while len(self._hits) > MAX_KEYS:
                self._hits.popitem(last=False)
            return 0


DEFAULT_RULES = {
    "order_create": [(5, 60), (20, 3600)],  # 5 commandes par minute, 20 par heure
    "order_track": [(60, 60)],  # le suivi interroge régulièrement : 1 par seconde
    "auth": [(10, 60), (30, 3600)],  # connexions du staff : freine le bourrage d'essais
    "loyalty": [(20, 60), (200, 3600)],  # cartes : freine qui essaie des numéros au hasard
    "assistant": [(10, 60), (100, 3600)],  # assistant IA : protège le quota Gemini (T15)
    "resume": [(10, 60), (60, 3600)],  # résumé du jour (J10) : même raison
}
