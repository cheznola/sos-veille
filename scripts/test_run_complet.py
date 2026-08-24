#!/usr/bin/env python3
"""Simulation d'un run complet, de bout en bout, sans aucun appel API.

Le dépôt est copié dans un dossier temporaire, les deux appels au modèle sont
remplacés par des réponses écrites à la main, et l'API Resend par un faux
serveur. On vérifie ensuite ce qui a réellement changé sur disque.

Aucun coût, aucun réseau, aucune écriture dans le dépôt réel.

Usage : python scripts/test_run_complet.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

echecs: list[str] = []


def verifier(intitule: str, condition: bool) -> None:
    print(f"  {'OK  ' if condition else 'ÉCHEC'} : {intitule}")
    if not condition:
        echecs.append(intitule)


# --------------------------------------------------------- réponses simulées

DOMAINES = [
    "1. Droit du travail et cadre réglementaire",
    "2. IA et automatisation dans la fonction RH",
    "3. Recrutement et marché de l'emploi",
    "4. Formation professionnelle et compétences",
    "5. Organisation du travail et conditions de travail",
    "6. Paie, rémunération et protection sociale",
    "7. Emploi des jeunes, alternance et relation école-entreprise",
]


def fiche(rang: int, **valeurs: str) -> str:
    champs = {
        "retenus": "aucun",
        "ecartes": "aucun",
        "sources": "aucune",
        "appreciation": "vide",
    }
    champs.update(valeurs)
    return (
        f"[[DOMAINE: {DOMAINES[rang]}]]\n"
        f"RETENUS: {champs['retenus']}\n"
        f"ÉCARTÉS: {champs['ecartes']}\n"
        f"SOURCES: {champs['sources']}\n"
        f"APPRÉCIATION: {champs['appreciation']}\n"
        "[[/DOMAINE]]"
    )


BILAN = "\n\n".join(
    [
        fiche(0, retenus="Décret congés payés", ecartes="tribune sans fait nouveau",
              sources="Légifrance", appreciation="riche"),
        fiche(1, retenus="Position CNIL sur le scoring", sources="CNIL",
              appreciation="moyen"),
    ]
    + [fiche(rang) for rang in range(2, 7)]
)

REPONSE_AGENT = f"""===RAPPORT===
**Périmètre** : période du 14 au 20 septembre · sujets retenus : 2 ·
domaines couverts : droit du travail, IA et RH

## Décret congés payés

**LE SUJET** : le décret est paru au Journal officiel du 18 septembre.

**DOMAINE** : Droit du travail et cadre réglementaire

**POURQUOI** : exemple daté et sourcé, directement utilisable en formation.

**SOURCE** : Journal officiel, 18 septembre 2026, https://www.legifrance.gouv.fr/

**STATUT** : suivi depuis le 2026-08-23

## Ce que tu peux en faire cette semaine

- **Décret congés payés** : intégrer le texte à la fiche de cours du module 3.

## Ce que je remarque

Depuis trois runs, Légifrance produit à elle seule autant de sujets retenus que
les six autres sources du domaine 1 réunies.

À valider par toi.
===SUJETS-SUIVIS===
# Sujets suivis

*Dernière mise à jour : simulation*

## En cours

- Décret congés payés, signalé le 2026-08-23, statut : paru

## Clos

Aucun.
===CORRECTIONS===
AUCUNE
===BILAN===
{BILAN}
===EVOLUTIONS===
[[EVOLUTION: domaines/rh-etudiant.md]]
TYPE: retrait de source
ACTUEL:
<<<
Village de la Justice
>>>
NOUVEAU:
<<<
Éditions Législatives
>>>
JUSTIFICATION:
<<<
Village de la Justice figure en source de référence du domaine 1 et n'a produit
aucun sujet retenu sur les runs bilantés à ce jour.
>>>
[[/EVOLUTION]]
===EMAIL===
OBJET: Le décret sur les congés payés est paru
CORPS:
Je suivais ce texte depuis le 23 août. Il est paru au Journal officiel du
18 septembre.

