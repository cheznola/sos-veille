#!/usr/bin/env python3
"""Run hebdomadaire de l'agent de veille.

Lit le moteur, le domaine, le profil, la mémoire et les derniers rapports, appelle
l'API Anthropic avec la recherche web serveur, puis écrit le rapport du jour, réécrit
la mémoire et applique les corrections sur les rapports passés.

Rien n'est écrit sur disque tant que la réponse n'a pas été entièrement validée.
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

RACINE = Path(__file__).resolve().parent.parent

MOTEUR = RACINE / "moteur.md"
DOMAINE = RACINE / "domaines" / "rh-etudiant.md"
PROFIL = RACINE / "profil.md"
SUJETS_SUIVIS = RACINE / "etat" / "sujets-suivis.md"
RAPPORTS = RACINE / "rapports"

NB_RAPPORTS_RELUS = 3

MODELE = "claude-sonnet-4-6"
MAX_TOKENS = 32000
MAX_REPRISES = 6  # nombre de reprises autorisées sur stop_reason == "pause_turn"

OUTIL_RECHERCHE_WEB = {"type": "web_search_20260209", "name": "web_search"}

MARQUEURS = ("===RAPPORT===", "===SUJETS-SUIVIS===", "===CORRECTIONS===")

MOTIF_CORRECTION = re.compile(
    r"\[\[CORRECTION:\s*(?P<cible>[^\]\n]+?)\s*\]\]\s*\n"
    r"(?P<encart>.*?)"
    r"\n?\[\[/CORRECTION\]\]",
    re.DOTALL,
)


class ErreurVeille(Exception):
    """Erreur bloquante : le run s'arrête sans rien écrire."""


# --------------------------------------------------------------------------- lecture


def lire(chemin: Path) -> str:
    if not chemin.is_file():
        raise ErreurVeille(
            f"Fichier requis introuvable : {chemin.relative_to(RACINE)}\n"
            f"Le run ne peut pas démarrer sans lui."
        )
    contenu = chemin.read_text(encoding="utf-8").strip()
    if not contenu:
        raise ErreurVeille(f"Fichier vide : {chemin.relative_to(RACINE)}")
    return contenu


def derniers_rapports() -> list[tuple[str, str]]:
    """Les N derniers rapports, du plus ancien au plus récent."""
    if not RAPPORTS.is_dir():
        return []
    fichiers = sorted(
        (f for f in RAPPORTS.glob("*.md") if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f.name)),
        key=lambda f: f.name,
    )
    retenus = fichiers[-NB_RAPPORTS_RELUS:]
    return [(f"rapports/{f.name}", f.read_text(encoding="utf-8")) for f in retenus]


def construire_prompt(aujourdhui: str) -> str:
    morceaux = [
        "Tu exécutes un run de veille. Applique la méthode ci-dessous à la lettre.",
        f"\nDate du jour : {aujourdhui}.",
        "\n\n########## MÉTHODE (moteur.md) ##########\n\n" + lire(MOTEUR),
        "\n\n########## DOMAINE (domaines/rh-etudiant.md) ##########\n\n" + lire(DOMAINE),
        "\n\n########## PROFIL (profil.md) ##########\n\n" + lire(PROFIL),
        "\n\n########## MÉMOIRE (etat/sujets-suivis.md) ##########\n\n" + lire(SUJETS_SUIVIS),
    ]

    precedents = derniers_rapports()
    if precedents:
        morceaux.append(
            f"\n\n########## {len(precedents)} DERNIERS RAPPORTS "
            "(déjà lus par le destinataire) ##########"
        )
        for nom, contenu in precedents:
            morceaux.append(f"\n\n----- {nom} -----\n\n{contenu}")
    else:
        morceaux.append(
            "\n\n########## RAPPORTS PRÉCÉDENTS ##########\n\n"
            "Aucun. C'est le premier run : rien n'a encore été signalé, "
            "et il n'y a donc aucune correction possible."
        )

    morceaux.append(
        "\n\n########## CE QUE TU FAIS MAINTENANT ##########\n\n"
        "Mène les deux passes de recherche par domaine, sélectionne, puis réponds en "
        "trois blocs délimités exactement comme le prescrit la méthode :\n"
        f"{MARQUEURS[0]}\n{MARQUEURS[1]}\n{MARQUEURS[2]}\n"
        "Rien avant le premier délimiteur, rien après le dernier bloc."
    )
    return "".join(morceaux)


# ------------------------------------------------------------------------------ API


