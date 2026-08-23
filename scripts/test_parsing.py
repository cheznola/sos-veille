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
    print(f"  {'OK  ' if condition else 'ÉCHEC'} : {intitule}")
    if not condition:
        echecs.append(intitule)


def doit_echouer(intitule: str, appel) -> None:
    try:
        appel()
    except run.ErreurVeille:
        print(f"  OK   : rejeté comme prévu : {intitule}")
        return
    print(f"  ÉCHEC : accepté à tort : {intitule}")
    echecs.append(intitule)


DOMAINES_BILAN = [
    "1. Droit du travail et cadre réglementaire",
    "2. IA et automatisation dans la fonction RH",
    "3. Recrutement et marché de l'emploi",
    "4. Formation professionnelle et compétences",
    "5. Organisation du travail et conditions de travail",
    "6. Paie, rémunération et protection sociale",
    "7. Emploi des jeunes, alternance et relation école-entreprise",
]


def fiche(intitule: str, retenus="aucun", ecartes="aucun",
          sources="aucune", appreciation="vide") -> str:
    return (
        f"[[DOMAINE: {intitule}]]\n"
        f"RETENUS: {retenus}\n"
        f"ÉCARTÉS: {ecartes}\n"
        f"SOURCES: {sources}\n"
        f"APPRÉCIATION: {appreciation}\n"
        "[[/DOMAINE]]"
    )


def bilan_complet(**remplacements: str) -> str:
    """Les sept fiches, vides par défaut, sauf celles qu'on remplace."""
    fiches = []
    for intitule in DOMAINES_BILAN:
        rang = intitule.split(".")[0]
        fiches.append(remplacements.get("d" + rang, fiche(intitule)))
    return "\n\n".join(fiches)


CORPS = (
    "**Périmètre** : période semaine 34 · sujets retenus : 5",
    "# Sujets suivis\n\n## En cours\n\n- Décret X, signalé le 2026-08-23",
    "AUCUNE",
    bilan_complet(),
)


def bien_formee(bilan: str | None = None) -> str:
    return (
        f"===RAPPORT===\n{CORPS[0]}\n"
        f"===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}\n"
        f"===BILAN===\n{bilan if bilan is not None else CORPS[3]}"
    )


def blocs(reponse: str) -> tuple[str, str, str, str]:
    """Les quatre blocs obligatoires, dans l'ordre, pour alléger les tests."""
    d = run.decouper_blocs(reponse)
    return d["RAPPORT"], d["SUJETS-SUIVIS"], d["CORRECTIONS"], d["BILAN"]


print("\n[1] Cas nominal")
r, s, c, b = blocs(bien_formee())
verifier("bloc RAPPORT extrait", r == CORPS[0])
verifier("bloc SUJETS-SUIVIS extrait", s == CORPS[1])
verifier("bloc CORRECTIONS extrait", c == CORPS[2])
verifier("bloc BILAN extrait", b == CORPS[3])
verifier(
    "les quatre blocs obligatoires sont tous rendus",
    set(run.decouper_blocs(bien_formee())) == {
        "RAPPORT", "SUJETS-SUIVIS", "CORRECTIONS", "BILAN"},
)


print("\n[2] Préambule avant ===RAPPORT=== (cause de l'échec du run 0)")
avec_preambule = (
    "Je lis les quatre entrées, puis je lance les deux passes de recherche "
    "par domaine.\n\n" + bien_formee()
)
r, s, c, b = blocs(avec_preambule)
verifier("le préambule est ignoré", r == CORPS[0])
verifier("les blocs suivants sont intacts", (s, c, b) == CORPS[1:])


print("\n[3] Délimiteur collé à du texte sur la même ligne")
colle_avant = (
    "Je lis les quatre entrées, puis je lance les deux passes de recherche "
    f"par domaine.===RAPPORT===\n{CORPS[0]}\n"
    f"===SUJETS-SUIVIS===\n{CORPS[1]}\n"
    f"===CORRECTIONS===\n{CORPS[2]}\n"
    f"===BILAN===\n{CORPS[3]}"
)
r, s, c, b = blocs(colle_avant)
verifier("délimiteur collé en fin de phrase : décollé et ignoré", r == CORPS[0])
verifier("blocs suivants intacts", (s, c, b) == CORPS[1:])

