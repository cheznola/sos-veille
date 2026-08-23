#!/usr/bin/env python3
"""Tests à blanc du parsing de la réponse du modèle. Aucun appel API.

Usage : python scripts/test_parsing.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("run", RACINE / "scripts" / "run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)

echecs: list[str] = []


def verifier(intitule: str, condition: bool) -> None:
    print(f"  {'OK  ' if condition else 'ÉCHEC'} — {intitule}")
    if not condition:
        echecs.append(intitule)


def doit_echouer(intitule: str, appel) -> None:
    try:
        appel()
    except run.ErreurVeille:
        print(f"  OK   — rejeté comme prévu : {intitule}")
        return
    print(f"  ÉCHEC — accepté à tort : {intitule}")
    echecs.append(intitule)


CORPS = (
    "**Périmètre** — période : semaine 34 · recherches : 33 · sujets retenus : 5",
    "# Sujets suivis\n\n## En cours\n\n- Décret X — signalé le 2026-08-23",
    "AUCUNE",
)


def bien_formee() -> str:
    return (
        f"===RAPPORT===\n{CORPS[0]}\n"
        f"===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}"
    )


print("\n[1] Cas nominal")
r, s, c = run.decouper_blocs(bien_formee())
verifier("bloc RAPPORT extrait", r == CORPS[0])
verifier("bloc SUJETS-SUIVIS extrait", s == CORPS[1])
verifier("bloc CORRECTIONS extrait", c == CORPS[2])


print("\n[2] Préambule avant ===RAPPORT=== (cause de l'échec du run 0)")
avec_preambule = (
    "Je lis les quatre entrées, puis je lance les deux passes de recherche "
    "par domaine.\n\n" + bien_formee()
)
r, s, c = run.decouper_blocs(avec_preambule)
verifier("le préambule est ignoré", r == CORPS[0])
verifier("les blocs suivants sont intacts", (s, c) == (CORPS[1], CORPS[2]))


print("\n[3] Délimiteur collé à du texte sur la même ligne")
colle_avant = (
    "Je lis les quatre entrées, puis je lance les deux passes de recherche "
    f"par domaine.===RAPPORT===\n{CORPS[0]}\n"
    f"===SUJETS-SUIVIS===\n{CORPS[1]}\n"
    f"===CORRECTIONS===\n{CORPS[2]}"
)
r, s, c = run.decouper_blocs(colle_avant)
verifier("délimiteur collé en fin de phrase : décollé et ignoré", r == CORPS[0])
verifier("blocs suivants intacts", (s, c) == (CORPS[1], CORPS[2]))

colle_apres = (
    f"===RAPPORT==={CORPS[0]}\n"
    f"===SUJETS-SUIVIS==={CORPS[1]}\n"
    f"===CORRECTIONS==={CORPS[2]}"
)
r, s, c = run.decouper_blocs(colle_apres)
verifier("délimiteur collé au début du bloc suivant", r == CORPS[0])
verifier("les trois blocs sont récupérés", (s, c) == (CORPS[1], CORPS[2]))

colle_des_deux_cotes = (
    f"Voici le résultat.===RAPPORT==={CORPS[0]}===SUJETS-SUIVIS==={CORPS[1]}"
    f"===CORRECTIONS==={CORPS[2]}"
)
r, s, c = run.decouper_blocs(colle_des_deux_cotes)
verifier("tout sur une seule ligne, sans aucun saut", (r, s, c) == CORPS)

indente = f"   ===RAPPORT===  \n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n===CORRECTIONS===\n{CORPS[2]}"
r, _, _ = run.decouper_blocs(indente)
verifier("délimiteur indenté et suivi d'espaces", r == CORPS[0])

verifier(
    "une réponse déjà propre n'est pas altérée par la normalisation",
    run.normaliser_delimiteurs(bien_formee()).strip() == bien_formee().strip(),
)


print("\n[4] Garde-fous de fond : ils doivent TOUJOURS rejeter")
doit_echouer(
    "bloc CORRECTIONS absent",
    lambda: run.decouper_blocs(f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}"),
)
doit_echouer(
    "blocs dans le désordre",
    lambda: run.decouper_blocs(
        f"===SUJETS-SUIVIS===\n{CORPS[1]}\n===RAPPORT===\n{CORPS[0]}\n===CORRECTIONS===\n{CORPS[2]}"
    ),
)
doit_echouer(
    "délimiteur en double",
    lambda: run.decouper_blocs(bien_formee() + "\n===RAPPORT===\nautre chose"),
)
doit_echouer(
    "bloc RAPPORT vide",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n\n===SUJETS-SUIVIS===\n{CORPS[1]}\n===CORRECTIONS===\n{CORPS[2]}"
    ),
)
doit_echouer("réponse entièrement vide", lambda: run.decouper_blocs(""))


print("\n[5] Corrections : format et sécurité des chemins")
faux_rapport = run.RAPPORTS / "2000-01-01.md"
faux_rapport.write_text("# Veille — 2000-01-01\n\n*run*\n\n## Sujet\ntexte\n", encoding="utf-8")
try:
    verifier(
        "AUCUNE ne produit aucune correction",
        run.analyser_corrections("AUCUNE", run.RAPPORTS / "z.md") == [],
    )

    bloc = "[[CORRECTION: rapports/2000-01-01.md]]\n> **Révision** — erreur.\n[[/CORRECTION]]"
    corrections = run.analyser_corrections(bloc, run.RAPPORTS / "z.md")
    verifier("une correction valide est acceptée", len(corrections) == 1)
    verifier("insertion effectuée", run.inserer_correction(*corrections[0]) is True)
    verifier("insertion idempotente", run.inserer_correction(*corrections[0]) is False)
    contenu = faux_rapport.read_text(encoding="utf-8")
    verifier("le titre du rapport reste en première ligne", contenu.startswith("# Veille"))
    verifier("l'encart est bien inséré", "> **Révision** — erreur." in contenu)

    doit_echouer(
        "correction visant un rapport inexistant",
        lambda: run.analyser_corrections(
            "[[CORRECTION: rapports/2099-01-01.md]]\n> x\n[[/CORRECTION]]",
            run.RAPPORTS / "z.md",
        ),
    )
    doit_echouer(
        "correction visant un chemin hors rapports/",
        lambda: run.analyser_corrections(
            "[[CORRECTION: ../../../etc/passwd]]\n> x\n[[/CORRECTION]]", run.RAPPORTS / "z.md"
        ),
    )
    doit_echouer(
        "correction visant le rapport du jour",
        lambda: run.analyser_corrections(bloc, faux_rapport.resolve()),
    )
    doit_echouer(
        "bloc CORRECTIONS au format invalide",
        lambda: run.analyser_corrections("n'importe quoi", run.RAPPORTS / "z.md"),
    )
finally:
    faux_rapport.unlink(missing_ok=True)


print()
if echecs:
    print(f"{len(echecs)} test(s) en échec :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
print("Tous les tests passent.")
