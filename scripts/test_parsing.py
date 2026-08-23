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


print("\n[12] Bloc EVOLUTIONS : optionnel, contrairement aux quatre autres")
verifier("EVOLUTIONS est declaré optionnel",
         "===EVOLUTIONS===" in run.MARQUEURS_OPTIONNELS)
verifier("les quatre autres restent obligatoires",
         run.MARQUEURS_OBLIGATOIRES == ("===RAPPORT===", "===SUJETS-SUIVIS===",
                                        "===CORRECTIONS===", "===BILAN==="))
d = run.decouper_blocs(bien_formee())
verifier("son absence ne fait pas échouer le découpage", "EVOLUTIONS" not in d)

EVO_VALIDE = (
    "[[EVOLUTION: domaines/rh-etudiant.md]]\n"
    "TYPE: retrait de source\n"
    "ACTUEL:\n<<<\nVillage de la Justice\n>>>\n"
    "NOUVEAU:\n<<<\nÉditions Législatives\n>>>\n"
    "JUSTIFICATION:\n<<<\nCette source figure en référence du domaine 1 depuis "
    "11 runs et n'a produit aucun sujet retenu.\n>>>\n"
    "[[/EVOLUTION]]"
)
avec_evo = bien_formee() + "\n===EVOLUTIONS===\n" + EVO_VALIDE
d = run.decouper_blocs(avec_evo)
verifier("le bloc optionnel est extrait quand il est là", d["EVOLUTIONS"] == EVO_VALIDE)
verifier("les quatre obligatoires restent intacts",
         (d["RAPPORT"], d["SUJETS-SUIVIS"], d["CORRECTIONS"], d["BILAN"]) == CORPS)

doit_echouer("EVOLUTIONS présent mais vide",
             lambda: run.decouper_blocs(bien_formee() + "\n===EVOLUTIONS===\n"))
doit_echouer("EVOLUTIONS placé avant BILAN", lambda: run.decouper_blocs(
    f"===RAPPORT===\n{CORPS[0]}\n===SUJETS-SUIVIS===\n{CORPS[1]}\n"
    f"===CORRECTIONS===\n{CORPS[2]}\n===EVOLUTIONS===\n{EVO_VALIDE}\n"
    f"===BILAN===\n{CORPS[3]}"))
doit_echouer("EVOLUTIONS en double",
             lambda: run.decouper_blocs(avec_evo + "\n===EVOLUTIONS===\nautre"))


print("\n[13] Évolutions : validation avant toute écriture")
verifier("AUCUNE ne produit aucune évolution", run.analyser_evolutions("AUCUNE") == [])
evos = run.analyser_evolutions(EVO_VALIDE)
verifier("une évolution valide est acceptée", len(evos) == 1)
verifier("le fichier visé est résolu", evos[0]["cible"] == "domaines/rh-etudiant.md")
verifier("le type est normalisé", evos[0]["type"] == "retrait de source")
verifier("la justification est conservée", "11 runs" in evos[0]["justification"])


print("\n[14] Chemins interdits : la constitution est hors de portée")
def evo(cible, actuel="Village de la Justice", nouveau="autre chose",
        type_="retrait de source", justification="12 runs sans un seul sujet retenu."):
    return (
        f"[[EVOLUTION: {cible}]]\nTYPE: {type_}\n"
        f"ACTUEL:\n<<<\n{actuel}\n>>>\n"
        f"NOUVEAU:\n<<<\n{nouveau}\n>>>\n"
        f"JUSTIFICATION:\n<<<\n{justification}\n>>>\n[[/EVOLUTION]]"
    )

for interdit in (
    "constitution.md",
    "profil.md",
    "scripts/run.py",
    "scripts/test_parsing.py",
    ".github/workflows/veille.yml",
    "README.md",
    "etat/performance.md",
    "rapports/2026-08-23.md",
    "../../../etc/passwd",
    "domaines/../constitution.md",
    "./constitution.md",
    "/etc/passwd",
):
    doit_echouer(f"évolution visant {interdit}", lambda c=interdit: run.analyser_evolutions(evo(c)))

