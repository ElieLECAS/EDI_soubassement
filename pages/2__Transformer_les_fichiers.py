import streamlit as st
import pandas as pd
import io
import duckdb
import os

st.set_page_config(
    page_title="Transformation CSV/Excel",
    page_icon="📊",
    layout="wide"
)

# Chemin de la base de données DuckDB
DB_PATH = "correspondances.db"

def get_db_connection():
    """Crée ou récupère la connexion à la base de données"""
    try:
        conn = duckdb.connect(DB_PATH)
        return conn
    except:
        return None

def init_db_if_needed():
    """Initialise la base de données si elle n'existe pas"""
    conn = get_db_connection()
    if conn:
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

st.title("📊 Transformation de fichiers CSV/Excel")
st.markdown("---")

# Initialiser la base de données au démarrage
db_conn = init_db_if_needed()

# Afficher l'état de la base de données dans la sidebar
with st.sidebar:
    st.header("📊 État de la base de données")
    if db_conn is not None:
        try:
            count = db_conn.execute("SELECT COUNT(*) FROM correspondances").fetchone()[0]
            st.success(f"✅ Base de correspondances active ({count} entrées)")
        except:
            st.info("ℹ️ Base de correspondances initialisée")
    else:
        st.warning("⚠️ Base de correspondances non disponible")
    
    st.markdown("---")
    st.markdown("### 🧭 Navigation")
    if st.button("📋 Gérer les correspondances"):
        st.switch_page("correspondances.py")

