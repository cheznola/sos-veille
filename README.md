# sos-veille

Un agent qui fait votre veille sectorielle chaque semaine, tout seul, et qui se
souvient de ce qu'il vous a déjà dit.

Tous les dimanches à 1 h du matin, il part chercher sur le web ce qui a bougé dans
votre secteur, trie, écarte le bruit, et dépose un rapport de cinq à huit sujets dans
ce dépôt. Il tient aussi une liste des dossiers en cours — un décret pas encore publié,
une négociation ouverte — et il les suit d'une semaine sur l'autre. Quand l'un d'eux
aboutit et qu'il s'était trompé, il revient corriger son ancien rapport.

Vous n'avez rien à faire. Vous lisez.

---

## Ce que ça produit

Un fichier par semaine dans `rapports/`, nommé par sa date. Chaque rapport contient :

- une **ligne de périmètre** : période couverte, nombre de recherches, sujets retenus ;
- une **révision**, s'il y avait une erreur passée à corriger ;
- les **sujets retenus**, chacun avec ce qui s'est passé, pourquoi ça vous concerne, la
  source avec son lien, et son statut dans le suivi ;
- un bloc **« Ce que tu peux en faire cette semaine »** : une action concrète par sujet.

Cinq à huit sujets maximum. Souvent moins. L'agent a pour consigne explicite de ne pas
remplir : une semaine calme est une information, pas un échec.

---

## Comment c'est fait

Deux fichiers, et c'est toute l'idée du projet.

**`moteur.md`** contient la méthode : comment chercher, en combien de passes, quand
relancer parce que le bruit domine, comment écrire, quand se corriger. Il ne mentionne
aucun secteur. Il ne sait pas dans quel domaine il travaille.

**`domaines/rh-etudiant.md`** contient le secteur : les sept domaines à couvrir, les
sources de référence, et surtout la liste de ce qui est du bruit dans ce secteur-là.

Le moteur ne connaît pas le domaine, le domaine ne connaît pas la méthode. C'est ce qui
permet de changer complètement de secteur en réécrivant un seul fichier.

À côté, **`profil.md`** décrit la personne servie : ce qu'elle fait de cette veille, ce
qui l'intéresse, ce qui ne lui sert à rien. C'est ce fichier qui rend les
recommandations utiles plutôt que génériques.

Et **`etat/sujets-suivis.md`** est la mémoire. L'agent la réécrit à chaque run.

### Les fichiers, un par un

| Fichier | À quoi il sert | Qui l'écrit |
|---|---|---|
| `moteur.md` | La méthode de veille, indépendante du secteur | vous, rarement |
| `domaines/rh-etudiant.md` | Les sujets, sources et bruit d'un secteur | vous |
| `profil.md` | La personne servie et ses usages | vous |
| `etat/sujets-suivis.md` | Les dossiers en cours, suivis d'une semaine sur l'autre | l'agent |
| `rapports/AAAA-MM-JJ.md` | Un rapport par run | l'agent |
| `scripts/run.py` | Le script qui assemble tout et appelle le modèle | — |
| `.github/workflows/veille.yml` | Le déclencheur hebdomadaire | — |

---

## Le mettre en place

Il faut un compte GitHub et une clé d'API Anthropic. Comptez dix minutes.

**1. Forkez ce dépôt** — bouton *Fork* en haut à droite. Vous obtenez votre propre copie.

