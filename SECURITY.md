# Sécurité

Ce repo est public. Son code, sa méthode et tous ses rapports sont lisibles par
n'importe qui. Une seule chose ne doit jamais y figurer : la clé d'API.

## Où vit la clé

La clé d'API Anthropic vit à un seul endroit : les **secrets GitHub Actions** du
repo, sous le nom `ANTHROPIC_API_KEY`.

*Settings > Secrets and variables > Actions*

GitHub la chiffre, ne la réaffiche jamais après création, et la masque
automatiquement dans les journaux d'exécution. Le workflow l'injecte comme
variable d'environnement le temps du run, et rien d'autre.

## Ce que le code fait, et ne fait pas

`scripts/run.py` lit la clé **uniquement** depuis la variable d'environnement :

```python
client = anthropic.Anthropic()   # le SDK lit ANTHROPIC_API_KEY dans l'environnement
```

Aucune clé n'est écrite en dur, aucune n'est passée en argument, aucune n'est
journalisée. Si la variable est absente, le script s'arrête avec un message
explicite plutôt que de tenter quoi que ce soit.

## Les règles

1. **Ne commite jamais une clé.** Ni dans le code, ni dans un fichier de
   configuration, ni dans un commentaire, ni dans un message de commit.
2. **En local, utilise l'environnement**, pas un fichier suivi par git :
   `export ANTHROPIC_API_KEY=...` avant de lancer le script.
3. Si tu as besoin d'un fichier, appelle-le `.env` : le `.gitignore` couvre
   `.env`, `.env.*`, `*.env`, `secrets.*`, `*credentials*.json`, `*.pem`, `*.key`.
4. **Un secret commité est un secret compromis**, même supprimé au commit
   suivant : il reste dans l'historique, et l'historique est public.

## En cas de doute, révoquer

Le doute suffit. Une clé qu'on soupçonne exposée se révoque, elle ne s'audite pas.

1. Va sur [console.anthropic.com](https://console.anthropic.com) > *API Keys*.
2. Trouve la clé concernée et **révoque-la** (*Delete* ou *Revoke*). Elle cesse
   immédiatement de fonctionner, où qu'elle se trouve.
3. Crée une nouvelle clé.
4. Dans le repo : *Settings > Secrets and variables > Actions*, ouvre
   `ANTHROPIC_API_KEY` et remplace la valeur par la nouvelle.
5. Relance un run à la main (*Actions > Veille hebdomadaire > Run workflow*)
   pour vérifier que tout repart.
6. Si la clé était réellement dans un commit, la révocation reste la seule
   mesure qui compte. Réécrire l'historique ne suffit pas : le secret a pu être
   copié pendant qu'il était en ligne.

## Vérifier que l'historique est propre

```bash
git log -p --all | grep -inE "sk-ant-[a-zA-Z0-9_-]{20,}|sk-[a-zA-Z0-9]{32,}"
```

Aucune sortie signifie qu'aucun matériel de clé n'a jamais été commité.

## Signaler un problème

Ouvre une issue sur le repo **sans y recopier le secret concerné**. Décris où il
se trouve, pas ce qu'il contient.