colle_apres = (
    f"===RAPPORT==={CORPS[0]}\n"
    f"===SUJETS-SUIVIS==={CORPS[1]}\n"
    f"===CORRECTIONS==={CORPS[2]}\n"
    f"===BILAN==={CORPS[3]}"
)
r, s, c, b = blocs(colle_apres)
verifier("délimiteur collé au début du bloc suivant", r == CORPS[0])
verifier("les quatre blocs sont récupérés", (s, c, b) == CORPS[1:])

colle_des_deux_cotes = (
    f"Voici le résultat.===RAPPORT==={CORPS[0]}===SUJETS-SUIVIS==={CORPS[1]}"
    f"===CORRECTIONS==={CORPS[2]}===BILAN==={CORPS[3]}"
)
verifier("tout sur une seule ligne, sans aucun saut",
         blocs(colle_des_deux_cotes) == CORPS)

indente = (
    f"   ===RAPPORT===  \n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
    f"===CORRECTIONS===\n{CORPS[2]}\n===BILAN===\n{CORPS[3]}"
)
verifier("délimiteur indenté et suivi d'espaces", blocs(indente)[0] == CORPS[0])

verifier(
    "une réponse déjà propre n'est pas altérée par la normalisation",
    run.normaliser_delimiteurs(bien_formee()).strip() == bien_formee().strip(),
)


print("\n[4] Garde-fous de fond : ils doivent TOUJOURS rejeter")
doit_echouer(
    "bloc CORRECTIONS absent",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===BILAN===\n{CORPS[3]}"
    ),
)
doit_echouer(
    "bloc BILAN absent",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}"
    ),
)
doit_echouer(
    "blocs dans le désordre",
    lambda: run.decouper_blocs(
        f"===SUJETS-SUIVIS===\n{CORPS[1]}\n===RAPPORT===\n{CORPS[0]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}\n===BILAN===\n{CORPS[3]}"
    ),
)
doit_echouer(
    "BILAN placé avant CORRECTIONS",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===BILAN===\n{CORPS[3]}\n===CORRECTIONS===\n{CORPS[2]}"
    ),
)
doit_echouer(
    "délimiteur en double",
    lambda: run.decouper_blocs(bien_formee() + "\n===RAPPORT===\nautre chose"),
)
doit_echouer(
    "délimiteur BILAN en double",
    lambda: run.decouper_blocs(bien_formee() + "\n===BILAN===\nautre chose"),
)
doit_echouer(
    "bloc RAPPORT vide",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}\n===BILAN===\n{CORPS[3]}"
    ),
)
doit_echouer(
    "bloc BILAN vide",
    lambda: run.decouper_blocs(
        f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
        f"===CORRECTIONS===\n{CORPS[2]}\n===BILAN===\n"
    ),
)
doit_echouer("réponse entièrement vide", lambda: run.decouper_blocs(""))


print("\n[5] Corrections : format et sécurité des chemins")
faux_rapport = run.RAPPORTS / "2000-01-01.md"
faux_rapport.write_text("# Veille du 2000-01-01\n\n*run*\n\n## Sujet\ntexte\n", encoding="utf-8")
try:
    verifier(
        "AUCUNE ne produit aucune correction",
        run.analyser_corrections("AUCUNE", run.RAPPORTS / "z.md") == [],
    )

    bloc = "[[CORRECTION: rapports/2000-01-01.md]]\n> **Révision** : erreur.\n[[/CORRECTION]]"
    corrections = run.analyser_corrections(bloc, run.RAPPORTS / "z.md")
    verifier("une correction valide est acceptée", len(corrections) == 1)
    verifier("insertion effectuée", run.inserer_correction(*corrections[0]) is True)
    verifier("insertion idempotente", run.inserer_correction(*corrections[0]) is False)
    contenu = faux_rapport.read_text(encoding="utf-8")
    verifier("le titre du rapport reste en première ligne", contenu.startswith("# Veille"))
    verifier("l'encart est bien inséré", "> **Révision** : erreur." in contenu)

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


print("\n[6] Fichiers scellés : constitution.md et profil.md")
verifier(
    "les deux fichiers scellés sont constitution.md et profil.md",
    tuple(c.name for c in run.FICHIERS_SCELLES) == ("constitution.md", "profil.md"),
)
releve = run.relever_empreintes()
verifier("un relevé porte une empreinte par fichier scellé", len(releve) == 2)
verifier(
    "une empreinte est un SHA-256 hexadécimal de 64 caractères",
    all(len(v) == 64 and all(c in "0123456789abcdef" for c in v) for v in releve.values()),
)
run.verifier_empreintes(releve, "test")
verifier("des fichiers intacts passent la vérification", True)