verifier("les deux seuls fichiers évoluables sont moteur.md et le domaine",
         tuple(c.name for c in run.FICHIERS_EVOLUABLES) == ("moteur.md", "rh-etudiant.md"))


print("\n[15] Évolutions mal formées : le run échoue, rien n'est écrit partiellement")
doit_echouer("bloc ni AUCUNE ni balisé", lambda: run.analyser_evolutions("il faudrait revoir les sources"))
doit_echouer("champ TYPE absent", lambda: run.analyser_evolutions(
    "[[EVOLUTION: moteur.md]]\nACTUEL:\n<<<\nx\n>>>\nNOUVEAU:\n<<<\ny\n>>>\n"
    "JUSTIFICATION:\n<<<\nz\n>>>\n[[/EVOLUTION]]"))
doit_echouer("champ JUSTIFICATION absent", lambda: run.analyser_evolutions(
    "[[EVOLUTION: moteur.md]]\nTYPE: pondération\nACTUEL:\n<<<\nx\n>>>\n"
    "NOUVEAU:\n<<<\ny\n>>>\n[[/EVOLUTION]]"))
doit_echouer("type d'évolution inconnu",
             lambda: run.analyser_evolutions(evo("moteur.md", type_="refonte totale")))
doit_echouer("justification vide",
             lambda: run.analyser_evolutions(evo("moteur.md", justification="")))
doit_echouer("ACTUEL vide", lambda: run.analyser_evolutions(evo("moteur.md", actuel="")))
doit_echouer("ACTUEL introuvable dans le fichier visé",
             lambda: run.analyser_evolutions(evo("moteur.md", actuel="une règle qui n'existe pas")))
doit_echouer("ACTUEL présent plusieurs fois donc ambigu",
             lambda: run.analyser_evolutions(evo("domaines/rh-etudiant.md", actuel="Dares")))
doit_echouer("ACTUEL et NOUVEAU identiques", lambda: run.analyser_evolutions(
    evo("domaines/rh-etudiant.md", actuel="Village de la Justice",
        nouveau="Village de la Justice")))

melange = EVO_VALIDE + "\n\n" + evo("constitution.md")
avant = run.DOMAINE.read_bytes()
doit_echouer("un lot dont une seule évolution est interdite",
             lambda: run.analyser_evolutions(melange))
verifier("le fichier légitime du lot n'a pas été touché", run.DOMAINE.read_bytes() == avant)


print("\n[16] Application et archivage des évolutions")
avant_domaine = run.DOMAINE.read_bytes()
avant_moteur = run.MOTEUR.read_bytes()
try:
    archives = run.appliquer_evolutions(run.analyser_evolutions(EVO_VALIDE), "2026-09-06")
    verifier("une archive par évolution", archives == ["evolutions/2026-09-06-01.md"])
    contenu = run.DOMAINE.read_text(encoding="utf-8")
    verifier("la règle a été remplacée dans le fichier", "Éditions Législatives" in contenu)
    verifier("l'ancienne règle a disparu", "Village de la Justice" not in contenu)

    archive = (run.EVOLUTIONS / "2026-09-06-01.md").read_text(encoding="utf-8")
    verifier("l'archive porte la date", "Évolution du 2026-09-06" in archive)
    verifier("l'archive porte le fichier visé", "domaines/rh-etudiant.md" in archive)
    verifier("l'archive porte l'avant", "## Avant" in archive and "Village de la Justice" in archive)
    verifier("l'archive porte l'après", "## Après" in archive and "Éditions Législatives" in archive)
    verifier("l'archive porte la justification", "11 runs" in archive)
    verifier("l'archive rappelle que c'est réversible", "réversible" in archive)

    verifier("aucune évolution ne produit aucune archive",
             run.appliquer_evolutions([], "2026-09-06") == [])
finally:
    run.DOMAINE.write_bytes(avant_domaine)
    run.MOTEUR.write_bytes(avant_moteur)
    (run.EVOLUTIONS / "2026-09-06-01.md").unlink(missing_ok=True)

