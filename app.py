import streamlit as st
import pandas as pd
import io
import duckdb
import os
from pathlib import Path

st.set_page_config(
    page_title="Transformation CSV/Excel",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Transformation de fichiers CSV/Excel")

# Configuration de la base de données
DB_PATH = "/app/data/correspondances.duckdb"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

@st.cache_resource
def init_database():
    """Initialise la base de données DuckDB et crée la table si elle n'existe pas"""
    conn = duckdb.connect(DB_PATH)
    
    # Créer une séquence pour l'auto-increment (si elle n'existe pas)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS correspondances_id_seq START 1
    """)
    
    # Créer la table si elle n'existe pas
    conn.execute("""
        CREATE TABLE IF NOT EXISTS correspondances (
            id BIGINT PRIMARY KEY DEFAULT nextval('correspondances_id_seq'),
            denomination VARCHAR,
            forme_panneau VARCHAR,
            couleur_int VARCHAR,
            couleur_ext VARCHAR,
            epaisseur_mm REAL
        )
    """)
    
    return conn

def get_all_correspondances():
    """Récupère toutes les correspondances de la base de données"""
    conn = init_database()
    df = conn.execute("""
        SELECT id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm 
        FROM correspondances 
        ORDER BY id
    """).df()
    return df

def add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
    """Ajoute une nouvelle correspondance à la base de données si elle n'existe pas déjà"""
    conn = init_database()
    
    # Vérifier si une ligne avec exactement les mêmes valeurs existe déjà
    result = conn.execute("""
        SELECT COUNT(*) 
        FROM correspondances 
        WHERE denomination = ? 
          AND forme_panneau = ? 
          AND couleur_int = ? 
          AND couleur_ext = ? 
          AND epaisseur_mm = ?
    """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm]).fetchone()
    
    # Si aucune correspondance exacte n'existe, on insère
    if result[0] == 0:
        conn.execute("""
            INSERT INTO correspondances (denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
            VALUES (?, ?, ?, ?, ?)
        """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm])
        st.cache_resource.clear()
        return True  # Indique qu'une nouvelle correspondance a été ajoutée
    else:
        return False  # Indique qu'une doublon existe déjà

def update_correspondance(id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
    """Met à jour une correspondance existante"""
    conn = init_database()
    conn.execute("""
        UPDATE correspondances 
        SET denomination = ?, forme_panneau = ?, couleur_int = ?, couleur_ext = ?, epaisseur_mm = ?
        WHERE id = ?
    """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm, id])
    st.cache_resource.clear()

def delete_correspondance(id):
    """Supprime une correspondance de la base de données"""
    conn = init_database()
    conn.execute("DELETE FROM correspondances WHERE id = ?", [id])
    st.cache_resource.clear()