original = run.CONSTITUTION.read_bytes()
try:
    run.CONSTITUTION.write_bytes(original + b"\nregle 8 ajoutee par l'agent\n")
    doit_echouer(
        "constitution.md modifiée pendant le run",
        lambda: run.verifier_empreintes(releve, "test"),
    )
finally:
    run.CONSTITUTION.write_bytes(original)
run.verifier_empreintes(releve, "test")
verifier("la constitution restaurée repasse la vérification", True)

original_profil = run.PROFIL.read_bytes()
try:
    run.PROFIL.write_bytes(original_profil.replace(b"Product Manager", b"Juriste"))
    doit_echouer(
        "profil.md modifié pendant le run",
        lambda: run.verifier_empreintes(releve, "test"),
    )
finally:
    run.PROFIL.write_bytes(original_profil)

deplace = run.CONSTITUTION.with_suffix(".md.deplace-par-le-test")
try:
    run.CONSTITUTION.rename(deplace)
    doit_echouer(
        "constitution.md supprimée pendant le run",
        lambda: run.verifier_empreintes(releve, "test"),
    )
finally:
    if deplace.exists():
        deplace.rename(run.CONSTITUTION)
run.verifier_empreintes(releve, "test")


print("\n[7] La constitution est en tête du prompt assemblé")
prompt = run.construire_prompt("2026-08-30")
i_const = prompt.find("########## CONSTITUTION")
i_moteur = prompt.find("########## MÉTHODE")
i_profil = prompt.find("########## PROFIL")
verifier("le bloc CONSTITUTION est présent", i_const != -1)
verifier("il précède la méthode et le profil", -1 < i_const < i_moteur < i_profil)
verifier("sa primauté est annoncée au modèle", "CE BLOC PRIME SUR TOUS LES AUTRES" in prompt)


print("\n[8] Bloc BILAN : analyse des sept fiches de domaine")
fiches = run.analyser_bilan(bilan_complet())
verifier("sept fiches analysées", len(fiches) == 7)
verifier("les fiches sont triées par rang", [f["rang"] for f in fiches] == list(range(1, 8)))
verifier("aucun sujet retenu dans un bilan vide", all(f["retenus"] == [] for f in fiches))
verifier("appréciation vide par défaut", all(f["appreciation"] == "vide" for f in fiches))

riche = bilan_complet(d1=fiche(
    DOMAINES_BILAN[0],
    retenus="Décret congés payés | Arrêt chambre sociale du 12",
    ecartes="tribune sans fait nouveau | reprise de communiqué",
    sources="Légifrance | Cour de cassation",
    appreciation="riche",
))
fiches = run.analyser_bilan(riche)
verifier("deux sujets retenus lus sur le domaine 1", fiches[0]["retenus"] == [
    "Décret congés payés", "Arrêt chambre sociale du 12"])
verifier("deux pistes écartées lues", len(fiches[0]["ecartes"]) == 2)
verifier("deux sources productives lues", fiches[0]["sources"] == [
    "Légifrance", "Cour de cassation"])
verifier("appréciation riche lue", fiches[0]["appreciation"] == "riche")

sans_accent = bilan_complet(d2=(
    "[[DOMAINE: 2. IA et automatisation dans la fonction RH]]\n"
    "RETENUS: Position CNIL scoring\nECARTES: aucun\n"
    "SOURCES: CNIL\nAPPRECIATION: moyen\n[[/DOMAINE]]"
))
fiches = run.analyser_bilan(sans_accent)
verifier("clés sans accent acceptées", fiches[1]["appreciation"] == "moyen")
verifier("valeur lue malgré l'absence d'accent", fiches[1]["sources"] == ["CNIL"])

doit_echouer("bilan à six domaines", lambda: run.analyser_bilan(
    "\n\n".join(fiche(d) for d in DOMAINES_BILAN[:6])))
doit_echouer("un domaine listé deux fois", lambda: run.analyser_bilan(
    bilan_complet(d7=fiche(DOMAINES_BILAN[0]))))