**2. Ajoutez votre clé d'API.** Dans votre copie : *Settings* → *Secrets and variables*
→ *Actions* → *New repository secret*. Nom exact : `ANTHROPIC_API_KEY`. Valeur : votre
clé, qui commence par `sk-ant-`. Elle se crée sur
[console.anthropic.com](https://console.anthropic.com) → *API Keys*.

> **Ne commitez jamais votre clé**, nulle part : ni dans le code, ni dans un fichier
> de configuration, ni dans un message de commit. Elle passe toujours par les secrets
> du repo. Ce repo est public, et un secret commité reste dans l'historique même
> après suppression. En cas de doute, révoquez-la : la marche à suivre est dans
> [SECURITY.md](SECURITY.md).

**3. Autorisez les workflows.** Onglet *Actions* → *I understand my workflows, go ahead
and enable them*. Sur un dépôt forké, GitHub les désactive par défaut.

**4. Vérifiez les droits d'écriture.** *Settings* → *Actions* → *General* → section
*Workflow permissions* → cochez *Read and write permissions*. Sans ça, l'agent produira
son rapport mais ne pourra pas l'enregistrer.

**5. Relisez `profil.md` et le fichier de domaine.** Les deux versions livrées sont des
premières versions plausibles, pas des versions justes. Tant qu'elles ne décrivent pas
votre réalité, les rapports seront à côté.

**6. Lancez un run à la main pour vérifier.** Onglet *Actions* → *Veille hebdomadaire*
→ *Run workflow*. Comptez cinq à quinze minutes. Le rapport apparaît ensuite dans
`rapports/`.

Ensuite, ça tourne tout seul chaque dimanche à 1 h UTC.

---

## Changer de secteur

C'est le point du projet : passer des ressources humaines à l'immobilier, à la
logistique ou à la cybersécurité ne demande pas de toucher au moteur.

**1. Écrivez votre fichier de domaine.** Copiez `domaines/rh-etudiant.md` sous un
nouveau nom, par exemple `domaines/logistique.md`, et remplacez son contenu. Gardez la
structure : un périmètre géographique, sept domaines (chacun avec ses sources de
référence nommées), puis la liste de ce qui est du bruit dans ce secteur.

La section « bruit » est celle qui fait la différence entre un rapport utile et un flux
d'actualités. Soyez précis et sans pitié : les études d'éditeurs, les listes de
tendances, les communiqués recyclés. C'est là que se gagne la qualité.

**2. Pointez le script sur votre fichier.** Dans `scripts/run.py`, ligne 25 environ :

```python
DOMAINE = RACINE / "domaines" / "rh-etudiant.md"
```

Remplacez `rh-etudiant.md` par le nom de votre fichier.

**3. Réécrivez `profil.md`.** Qui lit, pour quoi faire, ce qui l'intéresse et ce qui ne
lui sert à rien. Soyez concret : c'est de ce fichier que dépend la qualité des actions
proposées.

**4. Videz la mémoire et les rapports.** Remettez `etat/sujets-suivis.md` dans son état
initial (les deux sections « En cours » et « Clos » vides) et supprimez le contenu de
`rapports/`. Une mémoire d'un autre secteur produirait des recoupements absurdes.

**Ne touchez pas à `moteur.md`.** Il vaut pour n'importe quel secteur. Vous ne le
modifiez que si vous voulez changer la *méthode* — plus de sujets, un autre format de
rapport, trois passes de recherche au lieu de deux.

---

## Les réglages courants

Tous dans `scripts/run.py`, en haut du fichier :

| Réglage | Par défaut | Ce que ça change |
|---|---|---|
| `DOMAINE` | `domaines/rh-etudiant.md` | Le fichier de secteur utilisé |
| `NB_RAPPORTS_RELUS` | `3` | Combien de rapports passés l'agent relit avant de chercher |
| `MODELE` | `claude-sonnet-4-6` | Le modèle appelé |
| `MAX_TOKENS` | `32000` | La longueur maximale de la réponse |

Le jour et l'heure du run se changent dans `.github/workflows/veille.yml`, ligne
`- cron: "0 1 * * 0"` — dans l'ordre : minute, heure, jour du mois, mois, jour de la
semaine (`0` = dimanche), toujours en UTC.

Le nombre de sujets par rapport, lui, n'est pas un réglage technique : il est écrit
dans `moteur.md`, section « Sélection ».

---

## Quand ça casse

Le script est volontairement strict : **si quelque chose ne va pas, il s'arrête et
n'écrit rien du tout**. Jamais de rapport à moitié écrit, jamais de mémoire corrompue.
Vous relancez, c'est tout.

Les messages d'erreur sont en français et disent quoi faire. Les cas courants :

- *ANTHROPIC_API_KEY absent* — le secret n'est pas créé, ou son nom est mal orthographié.
- *Bloc manquant dans la réponse du modèle* — le modèle n'a pas respecté le format.
  Relancez ; si ça se répète, c'est le signe qu'un des fichiers de contexte est devenu
  trop long ou contradictoire.
- *Réponse tronquée* — augmentez `MAX_TOKENS`.
- *Correction visant un rapport inexistant* — le modèle a cité un rapport qui n'existe
  pas. Le run s'arrête plutôt que d'écrire à côté. Relancez.
- Le run réussit mais rien n'apparaît dans le dépôt — les droits d'écriture du workflow
  ne sont pas activés (étape 4 de la mise en place).

Pour voir ce qui s'est passé : onglet *Actions*, cliquez sur le run, dépliez l'étape
*Lancer le run de veille*.

---

## Ce que ça coûte

Un run par semaine, un appel au modèle par run, avec de la recherche web. À la publication
de ce dépôt, `claude-sonnet-4-6` est facturé 3 $ par million de tokens en entrée et 15 $
par million en sortie, et les recherches web sont facturées à part. Un run typique reste
de l'ordre de quelques dizaines de centimes ; comptez quelques euros par an. Les tarifs
à jour sont sur [claude.com/pricing](https://claude.com/pricing).

---

## Le faire tourner sur votre machine

Pour tester sans attendre dimanche :

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/run.py
```

Le script écrit les mêmes fichiers qu'en automatique. À vous de committer ensuite si le
résultat vous convient.