def fill_empty_columns(df):
    """
    Remplit les colonnes A (Date) et F (Denomination) vides en se basant sur les paires de valeurs B (Reference) et C (Code).
    Si une ligne a les colonnes A et F vides, cherche une autre ligne avec les mêmes
    valeurs B et C et copie les valeurs A et F de cette ligne.
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 6 colonnes (minimum nécessaire)
    if len(df.columns) < 6:
        st.warning("Le fichier doit avoir au moins 6 colonnes")
        return df_result
    
    # Obtenir les noms des colonnes 
    col_names = df.columns.tolist()
    
    # Utiliser les noms de colonnes si disponibles, sinon utiliser les index
    if 'Date' in col_names:
        col_a = 'Date'  # Colonne Date
    else:
        col_a = col_names[0]  # Colonne A (fallback)
    
    # Déterminer les colonnes B (Reference), C (Code) et F (Denomination)
    # Structure attendue après split et secteurs:
    # index 0=Date, 1=Reference, 2=Extension, 3-5=Secteurs, 6=Code, 7-9=..., 10=Denomination
    if 'Reference' in col_names:
        col_b = 'Reference'  # Colonne Reference
    else:
        col_b = col_names[1] if len(col_names) > 1 else col_a  # Colonne B (fallback)
    
    # Colonne C (Code) est après les secteurs (index 6)
    if 'Code' in col_names:
        col_c = 'Code'
    else:
        col_c = col_names[6] if len(col_names) > 6 else (col_names[3] if len(col_names) > 3 else col_names[2])
    
    # Colonne F (Denomination) est à l'index 10 si disponible, sinon à l'index 5
    if 'Denomination' in col_names:
        col_f = 'Denomination'
    else:
        col_f = col_names[9] if len(col_names) > 9 else (col_names[6] if len(col_names) > 6 else col_names[5])
    
    # Parcourir chaque ligne
    for idx in df_result.index:
        # Vérifier si les colonnes A et F sont vides (None ou chaîne vide)
        val_a = df_result.loc[idx, col_a]
        val_f = df_result.loc[idx, col_f]
        
        is_a_empty = pd.isna(val_a) or (isinstance(val_a, str) and val_a.strip() == '')
        is_f_empty = pd.isna(val_f) or (isinstance(val_f, str) and val_f.strip() == '')
        
        if is_a_empty and is_f_empty:
            # Obtenir les valeurs de B et C pour cette ligne
            val_b = df_result.loc[idx, col_b]
            val_c = df_result.loc[idx, col_c]
            
            # Chercher une ligne avec les mêmes valeurs B et C mais avec A et F remplis
            for other_idx in df_result.index:
                if other_idx != idx:
                    other_b = df_result.loc[other_idx, col_b]
                    other_c = df_result.loc[other_idx, col_c]
                    other_a = df_result.loc[other_idx, col_a]
                    other_f = df_result.loc[other_idx, col_f]
                    
                    # Vérifier si les valeurs B et C correspondent (gérer les None)
                    b_match = (pd.isna(val_b) and pd.isna(other_b)) or (val_b == other_b)
                    c_match = (pd.isna(val_c) and pd.isna(other_c)) or (val_c == other_c)
                    
                    if b_match and c_match:
                        # Vérifier si A et F ne sont pas vides dans l'autre ligne
                        is_other_a_empty = pd.isna(other_a) or (isinstance(other_a, str) and other_a.strip() == '')
                        is_other_f_empty = pd.isna(other_f) or (isinstance(other_f, str) and other_f.strip() == '')
                        
                        if not is_other_a_empty and not is_other_f_empty:
                            # Copier les valeurs
                            df_result.loc[idx, col_a] = other_a
                            df_result.loc[idx, col_f] = other_f
                            st.info(f"✅ Ligne {idx}: Rempli avec les valeurs de la ligne {other_idx}")
                            break
    
    return df_result

def split_column_1(df):
    """
    Éclate la colonne Reference en deux colonnes en séparant à gauche et à droite du point.
    Exemple: "123.456" devient colonne 1: "123", colonne 2: "456"
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 2 colonnes (colonne 0 et colonne 1)
    if len(df.columns) < 2:
        return df_result
    
    col_names = df.columns.tolist()
    
    # Utiliser le nom de colonne si disponible, sinon utiliser l'index
    if 'Reference' in col_names:
        col_1 = 'Reference'
    else:
        col_1 = col_names[1]  # Colonne 1 (colonne B, index 1)
    
    # Extraire les valeurs de la colonne 1
    values = df_result[col_1].astype(str)
    
    # Séparer à gauche et à droite du point
    left_values = []
    right_values = []
    
    for val in values:
        if pd.isna(val) or val == 'nan' or val.strip() == '':
            left_values.append('')
            right_values.append('')
        elif '.' in str(val):
            parts = str(val).split('.', 1)
            left_values.append(parts[0] if parts[0] else '')
            right_values.append(parts[1] if len(parts) > 1 else '')
        else:
            left_values.append(str(val))
            right_values.append('')
    
    # Mettre à jour la colonne 1 avec les valeurs de gauche
    df_result[col_1] = left_values
    
    # Créer la nouvelle colonne avec les valeurs de droite juste après la colonne 1
    df_result.insert(2, 'col_1_partie_droite', right_values)
    
    return df_result

