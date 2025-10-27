import streamlit as st
import pandas as pd
import duckdb
import os

st.set_page_config(
    page_title="Gérer les correspondances",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Gestion des correspondances")
st.markdown("---")

# Chemin de la base de données DuckDB
DB_PATH = "correspondances.db"

def get_db_connection():
    """Crée ou récupère la connexion à la base de données"""
    return duckdb.connect(DB_PATH)

def init_db_if_needed():
    """Initialise la base de données si elle n'existe pas"""
    conn = get_db_connection()
    try:
        # Vérifier si la table existe
        result = conn.execute("SELECT COUNT(*) FROM correspondances").fetchone()
    except:
        # Créer la table si elle n'existe pas
        conn.execute("""
            CREATE TABLE IF NOT EXISTS correspondances (
                "Dénomination" VARCHAR,
                "Forme de panneau" VARCHAR,
                "Couleur int" VARCHAR,
                "Couleur ext" VARCHAR,
                "Epaisseur (mm)" VARCHAR
            )
        """)
    return conn

def load_correspondance_file(file):
    """Charge un fichier Excel de correspondance et retourne un DataFrame"""
    try:
        if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            df = pd.read_excel(file)
            # Vérifier que les colonnes nécessaires existent
            required_cols = ['Dénomination', 'Forme de panneau', 'Couleur int', 'Couleur ext', 'Epaisseur (mm)']
            if not all(col in df.columns for col in required_cols):
                st.error("❌ Le fichier doit contenir les colonnes suivantes : Dénomination, Forme de panneau, Couleur int, Couleur ext, Epaisseur (mm)")
                return None
            
            # Sélectionner les colonnes pertinentes
            df = df[required_cols].copy()
            # Nettoyer les données
            df = df.dropna(subset=['Dénomination'])
            return df
        else:
            st.error("❌ Format de fichier non supporté. Veuillez utiliser un fichier Excel (.xlsx ou .xls)")
            return None
    except Exception as e:
        st.error(f"❌ Erreur lors de la lecture du fichier : {str(e)}")
        return None

def add_to_database(df):
    """Ajoute les données au fichier de correspondances"""
    conn = get_db_connection()
    try:
        # Supprimer les anciennes données
        conn.execute("DELETE FROM correspondances")
        # Insérer les nouvelles données
        conn.execute("INSERT INTO correspondances SELECT * FROM df")
        st.success("✅ Correspondances mises à jour avec succès !")
        return True
    except Exception as e:
        st.error(f"❌ Erreur lors de l'insertion : {str(e)}")
        return False
    finally:
        conn.close()

def get_all_correspondances():
    """Récupère toutes les correspondances de la base de données"""
    conn = get_db_connection()
    try:
        df = conn.execute("SELECT * FROM correspondances ORDER BY \"Dénomination\"").df()
        return df
    except Exception as e:
        st.error(f"❌ Erreur lors de la récupération : {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

# Initialiser la base de données
init_db_if_needed()

# Sidebar avec les statistiques
with st.sidebar:
    st.header("📊 Statistiques")
    conn = get_db_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM correspondances").fetchone()[0]
        st.success(f"✅ {count} correspondances dans la base")
    except:
        st.info("ℹ️ Base de données vide")
    conn.close()
    
    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    if st.button("🔄 Transformer les fichiers"):
        st.switch_page("app.py")

# Section 1 : Charger un fichier de correspondances
st.subheader("📤 Charger un fichier de correspondances")

uploaded_file = st.file_uploader(
    "Glissez-déposez votre fichier Excel de correspondances",
    type=['xlsx', 'xls'],
    help="Le fichier doit contenir les colonnes : Dénomination, Forme de panneau, Couleur int, Couleur ext, Epaisseur (mm)"
)

if uploaded_file is not None:
    # Lire le fichier
    df = load_correspondance_file(uploaded_file)
    
    if df is not None:
        st.subheader("📄 Aperçu du fichier")
        st.dataframe(df, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Nombre de correspondances", len(df))
        with col2:
            st.metric("Colonnes", len(df.columns))
        
        # Afficher un échantillon des données
        st.subheader("🎯 Échantillon des données")
        st.dataframe(df.head(10), use_container_width=True)
        
        # Bouton pour ajouter à la base de données
        if st.button("💾 Enregistrer dans la base de données", type="primary"):
            if add_to_database(df):
                st.rerun()

# Séparateur
st.markdown("---")

# Section 2 : Afficher les correspondances actuelles
st.subheader("📋 Correspondances actuelles")

if st.button("🔄 Rafraîchir"):
    st.rerun()

# Récupérer et afficher les données
df_current = get_all_correspondances()

if len(df_current) > 0:
    st.dataframe(df_current, use_container_width=True)
    
    # Options de filtrage et recherche
    search_term = st.text_input("🔍 Rechercher une dénomination")
    if search_term:
        df_filtered = df_current[df_current['Dénomination'].str.contains(search_term, case=False, na=False)]
        st.write(f"**{len(df_filtered)} résultat(s) trouvé(s)**")
        st.dataframe(df_filtered, use_container_width=True)
else:
    st.info("ℹ️ Aucune correspondance dans la base de données. Chargez un fichier ci-dessus pour commencer.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888;'>
        Gestion des correspondances - Application EDI Soubassement
    </div>
    """,
    unsafe_allow_html=True
)

