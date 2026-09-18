# Foodvisor Exporter

[English](README.en.md) · Français

Foodvisor Exporter permet d'exporter les données du journal de son propre compte Foodvisor en JSON, CSV et XLSX. Le projet est **non officiel, indépendant et non affilié à Foodvisor**. Il utilise une API privée qui peut changer ou refuser ses requêtes ; vérifiez les [conditions d'utilisation de Foodvisor](https://www.foodvisor.io/fr/terms-of-service/raw/) avant de l'utiliser.

## Installation et lancement

Le code source nécessite [**Python 3.9 ou plus récent**](https://www.python.org/downloads/) et un navigateur récent. Les archives exécutables, lorsqu'elles sont disponibles, incluent Python.

| Système | Fichier à ouvrir |
| --- | --- |
| Windows | `Foodvisor-exporter-windows.cmd` |
| macOS | `Foodvisor-exporter-macos.command` |
| Linux | `Foodvisor-exporter-linux.sh` |

Si le gestionnaire de fichiers n'exécute pas le lanceur Linux, ouvrez un terminal dans le dossier du projet et lancez `bash Foodvisor-exporter-linux.sh`. Sur macOS, le fichier `.command` s'ouvre dans Terminal. On peut aussi démarrer l'interface directement avec `python3 app/web_interface.py` (ou `py -3 app\web_interface.py` sous Windows). Le programme ouvre automatiquement une page dans le navigateur ; si cela échoue, copiez l'adresse locale affichée dans le terminal.

La version source fonctionne sans dépendance supplémentaire. Pour mémoriser le mot de passe dans le coffre système, installez facultativement `keyring` avec `python3 -m pip install keyring` (ou `py -3 -m pip install keyring` sous Windows).

## Utilisation de l'interface

1. Choisissez la langue de l'interface dans le menu en haut à droite. La langue des données la suit par défaut.
2. Saisissez l'adresse e-mail et le mot de passe de votre compte Foodvisor personnel. Le volet **Options avancées** permet de modifier le pays détecté et la langue des données ; il s'ouvre automatiquement si aucun pays n'a été trouvé.
3. Cliquez sur **Se connecter**. La période et l'export s'activent après la réponse de Foodvisor. Les préférences du compte peuvent renseigner le pays et la langue des données, sauf si vous avez choisi cette dernière manuellement. Le coffre système peut mémoriser le mot de passe s'il est disponible.
4. Choisissez les dates dans les calendriers, puis le dossier de destination. Vous pouvez saisir son chemin ou le choisir dans l'explorateur de dossiers de la page. Lancez ensuite l'export. La page affiche la progression et les erreurs. **Annuler** arrête le traitement entre deux requêtes ; une requête déjà en cours peut prendre jusqu'à 30 secondes.

Le menu « Pays » propose des pays courants et « Autre pays » pour saisir un code ISO à deux lettres. Foodvisor peut refuser certains codes.

Chaque export réussi crée un dossier horodaté avec `historique.json`, `Foodvisor.csv`, `Foodvisor.xlsx`, `EXPORT_TERMINE.txt` et les réponses JSON brutes dans `sources/`. Les activités figurent aussi dans `Foodvisor-activities.csv` et `.json` ; leur total quotidien apparaît dans `Foodvisor-days.csv` et le classeur. Ces fichiers peuvent contenir des données personnelles sensibles : conservez-les dans un emplacement privé. La conversion des données déjà téléchargées fonctionne sans connexion à Foodvisor.
Les libellés des exports suivent la langue des données choisie. Une origine d'activité inconnue apparaît comme « Autre », avec sa valeur Foodvisor conservée dans une colonne distincte.
Les activités saisies manuellement dans Foodvisor sont exportées lorsqu’elles figurent dans le journal reçu. Les activités issues de Santé Connect ou d’Apple Santé peuvent manquer : l’exporteur ne lit pas directement les données du téléphone.

**Se déconnecter** efface le jeton en mémoire et reverrouille l'export. Le pays et la langue des données restent modifiables après connexion ; leurs changements s'appliquent au prochain export sans nouvelle connexion. Pour changer de compte, déconnectez-vous d'abord. La conversion hors ligne reste accessible sans connexion. **Oublier le mot de passe** le retire du coffre système ; décocher l'option de mémorisation a le même effet.

L'interface utilise un serveur local (`127.0.0.1`), qui contacte Foodvisor par HTTPS. **Quitter** l'arrête ; fermer la page l'arrête après environ deux minutes d'inactivité. Le jeton reste en mémoire et le mot de passe n'est mémorisé que si vous activez le coffre système.

## Ligne de commande

Pour exporter sans interface graphique :

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

Dans le terminal, les dates utilisent le format **AAAA-MM-JJ**. `--start` est requis pour un téléchargement ; `--end` prend la date du jour par défaut. Les dates sont inclusives. Le pays (`--country`) et la langue des données (`--locale`) valent respectivement `BE` et `fr` par défaut. `--locale en` demande les données en anglais et produit des libellés CSV/XLSX en anglais. Le programme demande les identifiants dans le terminal, puis crée les fichiers dans `exports/<horodatage>/`.

Pour convertir à nouveau des réponses déjà téléchargées, sans connexion :

```bash
bash Foodvisor-exporter.sh --source exports/<horodatage>/sources
```

Une commande normale se termine après un export. Pour en lancer plusieurs dans la même console en réutilisant la session, utilisez `bash Foodvisor-exporter.sh --interactive`. Saisissez une période au format **AAAA-MM-JJ** pour chaque export, puis laissez la date de début vide pour quitter. Le mot de passe est redemandé seulement si la session n'est plus valide. Il n'est pas conservé sur disque.
Les anciens dossiers `donnees-brutes/` restent utilisables avec `--source` ou la conversion dans l'interface.

## Limites

L'exporteur lit le journal du compte authentifié et les fiches alimentaires référencées par ce journal. Il ne parcourt pas le catalogue général, ne modifie pas le compte et n'effectue aucune synchronisation. Les requêtes sont séquentielles, espacées d'une seconde ; cette précaution ne garantit pas leur acceptation par Foodvisor.

L'API peut changer, et les résultats peuvent être incomplets si le journal n'est pas synchronisé. Les noms de plats et d'aliments proviennent de Foodvisor et ne sont pas traduits localement. L'outil ne renouvelle pas les jetons, ne télécharge pas les images et ne programme pas d'export automatique. Vérifiez les fichiers obtenus avant de vous y fier.
Les kcal dépensées par jour sont la somme des `calories_burned` des activités reçues ; ce chiffre peut différer du bilan affiché par Foodvisor.

Le dépôt ne contient aucun APK, code décompilé, secret extrait de l'application ou donnée de compte. Pour demander officiellement vos données, consultez la [politique de confidentialité de Foodvisor](https://www.foodvisor.io/fr/privacy-policy/raw/).