def add_concatenated_column(df):
    """
    Ajoute une colonne concaténée en première position.
    Format: colonne_1 . extension / Pos (Code) / Secteur prioritaire
    Ordre de priorité des secteurs: PE > TEX > ALU
    """
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 7 colonnes (pour avoir la colonne 2 = C)
    if len(df.columns) < 7:
        st.warning("⚠️ Le fichier doit avoir au moins 7 colonnes pour la concaténation")
        return df_result
    
    col_names = df.columns.tolist()
    
    # Utiliser les noms de colonnes si disponibles, sinon utiliser les index
    # Colonne 1 = Reference partie gauche (index 1 après split)
    if 'Reference' in col_names:
        col_1 = 'Reference'
    else:
        col_1 = col_names[1] if len(col_names) > 1 else col_names[0]
    
    # col_1_partie_droite = Extension (index 2 après split)
    col_extension = col_names[2] if len(col_names) > 2 else col_names[1]
    
    # Colonne 2 (Code) pour la partie Pos (index 6 après secteurs)
    if 'Code' in col_names:
        col_2 = 'Code'
    else:
        col_2 = col_names[6] if len(col_names) > 6 else col_names[3]
    
    # Colonnes de secteurs (index 3, 4, 5 : PE, ALU, TEX)
    col_pe = col_names[3] if len(col_names) > 3 else None
    col_alu = col_names[4] if len(col_names) > 4 else None
    col_tex = col_names[5] if len(col_names) > 5 else None
    
    # Valeurs concaténées
    concat_values = []
    
    for idx in df_result.index:
        val_1 = df_result.loc[idx, col_1]
        val_ext = df_result.loc[idx, col_extension]
        val_pos = df_result.loc[idx, col_2]
        
        # Récupérer les valeurs des secteurs
        val_pe = df_result.loc[idx, col_pe] if col_pe else ''
        val_alu = df_result.loc[idx, col_alu] if col_alu else ''
        val_tex = df_result.loc[idx, col_tex] if col_tex else ''
        
        # Convertir en string et gérer les NaN
        val_1_str = str(val_1) if pd.notna(val_1) else ''
        val_ext_str = str(val_ext) if pd.notna(val_ext) else ''
        val_pos_str = str(val_pos) if pd.notna(val_pos) else ''
        val_pe_str = str(val_pe).strip() if pd.notna(val_pe) and val_pe != '' else ''
        val_alu_str = str(val_alu).strip() if pd.notna(val_alu) and val_alu != '' else ''
        val_tex_str = str(val_tex).strip() if pd.notna(val_tex) and val_tex != '' else ''
        
        # Déterminer le secteur prioritaire (ALU > PE > TEX)
        secteur_prioritaire = ''
        if val_alu_str:
            secteur_prioritaire = val_alu_str
        elif val_pe_str:
            secteur_prioritaire = val_pe_str
        elif val_tex_str:
            secteur_prioritaire = val_tex_str
        
        # Concaténation selon le schéma: colonne_1 . extension / Pos / Secteur
        parts = []
        if val_1_str and val_ext_str:
            parts.append(f"{val_1_str}.{val_ext_str}")
        elif val_1_str:
            parts.append(val_1_str)
        
        if val_pos_str:
            parts.append(val_pos_str)
        
        if secteur_prioritaire:
            parts.append(secteur_prioritaire)
        
        concat_val = '/'.join(parts) if parts else ''
        concat_values.append(concat_val)
    
    # Créer un nouveau dataframe avec la colonne concaténée en première position
    # Si la colonne 'Reference' existe déjà, on la remplace par la version concaténée
    if 'Reference' in df_result.columns:
        # Supprimer l'ancienne colonne 'Reference'
        df_result = df_result.drop(columns=['Reference'])
    
    # Insérer la colonne concaténée à la première position
    df_result.insert(0, 'Reference', concat_values)
    
    return df_result

def merge_with_correspondances(df):
    """
    Effectue un merge (left join) avec la table de correspondances basé sur la dénomination.
    La colonne de dénomination dans le fichier transformé est la colonne 'Denomination'.
    """
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 10 colonnes
    if len(df.columns) < 10:
        st.warning("⚠️ Le fichier doit avoir au moins 10 colonnes pour le merge")
        return df_result
    
    # Récupérer toutes les correspondances depuis la base de données
    df_correspondances = get_all_correspondances()
    
    if len(df_correspondances) == 0:
        st.warning("⚠️ Aucune correspondance trouvée dans la base de données. Le merge ne peut pas être effectué.")
        return df_result
    
    # La colonne de dénomination est 'Denomination' si disponible, sinon index 9
    col_names = df.columns.tolist()
    if 'Denomination' in col_names:
        denomination_col = 'Denomination'
    else:
        denomination_col = col_names[9]  # Fallback sur l'index
    
    # Faire le merge avec les correspondances
    df_result = df_result.reset_index(drop=True)
    df_result['denomination_key'] = df_result[denomination_col].astype(str)
    
    # Normaliser les dénominations pour le merge (retirer les espaces en plus)
    df_result['denomination_key'] = df_result['denomination_key'].str.strip()
    
    df_correspondances['denomination_key'] = df_correspondances['denomination'].astype(str).str.strip()
    
    # Effectuer le merge (left join)
    df_merged = pd.merge(
        df_result, 
        df_correspondances[['denomination_key', 'forme_panneau', 'couleur_int', 'couleur_ext', 'epaisseur_mm']],
        on='denomination_key',
        how='left'
    )
    
    # Compter le nombre de correspondances trouvées
    matched_count = df_merged['forme_panneau'].notna().sum()
    st.info(f"📊 {matched_count} correspondances trouvées sur {len(df_merged)} lignes")
    
    # Supprimer la colonne temporaire 'denomination_key'
    df_merged = df_merged.drop(columns=['denomination_key'])
    
    return df_merged

