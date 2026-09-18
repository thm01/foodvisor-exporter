# Foodvisor Exporter

[English](README.en.md) · Français

Foodvisor Exporter récupère le journal de votre propre compte Foodvisor et crée un classeur à ouvrir dans Excel ou LibreOffice Calc. Le projet est **non officiel, indépendant et non affilié à Foodvisor**. Il utilise une API privée susceptible de changer ou de refuser les requêtes. Consultez les [conditions d’utilisation de Foodvisor](https://www.foodvisor.io/fr/terms-of-service/raw/) avant de l’utiliser.

## Installer et lancer

1. Téléchargez le [dépôt en ZIP](https://github.com/thm01/foodvisor-exporter/archive/refs/heads/main.zip), puis extrayez l’archive. Gardez les fichiers et le dossier `app/` ensemble.
2. Installez [Python 3.9 ou plus récent](https://www.python.org/downloads/) si nécessaire. La version source n’exige aucune bibliothèque Python supplémentaire ; un navigateur récent suffit pour l’interface.
3. Ouvrez le lanceur correspondant à votre système **dans le dossier extrait** :

   | Système | Lanceur |
   | --- | --- |
   | Windows | `Foodvisor-exporter-windows.cmd` |
   | macOS | `Foodvisor-exporter-macos.command` |
   | Linux | `Foodvisor-exporter-linux.sh` |

L’application ouvre normalement une page dans votre navigateur. Si elle ne s’ouvre pas, copiez l’adresse `http://127.0.0.1:…` affichée dans le terminal. Sous Linux, si le lanceur ne s’ouvre pas depuis le gestionnaire de fichiers, lancez `bash Foodvisor-exporter-linux.sh` dans un terminal ouvert dans le dossier extrait. Vous pouvez aussi démarrer l’interface avec `python3 app/web_interface.py` (`py -3 app\web_interface.py` sous Windows).

Pour mémoriser le mot de passe dans le coffre système, vous pouvez installer **facultativement** `keyring` avec `python3 -m pip install keyring` (`py -3 -m pip install keyring` sous Windows). Sans cette option, le mot de passe n’est pas enregistré par l’application.

## Faire un export

1. Choisissez la langue de l’interface dans le menu. La langue des données la suit par défaut.
2. Saisissez les identifiants de votre compte Foodvisor et cliquez sur **Se connecter**. Le pays et la langue des données peuvent être ajustés dans **Options avancées**. Le pays proposé provient de l’ordinateur ou des préférences du compte ; Foodvisor peut refuser certains codes.
3. Choisissez les dates de début et de fin dans les calendriers, puis le dossier de destination. Les dates sont inclusives.
4. Cliquez sur **Exporter**. La progression et les erreurs apparaissent dans la page. Une fois l’export terminé, cliquez sur **Ouvrir le dossier**, puis ouvrez `Foodvisor.xlsx`.

**Annuler** interrompt le traitement entre deux requêtes ; une requête déjà en cours peut durer jusqu’à 30 secondes. **Se déconnecter** efface la session en mémoire. Pour arrêter le serveur local, utilisez **Quitter** ; fermer la page l’arrête après environ deux minutes d’inactivité.

## Comprendre les fichiers obtenus

Chaque export crée un dossier horodaté avec cette structure :

```text
<horodatage>/
├── Foodvisor.xlsx       Classeur à ouvrir
├── data/                CSV, JSON fusionné et rapport de fin
└── sources/             Réponses JSON brutes de Foodvisor
```

Le classeur `Foodvisor.xlsx` contient :

| Onglet | Contenu |
| --- | --- |
| **Par jour** | Totaux des repas et nutriments, eau enregistrée, nombre d’activités et kcal dépensées reçues. |
| **Par repas** | Totaux nutritionnels de chaque repas. |
| **Aliments** | Détail des aliments et plats, quantités et nutriments. |
| **Eau** | Volumes d’eau enregistrés, lorsqu’ils sont présents dans le journal. |
| **Activités** | Activités reçues, durée, kcal dépensées, mode d’ajout et origine. |
| **À lire** | Méthode de calcul et explication des valeurs absentes. |

Dans `data/`, `Foodvisor.csv` détaille les aliments, `Foodvisor-days.csv` les journées, et `Foodvisor-activities.csv` les activités. `Foodvisor-activities.json` fournit les activités et totaux quotidiens ; `historique.json` conserve les données fusionnées du journal. `sources/` permet de reconvertir l’export sans nouvelle connexion. Les en-têtes du classeur et des CSV, ainsi que les libellés de présentation du JSON des activités, suivent la langue des données choisie ; les noms fournis par Foodvisor ne sont pas traduits. Une origine d’activité inconnue apparaît comme « Autre », avec la valeur brute conservée à côté.

Tous ces fichiers peuvent contenir des données personnelles sensibles : conservez le dossier dans un emplacement privé.

## Convertir des données déjà téléchargées

Dans l’interface, choisissez le dossier `sources/` d’un export existant, puis cliquez sur **Convertir des données déjà téléchargées**. La conversion fonctionne sans connexion à Foodvisor et crée un nouveau dossier autonome avec une copie des sources. Les anciens dossiers `donnees-brutes/` restent acceptés.

## Ligne de commande

Vous pouvez aussi exporter sans l’interface :

```bash
bash Foodvisor-exporter.sh --start 2026-01-01 --end 2026-01-31
```

Dans le terminal, les dates utilisent le format **AAAA-MM-JJ**. `--start` est requis ; `--end` prend la date du jour par défaut. `--country` vaut `BE` et `--locale` vaut `fr` par défaut ; `--locale en` produit les libellés en anglais. Le programme demande les identifiants dans le terminal et place les fichiers dans `exports/<horodatage>/`.

Pour reconvertir des réponses existantes, utilisez `bash Foodvisor-exporter.sh --source exports/<horodatage>/sources`. Pour enchaîner plusieurs exports avec la même session, ajoutez `--interactive` ; le mot de passe est redemandé seulement si la session n’est plus valide.

## Limites

L’application a été développée et testée avec un compte Foodvisor Premium. Les comptes gratuits n’ont pas été testés : leur compatibilité et la disponibilité de toutes les données ne sont pas garanties.

L’exporteur lit uniquement le journal du compte connecté et les fiches alimentaires qu’il référence. Il ne parcourt pas le catalogue général, ne modifie pas le compte et ne synchronise pas les données du téléphone. Les activités saisies manuellement sont exportées lorsqu’elles figurent dans le journal reçu ; celles issues de Santé Connect ou d’Apple Santé peuvent manquer.

Les kcal dépensées par jour sont la somme des `calories_burned` des activités reçues ; elles peuvent différer du bilan affiché par Foodvisor. Les cellules vides représentent des valeurs absentes, pas nécessairement zéro. L’API peut changer et les résultats peuvent être incomplets. Les requêtes sont séquentielles et espacées d’une seconde, sans garantie d’acceptation par Foodvisor. L’outil ne renouvelle pas les jetons, ne télécharge pas d’images et ne programme pas d’export automatique. Vérifiez les données avant de vous y fier.

Le dépôt ne contient aucun APK, code décompilé, secret extrait de l’application ou donnée de compte. Pour demander officiellement vos données, consultez la [politique de confidentialité de Foodvisor](https://www.foodvisor.io/fr/privacy-policy/raw/).
