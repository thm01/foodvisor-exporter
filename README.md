# Foodvisor Exporter

[English](README.en.md) · Français

Foodvisor Exporter permet d'exporter les données du journal de son propre compte Foodvisor en JSON, CSV et XLSX. Le projet est **non officiel, indépendant et non affilié à Foodvisor**. Il utilise une API privée qui peut changer ou refuser ses requêtes ; vérifiez les [conditions d'utilisation de Foodvisor](https://www.foodvisor.io/fr/terms-of-service/raw/) avant de l'utiliser.

## Installation et lancement

Téléchargez le dépôt, extrayez-le, puis installez **Python 3.9 ou plus récent**. Les lanceurs vérifient ce prérequis et affichent une erreur s'il manque ; ils ne l'installent pas. Un navigateur web récent est nécessaire.

| Système | Fichier à ouvrir |
| --- | --- |
| Windows | `Foodvisor-exporter-windows.cmd` |
| macOS | `Foodvisor-exporter-macos.command` |
| Linux | `Foodvisor-exporter-linux.sh` |

Si le gestionnaire de fichiers n'exécute pas le lanceur Linux, ouvrez un terminal dans le dossier du projet et lancez `bash Foodvisor-exporter-linux.sh`. Sur macOS, le fichier `.command` s'ouvre dans Terminal. On peut aussi démarrer l'interface directement avec `python3 app/web_interface.py` (ou `py -3 app\web_interface.py` sous Windows). Le programme ouvre automatiquement une page dans le navigateur ; si cela échoue, copiez l'adresse locale affichée dans le terminal.

L'application fonctionne sans autre bibliothèque Python. Pour activer l'option facultative de mémorisation du mot de passe dans le coffre du système, installez `keyring` avec `python3 -m pip install keyring` (ou `py -3 -m pip install keyring` sous Windows). Le coffre du système doit aussi être disponible ; sinon, la connexion manuelle reste possible. Les archives construites par le workflow GitHub Actions incluent `keyring` et Python : elles ne demandent pas d'installation séparée de Python.

## Utilisation de l'interface

1. Choisissez la langue de l'interface en haut de la page. Ce réglage ne modifie pas la langue des données.
2. Saisissez l'adresse e-mail et le mot de passe de votre compte Foodvisor personnel. Le pays reprend le dernier code utilisé ou, au premier lancement, la région de l'ordinateur si elle est disponible. Choisissez un code si le champ reste vide. La langue des données (`fr` ou `en`) est modifiable ; elle détermine les réponses demandées à Foodvisor et les libellés CSV/XLSX.
3. Cliquez sur **Se connecter**. La fenêtre attend la réponse de Foodvisor et active la période et l'export seulement si un jeton d'accès a été reçu. Si la réponse contient les préférences du compte, elle renseigne automatiquement le pays alimentaire et la langue prise en charge. Vous pouvez cocher **Mémoriser le mot de passe dans le coffre système** avant de vous connecter ; cette option reste désactivée si aucun coffre compatible n'est disponible.
4. Choisissez la période au format **JJ-MM-AAAA** ou avec les calendriers, puis le dossier de destination. Vous pouvez saisir son chemin ou le choisir dans l'explorateur de dossiers de la page. Lancez ensuite l'export. La page affiche la progression et les erreurs. **Annuler** arrête le traitement entre deux requêtes ; une requête déjà en cours peut prendre jusqu'à 30 secondes.

Le champ « Pays » propose les codes ISO à deux lettres `BE`, `FR`, `CH`, `LU`, `CA`, `US`, `GB`, `DE`, `ES` et `IT`. Ce sont des suggestions, pas une liste de pays officiellement confirmés par Foodvisor. La région de l'ordinateur est seulement une proposition : elle peut différer du pays alimentaire du compte. Le code choisi entre dans l'URL de l'API ; un code ISO valide peut néanmoins être refusé par le service.

Chaque export réussi crée un dossier horodaté avec `historique.json`, `Foodvisor.csv`, `Foodvisor.xlsx`, `EXPORT_TERMINE.txt` et les réponses JSON brutes dans `donnees-brutes/`. Ces fichiers peuvent contenir des données personnelles sensibles : conservez-les dans un emplacement privé. L'option de conversion des données déjà téléchargées fonctionne sans connexion à Foodvisor ; son avancement et son résultat s'affichent dans la fenêtre. Le diagnostic peut être effacé avec le bouton prévu à cet effet.

**Se déconnecter** efface le jeton en mémoire et reverrouille l'export. Le pays et la langue des données restent modifiables après connexion ; leurs changements s'appliquent au prochain export sans nouvelle connexion. Pour changer de compte, déconnectez-vous d'abord. La conversion hors ligne reste accessible sans connexion. **Oublier le mot de passe** le retire du coffre système ; décocher l'option de mémorisation a le même effet.

La page communique uniquement avec un serveur local lié à `127.0.0.1`. Le programme Python contacte Foodvisor ; le navigateur ne le contacte pas directement. Utilisez **Quitter** dans la page pour arrêter le serveur local. La langue de l'interface et, après une tentative de connexion, l'adresse e-mail sont mémorisées localement. Le jeton n'est jamais enregistré sur disque. L'application n'enregistre le mot de passe que si vous activez explicitement le coffre système ; votre navigateur peut proposer séparément de le mémoriser. Pour la connexion, l'application transmet le mot de passe directement à Foodvisor par HTTPS. Elle n'envoie pas les identifiants au créateur du projet.

## Ligne de commande

Pour exporter sans interface graphique :

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

Dans le terminal, les dates utilisent le format **AAAA-MM-JJ**. `--start` est requis pour un téléchargement ; `--end` prend la date du jour par défaut. Les dates sont inclusives. Le pays (`--country`) et la langue des données (`--locale`) valent respectivement `BE` et `fr` par défaut. `--locale en` demande les données en anglais et produit des libellés CSV/XLSX en anglais. Le programme demande les identifiants dans le terminal, puis crée les fichiers dans `exports/<horodatage>/`.

Pour convertir à nouveau des réponses déjà téléchargées, sans connexion :

```bash
bash Foodvisor-exporter.sh --source exports/<horodatage>/donnees-brutes
```

Une commande normale se termine après un export. Pour en lancer plusieurs dans la même console en réutilisant la session, utilisez `bash Foodvisor-exporter.sh --interactive`. Saisissez une période au format **AAAA-MM-JJ** pour chaque export, puis laissez la date de début vide pour quitter. Le mot de passe est redemandé seulement si la session n'est plus valide. Il n'est pas conservé sur disque.

## Limites

L'exporteur lit le journal du compte authentifié et les fiches alimentaires référencées par ce journal. Il ne parcourt pas le catalogue général, ne modifie pas le compte et n'effectue aucune synchronisation. Les requêtes sont séquentielles, espacées d'une seconde ; cette précaution ne garantit pas leur acceptation par Foodvisor.

L'API peut changer, et les résultats peuvent être incomplets si le journal n'est pas synchronisé. Les noms de plats et d'aliments proviennent de Foodvisor et ne sont pas traduits localement. L'outil ne renouvelle pas les jetons, ne télécharge pas les images et ne programme pas d'export automatique. Vérifiez les fichiers obtenus avant de vous y fier.

Le dépôt ne contient aucun APK, code décompilé, secret extrait de l'application ou donnée de compte. Pour demander officiellement vos données, consultez la [politique de confidentialité de Foodvisor](https://www.foodvisor.io/fr/privacy-policy/raw/).