def clean_height_column(df):
    """
    Nettoie la colonne 'Hauteur' en supprimant les astérisques (*) et les espaces avant et après.
    """
    df_result = df.copy()
    
    # Vérifier si la colonne 'Hauteur' existe
    col_names = df_result.columns.tolist()
    if 'Hauteur' in col_names:
        # Appliquer le nettoyage : supprimer les astérisques et les espaces
        df_result['Hauteur'] = df_result['Hauteur'].astype(str).str.replace('*', '', regex=False).str.strip()
        st.info("✅ Colonne 'Hauteur' nettoyée (astérisques et espaces supprimés)")
    elif len(col_names) >= 8:
        # Fallback sur l'index si la colonne nommée n'existe pas
        height_col = col_names[7]  # Index 7 après renommage
        df_result[height_col] = df_result[height_col].astype(str).str.replace('*', '', regex=False).str.strip()
        st.info("✅ Colonne 'Hauteur' nettoyée (astérisques et espaces supprimés)")
    
    return df_result

def add_sector_columns(df):
    """
    Ajoute des colonnes de secteurs basées sur la colonne Extension (index 2 après split).
    - Secteur ligne vitrage pe: "PE" si Extension contient "P"
    - Secteur ligne vitrage alu: "ALU" si Extension commence par "U" ou "Y"
    - Secteur ligne vitrage textural: "TEX" si Extension contient "H", "Z" ou "X"
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 3 colonnes (0, 1, 2)
    if len(df.columns) < 3:
        return df_result
    
    col_names = df.columns.tolist()
    extension_col = col_names[2]  # Colonne Extension (index 2 après split)
    
    # Extraire les valeurs de la colonne Extension
    extensions = df_result[extension_col].astype(str)
    
    # Initialiser les colonnes de secteurs
    secteur_pe = []
    secteur_alu = []
    secteur_tex = []
    
    for ext in extensions:
        if pd.isna(ext) or ext == 'nan' or ext.strip() == '':
            secteur_pe.append('')
            secteur_alu.append('')
            secteur_tex.append('')
        else:
            # Secteur PE : contient "P"
            if 'P' in str(ext).upper():
                secteur_pe.append('PE')
            else:
                secteur_pe.append('')
            
            # Secteur ALU : commence par "U" ou "Y"
            if str(ext).upper().startswith('U') or str(ext).upper().startswith('Y'):
                secteur_alu.append('ALU')
            else:
                secteur_alu.append('')
            
            # Secteur TEX : contient "H", "Z" ou "X"
            if 'H' in str(ext).upper() or 'Z' in str(ext).upper() or 'X' in str(ext).upper():
                secteur_tex.append('TEX')
            else:
                secteur_tex.append('')
    
    # Ajouter les trois nouvelles colonnes (on insère dans l'ordre inverse pour éviter les décalages d'index)
    df_result.insert(3, 'Secteur ligne vitrage textural', secteur_tex)
    df_result.insert(3, 'Secteur ligne vitrage alu', secteur_alu)
    df_result.insert(3, 'Secteur ligne vitrage pe', secteur_pe)
    
    return df_result

# Créer des onglets
tab1, tab2 = st.tabs(["🔄 Transformation de fichiers", "🗂️ Gestion des correspondances"])

# ===== ONGLET 1 : TRANSFORMATION DE FICHIERS =====
with tab1:
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
            
            # Nommer les colonnes selon la structure du fichier EDI
            if len(df.columns) >= 11:
                df.columns = [
                    'Date',           # Colonne 0
                    'Reference',      # Colonne 1
                    'Position',           # Colonne 2
                    'Libelle_Quantite', # Colonne 3
                    'Quantite',       # Colonne 4
                    'Denomination',   # Colonne 5
                    'Largeur',        # Colonne 6 (renommé de Longueur)
                    'Hauteur',        # Colonne 7 (renommé de Surface_Poids)
                    'Code_G1',        # Colonne 8
                    'Code_G2',        # Colonne 9
                    'Reference_Dupliquee'  # Colonne 10
                ]
                # Ajouter des colonnes vides si nécessaire pour les colonnes 11+
                if len(df.columns) > 11:
                    for i in range(11, len(df.columns)):
                        df.columns.values[i] = f'Colonne_{i}'
                st.success("✅ Colonnes renommées avec succès")
            
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
                    col_f = col_names[5] if len(col_names) > 5 else col_names[4]
                    empty_count = sum((pd.isna(df[col_a]) | (df[col_a] == '')) & 
                                    (pd.isna(df[col_f]) | (df[col_f] == '')))
                    st.metric("Lignes avec A et F vides", empty_count)
            
            st.markdown("---")
            
            # Bouton de transformation
            if st.button("🔄 Transformer le fichier", type="primary", use_container_width=True):
                with st.spinner("Transformation en cours..."):
                    # Debug: afficher quelques informations
                    st.info(f"🔍 Debug: Le fichier a {len(df.columns)} colonnes")
                    if len(df.columns) >= 6:
                        st.info(f"🔍 Debug: Colonnes A={df.columns[0]}, B={df.columns[1]}, C={df.columns[2]}, F={df.columns[5]}")
                    
                    # Nettoyer la colonne Hauteur (astérisques et espaces)
                    df = clean_height_column(df)
                    
                    # Éclater la colonne 1 en deux colonnes
                    df_transformed = split_column_1(df)
                    
                    # Ajouter les colonnes de secteurs
                    df_transformed = add_sector_columns(df_transformed)
                    
                    # Ensuite remplir les colonnes vides
                    df_transformed = fill_empty_columns(df_transformed)
                    
                    # Effectuer le merge avec la table de correspondances
                    df_transformed = merge_with_correspondances(df_transformed)
                    
                    # Ajouter la colonne concaténée en première position
                    df_transformed = add_concatenated_column(df_transformed)
                    
                    # Afficher le résultat
                    st.subheader("✅ Fichier transformé")
                    st.dataframe(df_transformed, use_container_width=True)
                    
                    # Compter les modifications (après ajout de la colonne concaténée, tous les index sont décalés de 1)
                    col_names = df_transformed.columns.tolist()
                    if len(col_names) >= 11:
                        # La colonne A est maintenant à l'index 1 (décalé de 1)
                        col_a = col_names[1]
                        # La colonne F est maintenant à l'index 10 (anciennement 9)
                        col_f = col_names[10] if len(col_names) > 10 else col_names[7]
                        empty_after = sum((pd.isna(df_transformed[col_a]) | (df_transformed[col_a] == '')) & 
                                        (pd.isna(df_transformed[col_f]) | (df_transformed[col_f] == '')))
                        try:
                            # Calculer empty_count depuis le dataframe original
                            original_col_names = df.columns.tolist()
                            if len(original_col_names) >= 6:
                                original_col_a = original_col_names[0]
                                original_col_f = original_col_names[5] if len(original_col_names) > 5 else original_col_names[4]
                                original_empty_count = sum((pd.isna(df[original_col_a]) | (df[original_col_a] == '')) & 
                                                        (pd.isna(df[original_col_f]) | (df[original_col_f] == '')))
                                if original_empty_count > empty_after:
                                    st.success(f"🎉 Transformation terminée ! {original_empty_count - empty_after} lignes ont été remplies.")
                                else:
                                    st.success(f"🎉 Transformation terminée ! {len(df_transformed)} lignes traitées.")
                        except Exception as e:
                            st.success(f"🎉 Transformation terminée !")
                    
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
        - La colonne 1 est éclatée en deux colonnes (séparation au point)
          Exemple: "123.456" devient colonne 1: "123" et nouvelle colonne: "456"
        - Ajout de 3 colonnes de secteurs basées sur l'Extension :
          * Secteur PE : "PE" si Extension contient "P"
          * Secteur ALU : "ALU" si Extension commence par "U" ou "Y"
          * Secteur TEX : "TEX" si Extension contient "H", "Z" ou "X"
        - Les colonnes A et F vides sont automatiquement remplies
        - Si une ligne a les mêmes valeurs dans les colonnes B et C qu'une autre ligne,
          les valeurs A et F de cette autre ligne sont copiées dans la ligne vide
        - Merge avec la table de correspondances :
          * Les informations (forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
          * sont ajoutées en comparant la dénomination avec celles de la base de données
        - Ajout d'une colonne de référence en première position
          * Format: colonne_1 . extension / Pos (colonne 2) / Secteur prioritaire
          * Ordre de priorité des secteurs: PE > TEX > ALU
          * Exemple: "2508568.HP2/201/PE" (où 201 est la valeur de la colonne C et PE le secteur)
        """)