def appeler_modele(prompt: str) -> tuple[str, int]:
    """Retourne le texte complet de la réponse et le nombre de recherches web."""
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise ErreurVeille(
            "ANTHROPIC_API_KEY absent de l'environnement.\n"
            "En local : export ANTHROPIC_API_KEY=... — "
            "sur GitHub Actions : secret du dépôt du même nom."
        )

    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    texte: list[str] = []
    recherches = 0

    for tour in range(MAX_REPRISES + 1):
        try:
            with client.messages.stream(
                model=MODELE,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                tools=[OUTIL_RECHERCHE_WEB],
                messages=messages,
            ) as flux:
                reponse = flux.get_final_message()
        except anthropic.APIStatusError as err:
            raise ErreurVeille(
                f"L'API Anthropic a répondu {err.status_code} : {err.message}\n"
                "Aucun fichier n'a été modifié."
            ) from err
        except anthropic.APIConnectionError as err:
            raise ErreurVeille(
                f"Impossible de joindre l'API Anthropic : {err}\n"
                "Aucun fichier n'a été modifié."
            ) from err

        for bloc in reponse.content:
            if bloc.type == "text":
                texte.append(bloc.text)
            elif bloc.type == "server_tool_use" and bloc.name == "web_search":
                recherches += 1

        if reponse.stop_reason != "pause_turn":
            if reponse.stop_reason == "max_tokens":
                raise ErreurVeille(
                    f"Réponse tronquée : la limite de {MAX_TOKENS} tokens de sortie a été "
                    "atteinte avant la fin. Aucun fichier n'a été modifié.\n"
                    "Augmente MAX_TOKENS ou réduis le nombre de sujets demandé."
                )
            break

        # Turn en pause : on renvoie l'historique tel quel, le serveur reprend seul.
        messages.append({"role": "assistant", "content": reponse.content})
        if tour == MAX_REPRISES:
            raise ErreurVeille(
                f"Le modèle est resté en pause après {MAX_REPRISES} reprises. "
                "Aucun fichier n'a été modifié."
            )

    complet = "".join(texte).strip()
    if not complet:
        raise ErreurVeille("Le modèle n'a renvoyé aucun texte. Aucun fichier n'a été modifié.")
    return complet, recherches


# --------------------------------------------------------------------------- parsing


def decouper_blocs(reponse: str) -> tuple[str, str, str]:
    positions = []
    for marqueur in MARQUEURS:
        motif = re.compile(rf"^{re.escape(marqueur)}\s*$", re.MULTILINE)
        trouves = list(motif.finditer(reponse))
        if not trouves:
            raise ErreurVeille(
                f"Bloc manquant dans la réponse du modèle : {marqueur}\n"
                "Aucun fichier n'a été modifié. Réponse reçue (500 premiers caractères) :\n"
                f"{reponse[:500]}"
            )
        if len(trouves) > 1:
            raise ErreurVeille(
                f"Délimiteur {marqueur} présent {len(trouves)} fois dans la réponse. "
                "Découpage ambigu, aucun fichier n'a été modifié."
            )
        positions.append(trouves[0])

    if not positions[0].start() < positions[1].start() < positions[2].start():
        raise ErreurVeille(
            "Les trois blocs ne sont pas dans l'ordre attendu "
            "(RAPPORT, SUJETS-SUIVIS, CORRECTIONS). Aucun fichier n'a été modifié."
        )

    rapport = reponse[positions[0].end():positions[1].start()].strip()
    suivis = reponse[positions[1].end():positions[2].start()].strip()
    corrections = reponse[positions[2].end():].strip()

    if not rapport:
        raise ErreurVeille("Le bloc RAPPORT est vide. Aucun fichier n'a été modifié.")
    if not suivis:
        raise ErreurVeille("Le bloc SUJETS-SUIVIS est vide. Aucun fichier n'a été modifié.")
    if not corrections:
        raise ErreurVeille(
            "Le bloc CORRECTIONS est vide : il doit contenir au moins le mot AUCUNE. "
            "Aucun fichier n'a été modifié."
        )
    return rapport, suivis, corrections