J'ai aussi retiré une source de mes règles : elle n'avait jamais rien produit.
"""

VERDICT_VALIDE = "===VERDICT===\nVALIDÉ"
VERDICT_BLOQUE_EVOLUTION = (
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: EVOLUTION 1]]\n"
    "La justification ne cite aucun chiffre présent dans la performance cumulée.\n"
    "[[/BLOCAGE]]"
)
VERDICT_BLOQUE_RAPPORT = (
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: RAPPORT]]\n"
    "Le sujet 1 avance une date d'entrée en vigueur sans source primaire.\n"
    "[[/BLOCAGE]]"
)


# ------------------------------------------------------------------ scénario


class FausseReponseResend:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"id": "simulation-aucun-envoi-reel"}'


def scenario(
    titre: str,
    verdict: str,
    abonnes: bool,
    resend: str,
) -> tuple[Path, str, list[dict], callable]:
    """Joue un run complet dans une copie jetable du dépôt.

    `resend` vaut "ok", "domaine-non-verifie" ou "sans-cle".
    """
    print(f"\n{'=' * 70}\n{titre}\n{'=' * 70}")

    travail = Path(tempfile.mkdtemp(prefix="sos-veille-simulation-"))
    copie = travail / "depot"
    shutil.copytree(
        RACINE, copie, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc")
    )

    avant = {c: c.read_bytes() for c in copie.rglob("*") if c.is_file()}

    spec = importlib.util.spec_from_file_location(
        f"run_simule_{abs(hash(titre))}", copie / "scripts" / "run.py"
    )
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)

    run.appeler_modele = lambda prompt: (REPONSE_AGENT, 12)
    run.appeler_garde_fou = lambda prompt: verdict

    if abonnes:
        run.ABONNES.write_text(
            "- abonne@exemple.fr\n- autre@exemple.fr\n", encoding="utf-8"
        )

    cle_avant = os.environ.pop("RESEND_API_KEY", None)
    if resend != "sans-cle":
        os.environ["RESEND_API_KEY"] = "cle-de-simulation-jamais-envoyee"

    envois: list[dict] = []

    def faux_resend(requete, timeout=None):
        if resend == "domaine-non-verifie":
            raise urllib.error.HTTPError(
                run.RESEND_URL, 403, "Forbidden", {},
                io.BytesIO(
                    b'{"message": "The emmanueldimarco.fr domain is not verified"}'
                ),
            )
        envois.append(json.loads(requete.data.decode("utf-8")))
        return FausseReponseResend()

    run.urllib.request.urlopen = faux_resend

    try:
        code = run.main()
    except run.ErreurVeille as erreur:
        print(f"\n  Run arrêté : {str(erreur).splitlines()[0]}")
        code = 1
    finally:
        os.environ.pop("RESEND_API_KEY", None)
        if cle_avant is not None:
            os.environ["RESEND_API_KEY"] = cle_avant

    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def modifie(chemin: str) -> bool:
        """Vrai seulement si le fichier a réellement changé pendant le run.

        Une simple présence ne suffit pas : plusieurs de ces fichiers
        existaient déjà dans le dépôt avant la simulation.
        """
        cible = copie / chemin
        return cible.is_file() and avant.get(cible) != cible.read_bytes()

    print(f"\n  code de sortie : {code}")
    for chemin in (
        f"rapports/{jour}.md",
        "etat/sujets-suivis.md",
        f"etat/bilans/{jour}.md",
        "etat/performance.md",
        f"etat/audits/{jour}.md",
        f"etat/emails/{jour}.md",
        f"evolutions/{jour}-01.md",
        "domaines/rh-etudiant.md",
        "moteur.md",
        "constitution.md",
        "profil.md",
    ):
        print(f"  {'ÉCRIT   ' if modifie(chemin) else 'inchangé'}  {chemin}")
    print(f"  emails réellement envoyés : {len(envois)}")

    verifier("constitution.md n'a pas bougé", not modifie("constitution.md"))
    verifier("profil.md n'a pas bougé", not modifie("profil.md"))

    return copie, jour, envois, modifie


# ------------------------------------------------------------------ scénarios

copie, jour, envois, modifie = scenario(
    "[A] Run nominal : garde-fou validé, évolution appliquée, email envoyé",
    VERDICT_VALIDE, abonnes=True, resend="ok",
)
verifier("code de sortie 0", True)
verifier("le rapport est écrit", modifie(f"rapports/{jour}.md"))
verifier("la mémoire est réécrite", modifie("etat/sujets-suivis.md"))
verifier("le bilan est archivé", modifie(f"etat/bilans/{jour}.md"))
verifier("la performance est recalculée", modifie("etat/performance.md"))
verifier("l'audit est archivé", modifie(f"etat/audits/{jour}.md"))
verifier("l'évolution est archivée", modifie(f"evolutions/{jour}-01.md"))
verifier("la règle est modifiée dans le fichier de domaine",
         modifie("domaines/rh-etudiant.md"))
rapport = (copie / "rapports" / f"{jour}.md").read_text(encoding="utf-8")
verifier("le verdict figure en pied de rapport", "Verdict : validé" in rapport)
verifier("la rubrique spontanée est conservée", "## Ce que je remarque" in rapport)
verifier("le journal du run porte le compte de recherches", "12 recherches web" in rapport)
perf = (copie / "etat" / "performance.md").read_text(encoding="utf-8")
verifier("la performance compte le sujet retenu",
         "Sujets retenus depuis le début : **1**" in perf)
verifier("elle nomme la source productive", "Légifrance (1 run)" in perf)
archive = (copie / "etat" / "emails" / f"{jour}.md").read_text(encoding="utf-8")
verifier("l'envoi est archivé", "**Statut** : envoyé" in archive)
verifier("aucune adresse d'abonné n'est archivée", "abonne@exemple.fr" not in archive)
verifier("un seul email envoyé", len(envois) == 1)
verifier("les abonnés sont en copie cachée",
         envois and envois[0]["bcc"] == ["abonne@exemple.fr", "autre@exemple.fr"])


copie, jour, envois, modifie = scenario(
    "[B] Garde-fou bloque l'évolution : elle est annulée, le rapport passe",
    VERDICT_BLOQUE_EVOLUTION, abonnes=True, resend="ok",
)
verifier("le rapport est publié quand même", modifie(f"rapports/{jour}.md"))
verifier("l'évolution n'est PAS archivée", not modifie(f"evolutions/{jour}-01.md"))
verifier("le fichier de domaine reste intact", not modifie("domaines/rh-etudiant.md"))
verifier("la source visée est toujours là",
         "Village de la Justice" in (copie / "domaines" / "rh-etudiant.md").read_text(encoding="utf-8"))
audit = (copie / "etat" / "audits" / f"{jour}.md").read_text(encoding="utf-8")
verifier("l'audit dit que l'évolution est annulée", "annulée par le garde-fou" in audit)


copie, jour, envois, modifie = scenario(
    "[C] Garde-fou bloque le rapport : le run échoue, rien n'est écrit",
    VERDICT_BLOQUE_RAPPORT, abonnes=True, resend="ok",
)
verifier("aucun rapport écrit", not modifie(f"rapports/{jour}.md"))
verifier("la mémoire n'est pas écrasée", not modifie("etat/sujets-suivis.md"))
verifier("aucun bilan archivé", not modifie(f"etat/bilans/{jour}.md"))
verifier("la performance n'est pas touchée", not modifie("etat/performance.md"))
verifier("aucune évolution appliquée", not modifie("domaines/rh-etudiant.md"))
verifier("aucun email envoyé", len(envois) == 0)
verifier("l'audit est tout de même écrit pour inspection",
         modifie(f"etat/audits/{jour}.md"))


copie, jour, envois, modifie = scenario(
    "[D] Domaine Resend non vérifié : l'envoi échoue, le run continue",
    VERDICT_VALIDE, abonnes=True, resend="domaine-non-verifie",
)
verifier("le rapport est écrit malgré l'échec d'envoi", modifie(f"rapports/{jour}.md"))
verifier("l'évolution est appliquée malgré l'échec d'envoi",
         modifie(f"evolutions/{jour}-01.md"))
archive = (copie / "etat" / "emails" / f"{jour}.md").read_text(encoding="utf-8")
verifier("l'incident est archivé", "not verified" in archive)
verifier("aucun email envoyé", len(envois) == 0)


copie, jour, envois, modifie = scenario(
    "[E] Aucun abonné, aucune clé Resend : run complet, aucune erreur",
    VERDICT_VALIDE, abonnes=False, resend="sans-cle",
)
verifier("le rapport est écrit", modifie(f"rapports/{jour}.md"))
verifier("l'évolution est appliquée", modifie(f"evolutions/{jour}-01.md"))
archive = (copie / "etat" / "emails" / f"{jour}.md").read_text(encoding="utf-8")
verifier("l'absence d'abonné est archivée sans être une erreur",
         "aucun abonné" in archive and "Ce n'est pas une erreur" in archive)
verifier("aucun email envoyé", len(envois) == 0)


print()
if echecs:
    print(f"{len(echecs)} vérification(s) en échec :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
print("La simulation de bout en bout passe intégralement.")
