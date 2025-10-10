# Application Streamlit - Transformation CSV/Excel

## Description

Cette application Streamlit permet de manipuler des fichiers CSV et Excel avec une logique de remplissage automatique des colonnes A et F.

### Fonctionnalités

-   **Import de fichiers** : Glissez-déposez vos fichiers CSV ou Excel
-   **Transformation automatique** : Remplissage des colonnes A et F vides
-   **Logique de copie** : Si une ligne a les mêmes valeurs dans les colonnes B et C qu'une autre ligne, les valeurs A et F sont copiées
-   **Export** : Téléchargez le résultat en CSV ou Excel

## Installation et Lancement

### Option 1 : Avec Docker Compose (recommandé)

1. Assurez-vous d'avoir Docker et Docker Compose installés
2. Clonez ou téléchargez ce projet
3. Ouvrez un terminal dans le dossier du projet
4. Lancez l'application :

```bash
docker-compose up --build
```

5. Ouvrez votre navigateur à l'adresse : http://localhost:8501

Pour arrêter l'application :

```bash
docker-compose down
```

### Option 2 : Avec Docker uniquement

1. Construire l'image Docker :

```bash
docker build -t streamlit-csv-app .
```

2. Lancer le conteneur :

```bash
docker run -p 8501:8501 streamlit-csv-app
```

3. Ouvrez votre navigateur à l'adresse : http://localhost:8501

### Option 3 : Sans Docker (développement local)

1. Assurez-vous d'avoir Python 3.11+ installé
2. Installez les dépendances :

```bash
pip install -r requirements.txt
```

3. Lancez l'application :

```bash
streamlit run app.py
```

4. Ouvrez votre navigateur à l'adresse : http://localhost:8501

## Utilisation

1. **Importer un fichier** : Glissez-déposez ou cliquez pour sélectionner un fichier CSV ou Excel
2. **Visualiser** : Consultez le fichier original et les statistiques
3. **Transformer** : Cliquez sur le bouton "Transformer le fichier"
4. **Télécharger** : Téléchargez le résultat en CSV ou Excel

## Logique de Transformation

L'application analyse chaque ligne du fichier :

-   Si les colonnes A et F d'une ligne sont vides
-   Elle cherche une autre ligne avec les mêmes valeurs dans les colonnes B et C
-   Si une telle ligne existe avec A et F remplis, elle copie ces valeurs

### Exemple

**Avant transformation :**

```
| A          | B           | C   | D    | E | F                  |
|------------|-------------|-----|------|---|--------------------|
| 03/10/2025 | 2508568.HP2 | 201 | qte: | 1 | soubassement MOUL  |
|            | 2508568.HP2 | 201 | qte: | 1 |                    |
|            | 2508568.HP2 | 201 | qte: | 1 |                    |
```

**Après transformation :**

```
| A          | B           | C   | D    | E | F                  |
|------------|-------------|-----|------|---|--------------------|
| 03/10/2025 | 2508568.HP2 | 201 | qte: | 1 | soubassement MOUL  |
| 03/10/2025 | 2508568.HP2 | 201 | qte: | 1 | soubassement MOUL  |
| 03/10/2025 | 2508568.HP2 | 201 | qte: | 1 | soubassement MOUL  |
```

## Structure du Projet

```
.
├── app.py                  # Application Streamlit principale
├── Dockerfile              # Configuration Docker
├── docker-compose.yml      # Configuration Docker Compose
├── requirements.txt        # Dépendances Python
└── README.md              # Ce fichier
```

## Technologies Utilisées

-   **Streamlit** : Framework pour l'interface web
-   **Pandas** : Manipulation de données
-   **OpenPyXL** : Lecture/écriture de fichiers Excel
-   **Docker** : Containerisation

## Support

Pour toute question ou problème, veuillez créer une issue sur le dépôt GitHub.