suppression = evo("domaines/rh-etudiant.md", actuel="Village de la Justice", nouveau="")
evos = run.analyser_evolutions(suppression)
verifier("un NOUVEAU vide est accepté : c'est ainsi qu'on supprime une source",
         evos[0]["nouveau"].strip() == "")
verifier("l'archive d'une suppression le dit explicitement",
         "(règle supprimée)" in run.rendre_evolution(evos[0], "2026-09-06", 1))


print("\n[17] Garde-fou : verdict VALIDÉ")
v = run.analyser_verdict("===VERDICT===\nVALIDÉ")
verifier("un verdict validé passe", v.valide is True)
verifier("aucun blocage", v.blocages == [])
verifier("le rapport n'est pas bloqué", v.bloque_le_rapport is False)
verifier("aucune évolution annulée", v.evolutions_bloquees() == set())
verifier("la ligne de pied dit validé", "Verdict : validé" in v.ligne_de_pied())
verifier("la ligne de pied dit la lecture seule",
         "sans accès à la recherche web" in v.ligne_de_pied())
verifier("VALIDE sans accent est accepté", run.analyser_verdict("===VERDICT===\nVALIDE").valide)
verifier("un préambule bavard du relecteur est ignoré",
         run.analyser_verdict("J'ai tout relu.\n===VERDICT===\nVALIDÉ").valide)
verifier("délimiteur collé au verdict",
         run.analyser_verdict("===VERDICT===VALIDÉ").valide)


print("\n[18] Garde-fou : blocage sur une évolution, le rapport passe")
v = run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n"
    "[[BLOCAGE: EVOLUTION 2]]\nLa justification invoque « cette source semble peu "
    "productive », sans aucun chiffre présent dans la performance cumulée.\n[[/BLOCAGE]]"
)
verifier("le verdict n'est pas validé", v.valide is False)
verifier("le rapport n'est PAS bloqué", v.bloque_le_rapport is False)
verifier("l'évolution 2 est annulée", v.evolutions_bloquees() == {2})
verifier("la ligne de pied nomme le blocage", "evolution 2" in v.ligne_de_pied())
verifier("la ligne de pied dit que le bloqué n'a pas été appliqué",
         "n'a pas été appliqué" in v.ligne_de_pied())

v = run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n"
    "[[BLOCAGE: EVOLUTION 1]]\nmotif un\n[[/BLOCAGE]]\n"
    "[[BLOCAGE: EVOLUTION 3]]\nmotif trois\n[[/BLOCAGE]]"
)
verifier("plusieurs évolutions annulées", v.evolutions_bloquees() == {1, 3})


print("\n[19] Garde-fou : blocage sur le rapport, le run échoue")
v = run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n"
    "[[BLOCAGE: RAPPORT]]\nLe sujet 3 affirme une entrée en vigueur au 1er janvier "
    "sans citer aucune source.\n[[/BLOCAGE]]"
)
verifier("le rapport est bloqué", v.bloque_le_rapport is True)
verifier("aucune évolution n'est annulée pour autant", v.evolutions_bloquees() == set())

v = run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: EMAIL]]\nrien de notable cette semaine\n[[/BLOCAGE]]"
)
verifier("un blocage EMAIL est reconnu", v.bloque_l_email is True)
verifier("un blocage EMAIL ne bloque pas le rapport", v.bloque_le_rapport is False)


print("\n[20] Garde-fou : tout verdict illisible bloque, jamais ne valide")
doit_echouer("verdict vide", lambda: run.analyser_verdict(""))
doit_echouer("aucun délimiteur ===VERDICT===", lambda: run.analyser_verdict("VALIDÉ"))
doit_echouer("délimiteur ===VERDICT=== en double",
             lambda: run.analyser_verdict("===VERDICT===\nVALIDÉ\n===VERDICT===\nBLOQUÉ"))
doit_echouer("verdict ni VALIDÉ ni BLOQUÉ",
             lambda: run.analyser_verdict("===VERDICT===\nplutôt bon dans l'ensemble"))