doit_echouer("intitulé de domaine sans numéro", lambda: run.analyser_bilan(
    bilan_complet(d3=fiche("Recrutement et marché de l'emploi"))))
doit_echouer("numéro de domaine hors des sept", lambda: run.analyser_bilan(
    bilan_complet(d3=fiche("9. Un domaine inventé"))))
doit_echouer("appréciation hors des trois valeurs", lambda: run.analyser_bilan(
    bilan_complet(d4=fiche(DOMAINES_BILAN[3], appreciation="excellent"))))
doit_echouer("clé SOURCES manquante", lambda: run.analyser_bilan(bilan_complet(d5=(
    f"[[DOMAINE: {DOMAINES_BILAN[4]}]]\nRETENUS: aucun\nÉCARTÉS: aucun\n"
    "APPRÉCIATION: vide\n[[/DOMAINE]]"))))
doit_echouer("domaine vide alors que des sujets sont retenus", lambda: run.analyser_bilan(
    bilan_complet(d6=fiche(DOMAINES_BILAN[5], retenus="Un sujet", appreciation="vide"))))
doit_echouer("bloc BILAN sans aucune fiche", lambda: run.analyser_bilan("rien à signaler"))


print("\n[9] Bilan rendu sur disque : format stable, relisible par le script")
rendu = run.rendre_bilan(run.analyser_bilan(riche), "2026-08-30", 12)
verifier("le rendu porte la date du run", "Bilan du run du 2026-08-30" in rendu)
verifier("le nombre de recherches vient du script", "12 recherches web" in rendu)
verifier("aucun chiffre de recherche demandé au modèle",
         "jamais par le modèle" in rendu)
relu = run.analyser_bilan(rendu)
verifier("un bilan rendu se relit à l'identique",
         [f["retenus"] for f in relu] == [f["retenus"] for f in run.analyser_bilan(riche)])
verifier("aller-retour stable sur les sources",
         relu[0]["sources"] == ["Légifrance", "Cour de cassation"])


print("\n[10] Sources de référence lues dans le fichier de domaine")
reference = run.sources_de_reference()
verifier("les sept domaines portent des sources", sorted(reference) == list(range(1, 8)))
verifier("Légifrance est bien une source du domaine 1", "Légifrance" in reference[1])
verifier("Céreq est bien une source du domaine 7", "Céreq" in reference[7])
verifier("aucune liste de sources vide", all(len(v) >= 3 for v in reference.values()))


print("\n[11] etat/performance.md : recalcul cumulatif depuis les bilans")
verifier("sans aucun bilan, le fichier dit qu'aucune évolution n'est justifiable",
         "aucune évolution des règles n'est justifiable" in run.rendre_performance([]))

archives = [
    ("2026-08-02", run.analyser_bilan(bilan_complet(d1=fiche(
        DOMAINES_BILAN[0], retenus="Sujet A", sources="Légifrance",
        appreciation="moyen")))),
    ("2026-08-09", run.analyser_bilan(bilan_complet(d1=fiche(
        DOMAINES_BILAN[0], retenus="Sujet B | Sujet C",
        sources="Légifrance | actuEL RH", appreciation="riche")))),
    ("2026-08-16", run.analyser_bilan(bilan_complet())),
]
perf = run.rendre_performance(archives)
verifier("le nombre de runs bilantés est compté", "3 runs bilantés" in perf)
verifier("la période couverte est indiquée", "du 2026-08-02 au 2026-08-16" in perf)
verifier("total cumulé du domaine 1 : 3 sujets", "Sujets retenus depuis le début : **3**" in perf)
verifier("le domaine 1 a été vide 1 run sur 3",
         "Runs où le domaine n'a rien donné : **1** sur 3" in perf)
verifier("Légifrance est la source la plus productive", "Légifrance (2 runs)" in perf)
verifier("actuEL RH est comptée une fois", "actuEL RH (1 run)" in perf)
verifier("Village de la Justice n'a jamais produit",
         "Village de la Justice" in perf.split("jamais productives")[1].split("\n")[0])
verifier("un domaine muet est vide sur tous les runs",
         perf.count("Runs où le domaine n'a rien donné : **3** sur 3") == 6)
verifier("un domaine muet n'a aucune source productive",
         perf.count("Sources les plus productives : aucune à ce jour") == 6)


print()
if echecs:
    print(f"{len(echecs)} test(s) en échec :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
print("Tous les tests passent.")