def analyser_corrections(bloc: str, rapport_du_jour: Path) -> list[tuple[Path, str]]:
    if bloc.strip().upper() == "AUCUNE":
        return []

    trouvees = list(MOTIF_CORRECTION.finditer(bloc))
    if not trouvees:
        raise ErreurVeille(
            "Le bloc CORRECTIONS n'est ni AUCUNE ni une suite de balises "
            "[[CORRECTION: …]] … [[/CORRECTION]]. Aucun fichier n'a été modifié.\n"
            f"Contenu reçu :\n{bloc[:500]}"
        )

    corrections: list[tuple[Path, str]] = []
    for trouvee in trouvees:
        cible = trouvee.group("cible").strip()
        encart = trouvee.group("encart").strip()

        if not encart:
            raise ErreurVeille(
                f"Correction vide visant {cible}. Aucun fichier n'a été modifié."
            )

        chemin = (RACINE / cible).resolve()
        try:
            chemin.relative_to(RAPPORTS.resolve())
        except ValueError:
            raise ErreurVeille(
                f"Correction visant un chemin hors de rapports/ : {cible}. "
                "Aucun fichier n'a été modifié."
            ) from None
        if not chemin.is_file():
            raise ErreurVeille(
                f"Correction visant un rapport inexistant : {cible}. "
                "Aucun fichier n'a été modifié."
            )
        if chemin == rapport_du_jour:
            raise ErreurVeille(
                "Correction visant le rapport du jour lui-même : "
                "la révision doit figurer dans le bloc RAPPORT, pas en correction. "
                "Aucun fichier n'a été modifié."
            )
        corrections.append((chemin, encart))
    return corrections


# --------------------------------------------------------------------------- écriture


def en_tete(date_du_jour: str, heure_utc: str, duree: float, recherches: int) -> str:
    return (
        f"# Veille — {date_du_jour}\n\n"
        f"<!-- run automatique -->\n"
        f"*Run du {date_du_jour} à {heure_utc} UTC · durée {duree:.0f} s · "
        f"{recherches} recherche{'s' if recherches > 1 else ''} web · modèle {MODELE}*\n\n"
        f"---\n\n"
    )


def inserer_correction(chemin: Path, encart: str) -> bool:
    """Insère l'encart en tête du rapport visé. Retourne False si déjà présent."""
    contenu = chemin.read_text(encoding="utf-8")
    if encart.strip() in contenu:
        return False

    lignes = contenu.split("\n")
    # On garde le titre du rapport en première position s'il y en a un.
    if lignes and lignes[0].startswith("# "):
        avant, apres = lignes[:1], lignes[1:]
    else:
        avant, apres = [], lignes

    while apres and not apres[0].strip():
        apres.pop(0)
    nouveau = "\n".join(avant + ["", encart.strip(), ""] + apres).lstrip("\n")
    chemin.write_text(nouveau, encoding="utf-8")
    return True


# ------------------------------------------------------------------------------ main


def main() -> int:
    depart = time.monotonic()
    maintenant = datetime.now(timezone.utc)
    date_du_jour = maintenant.strftime("%Y-%m-%d")
    heure_utc = maintenant.strftime("%H:%M")

    RAPPORTS.mkdir(exist_ok=True)
    rapport_du_jour = (RAPPORTS / f"{date_du_jour}.md").resolve()

    prompt = construire_prompt(date_du_jour)
    print(f"Prompt assemblé : {len(prompt)} caractères.", file=sys.stderr)
    print(f"Appel du modèle {MODELE}…", file=sys.stderr)

    reponse, recherches = appeler_modele(prompt)
    print(f"Réponse reçue : {len(reponse)} caractères, {recherches} recherches.", file=sys.stderr)

    rapport, suivis, bloc_corrections = decouper_blocs(reponse)
    corrections = analyser_corrections(bloc_corrections, rapport_du_jour)

    # À partir d'ici, tout est validé : on écrit.
    duree = time.monotonic() - depart
    rapport_du_jour.write_text(
        en_tete(date_du_jour, heure_utc, duree, recherches) + rapport + "\n",
        encoding="utf-8",
    )
    print(f"Écrit : rapports/{date_du_jour}.md", file=sys.stderr)

    SUJETS_SUIVIS.write_text(suivis + "\n", encoding="utf-8")
    print("Écrit : etat/sujets-suivis.md", file=sys.stderr)

    for chemin, encart in corrections:
        nom = chemin.relative_to(RACINE)
        if inserer_correction(chemin, encart):
            print(f"Corrigé : {nom}", file=sys.stderr)
        else:
            print(f"Correction déjà présente, ignorée : {nom}", file=sys.stderr)

    print(f"Run terminé en {duree:.0f} s.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErreurVeille as erreur:
        print(f"\nÉCHEC DU RUN\n{erreur}", file=sys.stderr)
        sys.exit(1)