# ===== ONGLET 2 : GESTION DES CORRESPONDANCES =====
with tab2:
    st.subheader("🗂️ Gestion des correspondances")
    
    # Initialiser la base de données
    init_database()
    
    # Section d'import Excel/CSV
    st.markdown("### 📤 Importer des correspondances")
    with st.expander("➕ Importer depuis un fichier Excel ou CSV", expanded=False):
        uploaded_file = st.file_uploader(
            "Glissez-déposez votre fichier Excel ou CSV de correspondances",
            type=['xlsx', 'xls', 'csv'],
            help="Format attendu : Dénomination | Forme de panneau | Couleur int | Couleur ext | Epaisseur mm"
        )
        
        if uploaded_file is not None:
            try:
                # Lire le fichier selon son type
                if uploaded_file.name.endswith('.csv'):
                    # Essayer différents encodages et séparateurs pour CSV
                    encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
                    df_import = None
                    for encoding in encodings:
                        try:
                            uploaded_file.seek(0)
                            df_import = pd.read_csv(uploaded_file, encoding=encoding, sep=';')
                            st.info(f"✅ Fichier CSV lu avec l'encodage : {encoding}")
                            break
                        except:
                            try:
                                uploaded_file.seek(0)
                                df_import = pd.read_csv(uploaded_file, encoding=encoding, sep=',')
                                st.info(f"✅ Fichier CSV lu avec l'encodage : {encoding}")
                                break
                            except:
                                continue
                    
                    if df_import is None:
                        st.error("❌ Impossible de lire le fichier CSV")
                        st.stop()
                else:
                    # Lire le fichier Excel
                    df_import = pd.read_excel(uploaded_file)
                
                # Vérifier le nombre de colonnes
                if len(df_import.columns) < 5:
                    st.error("❌ Le fichier doit contenir au moins 5 colonnes")
                else:
                    st.success(f"✅ Fichier chargé : {len(df_import)} lignes détectées")
                    
                    # Afficher un aperçu
                    st.markdown("**Aperçu des données :**")
                    st.dataframe(df_import.head(10), use_container_width=True)
                    
                    if st.button("📥 Importer les données", type="primary", use_container_width=True):
                        progress_bar = st.progress(0)
                        imported_count = 0
                        duplicate_count = 0
                        error_count = 0
                        
                        # Insérer chaque ligne
                        for idx, row in df_import.iterrows():
                            try:
                                # Extraire les 5 colonnes
                                denomination = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
                                forme_panneau = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
                                couleur_int = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
                                couleur_ext = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
                                epaisseur_mm = row.iloc[4] if pd.notna(row.iloc[4]) else 0.0
                                
                                # Convertir epaisseur_mm en float si ce n'est pas déjà le cas
                                try:
                                    epaisseur_mm = float(epaisseur_mm)
                                except:
                                    epaisseur_mm = 0.0
                                
                                # Ajouter uniquement si la dénomination n'est pas vide
                                if denomination and denomination != "nan" and denomination.strip():
                                    if add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
                                        imported_count += 1
                                    else:
                                        duplicate_count += 1
                            except Exception as e:
                                error_count += 1
                                st.warning(f"Erreur ligne {idx + 2}: {str(e)}")
                            
                            # Mettre à jour la barre de progression
                            progress_bar.progress((idx + 1) / len(df_import))
                        
                        # Afficher les résultats
                        if imported_count > 0:
                            st.success(f"✅ {imported_count} correspondances importées avec succès !")
                        if duplicate_count > 0:
                            st.info(f"ℹ️ {duplicate_count} correspondances déjà existantes (doublons ignorés)")
                        if error_count > 0:
                            st.warning(f"⚠️ {error_count} erreurs rencontrées")
                        
                        st.rerun()
            
            except Exception as e:
                st.error(f"❌ Erreur lors de l'import : {str(e)}")
                st.exception(e)
    
    st.markdown("---")
    
    # Afficher les correspondances existantes
    st.markdown("### 📋 Liste des correspondances")
    df_correspondances = get_all_correspondances()
    
    if len(df_correspondances) > 0:
        st.dataframe(df_correspondances, use_container_width=True, height=300)
    else:
        st.info("Aucune correspondance enregistrée pour le moment.")
    
    st.markdown("---")
    
    # Formulaire d'ajout/édition
    st.markdown("### ✏️ Ajouter / Modifier une correspondance")
    
    # Récupérer les IDs pour le sélecteur d'édition
    if len(df_correspondances) > 0:
        correspondance_ids = df_correspondances['id'].tolist()
        edit_id = st.selectbox("Modifier une correspondance existante (ou 'Nouvelle' pour ajouter)", 
                               ["Nouvelle"] + [f"ID: {id}" for id in correspondance_ids])
        
        if edit_id.startswith("ID:"):
            # Mode édition
            id_to_edit = int(edit_id.split(":")[1])
            row = df_correspondances[df_correspondances['id'] == id_to_edit].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                denomination = st.text_input("Dénomination", value=row['denomination'])
                forme_panneau = st.text_input("Forme de panneau", value=row['forme_panneau'])
                couleur_int = st.text_input("Couleur int", value=row['couleur_int'])
            with col2:
                couleur_ext = st.text_input("Couleur ext", value=row['couleur_ext'])
                epaisseur_mm = st.number_input("Epaisseur (mm)", value=float(row['epaisseur_mm']) if pd.notna(row['epaisseur_mm']) else 0.0)
            
            col_update, col_delete = st.columns(2)
            with col_update:
                if st.button("💾 Mettre à jour", type="primary", use_container_width=True):
                    update_correspondance(id_to_edit, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
                    st.success("✅ Correspondance mise à jour !")
                    st.rerun()
            
            with col_delete:
                if st.button("🗑️ Supprimer", use_container_width=True):
                    delete_correspondance(id_to_edit)
                    st.success("✅ Correspondance supprimée !")
                    st.rerun()
        else:
            # Mode ajout
            col1, col2 = st.columns(2)
            with col1:
                denomination = st.text_input("Dénomination *")
                forme_panneau = st.text_input("Forme de panneau *")
                couleur_int = st.text_input("Couleur int *")
            with col2:
                couleur_ext = st.text_input("Couleur ext *")
                epaisseur_mm = st.number_input("Epaisseur (mm) *", value=0.0)
            
            if st.button("➕ Ajouter", type="primary", use_container_width=True):
                if denomination and forme_panneau and couleur_int and couleur_ext:
                    if add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
                        st.success("✅ Correspondance ajoutée !")
                    else:
                        st.warning("⚠️ Cette correspondance existe déjà dans la base de données.")
                    st.rerun()
                else:
                    st.error("❌ Veuillez remplir tous les champs obligatoires")
    else:
        # Mode ajout initial
        col1, col2 = st.columns(2)
        with col1:
            denomination = st.text_input("Dénomination *")
            forme_panneau = st.text_input("Forme de panneau *")
            couleur_int = st.text_input("Couleur int *")
        with col2:
            couleur_ext = st.text_input("Couleur ext *")
            epaisseur_mm = st.number_input("Epaisseur (mm) *", value=0.0)
        
        if st.button("➕ Ajouter", type="primary", use_container_width=True):
            if denomination and forme_panneau and couleur_int and couleur_ext:
                if add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
                    st.success("✅ Correspondance ajoutée !")
                else:
                    st.warning("⚠️ Cette correspondance existe déjà dans la base de données.")
                st.rerun()
            else:
                st.error("❌ Veuillez remplir tous les champs obligatoires")

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