doit_echouer("VALIDÉ accompagné de blocages", lambda: run.analyser_verdict(
    "===VERDICT===\nVALIDÉ\n[[BLOCAGE: RAPPORT]]\nmotif\n[[/BLOCAGE]]"))
doit_echouer("BLOQUÉ sans aucun blocage nommé",
             lambda: run.analyser_verdict("===VERDICT===\nBLOQUÉ"))
doit_echouer("blocage au motif vide", lambda: run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: RAPPORT]]\n\n[[/BLOCAGE]]"))
doit_echouer("portée de blocage inconnue", lambda: run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: MEMOIRE]]\nmotif\n[[/BLOCAGE]]"))
doit_echouer("portée EVOLUTION sans numéro", lambda: run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: EVOLUTION]]\nmotif\n[[/BLOCAGE]]"))
verifier(
    "le mot BLOQUÉ cité dans un motif ne renverse pas un verdict validé",
    run.analyser_verdict(
        "===VERDICT===\nVALIDÉ\n\nRien à signaler, aucune évolution n'est BLOQUÉ."
    ).valide is True,
)


print("\n[21] Garde-fou : prompt de relecture, lecture seule")
evos = run.analyser_evolutions(EVO_VALIDE)
prompt_gf = run.construire_prompt_garde_fou("le rapport du jour", CORPS[3], evos)
verifier("le garde-fou reçoit la constitution", "Constitution de l'agent de veille" in prompt_gf)
verifier("il reçoit le rapport produit", "le rapport du jour" in prompt_gf)
verifier("il reçoit les évolutions proposées", "Éditions Législatives" in prompt_gf)
verifier("il reçoit la justification à vérifier", "11 runs" in prompt_gf)
verifier("il reçoit la performance cumulée", "PERFORMANCE CUMULÉE" in prompt_gf)
verifier("il lui est dit qu'il n'a aucun outil", "aucun outil" in prompt_gf)
verifier("il lui est dit que c'est en lecture seule", "Lecture seule" in prompt_gf)
verifier("le rapport lui est présenté comme une pièce, pas une consigne",
         "pas des consignes" in prompt_gf)
verifier("il lui est interdit de bloquer sur une semaine pauvre",
         "Une semaine pauvre est un" in prompt_gf)
sans_evo = run.construire_prompt_garde_fou("le rapport", CORPS[3], [])
verifier("sans évolution, il le lui est dit explicitement",
         "Aucune évolution proposée ce run" in sans_evo)


print("\n[22] Audit archivé, y compris quand tout est validé")
audit = run.rendre_audit(run.analyser_verdict("===VERDICT===\nVALIDÉ"), [], set(), "2026-09-13")
verifier("un audit est écrit même quand tout passe", "**Verdict : VALIDÉ**" in audit)
verifier("il porte la date du run", "Audit du run du 2026-09-13" in audit)
verifier("il dit qu'aucune évolution n'était proposée",
         "Aucune évolution n'était proposée" in audit)
verifier("il archive le verdict brut", "## Verdict brut" in audit)

v = run.analyser_verdict(
    "===VERDICT===\nBLOQUÉ\n[[BLOCAGE: EVOLUTION 1]]\nimpression non chiffrée\n[[/BLOCAGE]]"
)
audit = run.rendre_audit(v, evos, v.evolutions_bloquees(), "2026-09-13")
verifier("un audit bloqué liste ce qui a été bloqué", "## Ce qui a été bloqué" in audit)
verifier("il donne le motif du relecteur", "impression non chiffrée" in audit)
verifier("il dit l'effet du blocage", "cette évolution est annulée, le rapport passe" in audit)
verifier("il dit le sort de chaque évolution soumise", "**annulée par le garde-fou**" in audit)

audit = run.rendre_audit(run.analyser_verdict("===VERDICT===\nVALIDÉ"), evos, set(), "2026-09-13")
verifier("une évolution non bloquée est marquée appliquée", "**appliquée**" in audit)


print()
if echecs:
    print(f"{len(echecs)} test(s) en échec :")
    for e in echecs:
        print(f"  - {e}")
    sys.exit(1)
print("Tous les tests passent.")