def fill_empty_columns(df, db_conn=None):
    """
    Remplit les colonnes A et F vides en se basant sur les paires de valeurs B-C.
    Si une ligne a les colonnes A et F vides, cherche une autre ligne avec les mêmes
    valeurs B et C et copie les valeurs A et F de cette ligne.
    Scinde également la colonne B au niveau du point.
    Enrichit également le fichier avec les informations de correspondance basées sur la dénomination (colonne F).
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 6 colonnes
    if len(df.columns) < 6:
        st.error("Le fichier doit avoir au moins 6 colonnes (A, B, C, D, E, F)")
        return df_result
    
    # Obtenir les noms des colonnes (index 0=A, 1=B, 2=C, 5=F)
    col_names = df.columns.tolist()
    col_a = col_names[0]  # Colonne A
    col_b = col_names[1]  # Colonne B  
    col_c = col_names[2]  # Colonne C
    col_f = col_names[5]  # Colonne F
    
    # Scinder la colonne B au niveau du point
    st.info("🔧 Scission de la colonne B au niveau du point...")
    
    # Créer deux nouvelles colonnes pour les parties avant et après le point
    df_result['N_cde'] = df_result[col_b].astype(str).str.split('.').str[0]
    df_result['Extension'] = df_result[col_b].astype(str).str.split('.').str[1]
    
    # Remplacer les valeurs 'nan' par des chaînes vides
    df_result['N_cde'] = df_result['N_cde'].replace('nan', '')
    df_result['Extension'] = df_result['Extension'].replace('nan', '')
    
    # Créer la colonne 'Secteur ligne vitrage pe' basée sur l'extension
    df_result['Secteur ligne vitrage pe'] = df_result['Extension'].apply(
        lambda x: 'PE' if 'P' in str(x).upper() else ''
    )
    
    # Créer la colonne 'Secteur ligne vitrage alu' basée sur l'extension
    df_result['Secteur ligne vitrage alu'] = df_result['Extension'].apply(
        lambda x: 'ALU' if str(x).upper().startswith(('U', 'Y')) else ''
    )
    
    # Créer la colonne 'Secteur ligne vitrage textural' basée sur l'extension
    df_result['Secteur ligne vitrage textural'] = df_result['Extension'].apply(
        lambda x: 'TEX' if any(char in str(x).upper() for char in ['H', 'Z', 'X']) else ''
    )
    
    # Réorganiser les colonnes : mettre N_cde, Extension et les secteurs après la colonne B
    cols = df_result.columns.tolist()
    # Trouver l'index de la colonne B
    col_b_index = cols.index(col_b)
    # Créer la nouvelle liste de colonnes
    new_cols = cols[:col_b_index+1] + ['N_cde', 'Extension', 'Secteur ligne vitrage pe', 'Secteur ligne vitrage alu', 'Secteur ligne vitrage textural'] + [col for col in cols[col_b_index+1:] if col not in ['N_cde', 'Extension', 'Secteur ligne vitrage pe', 'Secteur ligne vitrage alu', 'Secteur ligne vitrage textural']]
    df_result = df_result[new_cols]
    
    st.success(f"✅ Colonne B scindée en 'N_cde' et 'Extension', avec ajout des secteurs PE, ALU et TEX")
    
    # Parcourir chaque ligne
    for idx in df_result.index:
        # Vérifier si les colonnes A et F sont vides (None ou chaîne vide)
        val_a = df_result.loc[idx, col_a]
        val_f = df_result.loc[idx, col_f]
        
        is_a_empty = pd.isna(val_a) or (isinstance(val_a, str) and val_a.strip() == '')
        is_f_empty = pd.isna(val_f) or (isinstance(val_f, str) and val_f.strip() == '')
        
        if is_a_empty and is_f_empty:
            # Obtenir la valeur de B pour cette ligne
            val_b = df_result.loc[idx, col_b]
            
            # Chercher la ligne AU-DESSUS avec la même valeur B et A/F non vides
            for other_idx in range(idx-1, -1, -1):  # Parcourir de haut en bas jusqu'à la ligne courante
                other_b = df_result.loc[other_idx, col_b]
                other_a = df_result.loc[other_idx, col_a]
                other_f = df_result.loc[other_idx, col_f]
                
                # Vérifier si les valeurs B correspondent (gérer les None)
                b_match = (pd.isna(val_b) and pd.isna(other_b)) or (val_b == other_b)
                
                if b_match:
                    # Vérifier si A et F ne sont pas vides dans l'autre ligne
                    is_other_a_empty = pd.isna(other_a) or (isinstance(other_a, str) and other_a.strip() == '')
                    is_other_f_empty = pd.isna(other_f) or (isinstance(other_f, str) and other_f.strip() == '')
                    
                    if not is_other_a_empty and not is_other_f_empty:
                        # Copier les valeurs
                        df_result.loc[idx, col_a] = other_a
                        df_result.loc[idx, col_f] = other_f
                        st.info(f"✅ Ligne {idx}: Rempli avec les valeurs de la ligne {other_idx} au-dessus (même valeur B: {val_b})")
                        break
    
    # Enrichir avec les correspondances de la base de données
    if db_conn is not None:
        st.info("🔍 Enrichissement des données avec les correspondances...")
        
        # Ajouter les 4 colonnes vides
        df_result['Forme de panneau'] = ''
        df_result['Couleur int'] = ''
        df_result['Couleur ext'] = ''
        df_result['Epaisseur (mm)'] = ''
        
        # Trouver la colonne F (dénomination) dans le dataframe transformé
        # Après les transformations, la colonne F originale est maintenant à l'index original
        col_names = df_result.columns.tolist()
        
        # La colonne F est toujours à l'index 5 de la liste originale
        # Mais après réorganisation, elle peut être à une autre position
        # Cherchons la colonne F originale
        f_col_name = col_names[5] if len(col_names) > 5 else None
        
        if f_col_name:
            # Parcourir chaque ligne pour chercher dans la DB
            for idx in df_result.index:
                denomination = df_result.loc[idx, f_col_name]
                
                # Si la dénomination n'est pas vide, chercher dans la DB
                if pd.notna(denomination) and str(denomination).strip() != '':
                    try:
                        # Rechercher dans DuckDB
                        clean_denomination = str(denomination).strip().replace("'", "''")  # Échapper les apostrophes
                        query = f"SELECT \"Forme de panneau\", \"Couleur int\", \"Couleur ext\", \"Epaisseur (mm)\" FROM correspondances WHERE Dénomination = '{clean_denomination}'"
                        result = db_conn.execute(query).fetchone()
                        
                        if result:
                            df_result.loc[idx, 'Forme de panneau'] = result[0]
                            df_result.loc[idx, 'Couleur int'] = result[1]
                            df_result.loc[idx, 'Couleur ext'] = result[2]
                            df_result.loc[idx, 'Epaisseur (mm)'] = result[3]
                    except Exception as e:
                        # Si erreur, passer à la ligne suivante
                        pass
        
        # Réorganiser les colonnes pour mettre les correspondances après la colonne F
        cols = df_result.columns.tolist()
        # Trouver l'index de la colonne F
        if f_col_name and f_col_name in cols:
            f_index = cols.index(f_col_name)
            # Nouveau ordre : colonnes avant F, F, puis les 4 nouvelles colonnes, puis les restantes
            new_cols = [c for c in cols[:f_index+1] if c not in ['Forme de panneau', 'Couleur int', 'Couleur ext', 'Epaisseur (mm)']]
            new_cols += ['Forme de panneau', 'Couleur int', 'Couleur ext', 'Epaisseur (mm)']
            new_cols += [c for c in cols if c not in new_cols and c not in ['Forme de panneau', 'Couleur int', 'Couleur ext', 'Epaisseur (mm)']]
            df_result = df_result[new_cols]
        
        st.success("✅ Données enrichies avec les correspondances")
    
    return df_result

# Interface de téléchargement
st.subheader("📁 Importer votre fichier")
uploaded_file = st.file_uploader(
    "Glissez-déposez votre fichier CSV ou Excel ici",
    type=['csv', 'xlsx', 'xls'],
    help="Formats acceptés : CSV, Excel (.xlsx, .xls)"
)

if uploaded_file is not None:
    try:
        # Lire le fichier
        if uploaded_file.name.endswith('.csv'):
            # Essayer différents encodages pour les CSV
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
            df = None
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=';', header=None, encoding=encoding)
                    st.info(f"✅ Fichier lu avec l'encodage : {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    # Essayer avec une autre séparation si le point-virgule ne fonctionne pas
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, header=None, encoding=encoding)
                        st.info(f"✅ Fichier lu avec l'encodage : {encoding}")
                        break
                    except:
                        continue
            
            if df is None:
                st.error("Impossible de lire le fichier avec les encodages supportés.")
                st.stop()
        else:
            df = pd.read_excel(uploaded_file, header=None)
        
        # Afficher le fichier original
        st.subheader("📄 Fichier original")
        st.dataframe(df, use_container_width=True)
        
        # Afficher les statistiques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Nombre de lignes", len(df))
        with col2:
            st.metric("Nombre de colonnes", len(df.columns))
        with col3:
            # Compter les lignes avec colonnes A et F vides
            col_names = df.columns.tolist()
            if len(col_names) >= 6:
                col_a = col_names[0]
                col_f = col_names[5]
                empty_count = sum((pd.isna(df[col_a]) | (df[col_a] == '')) & 
                                (pd.isna(df[col_f]) | (df[col_f] == '')))
                st.metric("Lignes avec A et F vides", empty_count)
        
        st.markdown("---")
        
        # Bouton de transformation
        if st.button("🔄 Transformer le fichier", type="primary", use_container_width=True):
            with st.spinner("Transformation en cours..."):
                # Debug: afficher quelques informations
                st.info(f"🔍 Debug: Le fichier a {len(df.columns)} colonnes")
                st.info(f"🔍 Debug: Colonnes A={df.columns[0]}, B={df.columns[1]}, C={df.columns[2]}, F={df.columns[5]}")
                
                df_transformed = fill_empty_columns(df, db_conn)
                
                # Afficher le résultat
                st.subheader("✅ Fichier transformé")
                st.dataframe(df_transformed, use_container_width=True)
                
                # Compter les modifications
                col_names = df.columns.tolist()
                if len(col_names) >= 6:
                    col_a = col_names[0]
                    col_f = col_names[5]
                    empty_after = sum((pd.isna(df_transformed[col_a]) | (df_transformed[col_a] == '')) & 
                                    (pd.isna(df_transformed[col_f]) | (df_transformed[col_f] == '')))
                    st.success(f"🎉 Transformation terminée ! {empty_count - empty_after} lignes ont été remplies.")
                
                # Boutons de téléchargement
                st.subheader("💾 Télécharger le résultat")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Téléchargement CSV
                    csv_buffer = io.StringIO()
                    df_transformed.to_csv(csv_buffer, index=False, header=False, sep=';')
                    csv_data = csv_buffer.getvalue()
                    
                    st.download_button(
                        label="📥 Télécharger en CSV",
                        data=csv_data,
                        file_name=f"transforme_{uploaded_file.name.replace('.xlsx', '.csv').replace('.xls', '.csv')}",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    # Téléchargement Excel
                    excel_buffer = io.BytesIO()
                    df_transformed.to_excel(excel_buffer, index=False, header=False, engine='openpyxl')
                    excel_data = excel_buffer.getvalue()
                    
                    st.download_button(
                        label="📥 Télécharger en Excel",
                        data=excel_data,
                        file_name=f"transforme_{uploaded_file.name.replace('.csv', '.xlsx')}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
    except Exception as e:
        st.error(f"❌ Erreur lors du traitement du fichier : {str(e)}")
        st.exception(e)

else:
    # Instructions
    st.info("""
    👆 **Instructions :**
    1. Glissez-déposez votre fichier CSV ou Excel ci-dessus
    2. Visualisez le fichier original
    3. Cliquez sur "Transformer le fichier"
    4. Téléchargez le résultat transformé
    
    **Logique de transformation :**
    - Les colonnes A et F vides sont automatiquement remplies
    - Pour chaque ligne vide, on prend les valeurs A et F de la ligne AU-DESSUS
      qui a la même valeur B et qui n'est pas vide
    - La colonne B est scindée au niveau du point en :
      • N_cde (avant le point)
      • Extension (après le point)
      • Secteur ligne vitrage pe (PE si Extension contient 'P')
      • Secteur ligne vitrage alu (ALU si Extension commence par 'U' ou 'Y')
      • Secteur ligne vitrage textural (TEX si Extension contient 'H', 'Z' ou 'X')
    """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888;'>
        Développé avec ❤️ en Streamlit
    </div>
    """,
    unsafe_allow_html=True
)

