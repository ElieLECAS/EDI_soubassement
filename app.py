import streamlit as st
import pandas as pd
import io
import duckdb
import os
from pathlib import Path
from typing import Tuple, Optional
from dataclasses import dataclass

# ==============================================================================
# CONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title="Transformation CSV/Excel",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Transformation de fichiers CSV/Excel")

# Configuration
DB_PATH = "/app/data/correspondances.duckdb"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Constantes pour la structure des fichiers
COLUMN_NAMES = [
    'Date', 'Reference', 'Position', 'Quantite', 'Denomination',
    'Largeur', 'Hauteur', 'Ral intérieur', 'Ral extérieur', 'Reference_Dupliquee'
]

ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
SECTOR_PRIORITY = ['ALU', 'PE', 'TEX']

# ==============================================================================
# MODÈLES DE DONNÉES
# ==============================================================================

@dataclass
class Correspondence:
    """Modèle de données pour une correspondance"""
    denomination: str
    forme_panneau: str
    couleur_int: str
    couleur_ext: str
    epaisseur_mm: float

# ==============================================================================
# FONCTIONS UTILITAIRES
# ==============================================================================

def find_column(df: pd.DataFrame, *names: str, fallback_index: Optional[int] = None) -> Optional[str]:
    """Trouve une colonne par son nom ou retourne une colonne par index"""
    col_names = df.columns.tolist()
    for name in names:
        if name in col_names:
            return name
    
    if fallback_index is not None and fallback_index < len(col_names):
        return col_names[fallback_index]
    return None

def is_empty(value) -> bool:
    """Vérifie si une valeur est vide"""
    return pd.isna(value) or (isinstance(value, str) and value.strip() == '')

def clean_string(value) -> str:
    """Nettoie une chaîne de caractères"""
    return str(value).strip() if pd.notna(value) else ''

def split_on_dot(value: str) -> Tuple[str, str]:
    """Sépare une chaîne au point"""
    if pd.isna(value) or value == 'nan' or value.strip() == '':
        return '', ''
    
    parts = str(value).split('.', 1)
    left = parts[0] if parts[0] else ''
    right = parts[1] if len(parts) > 1 else ''
    return left, right

# ==============================================================================
# BASE DE DONNÉES
# ==============================================================================

@st.cache_resource
def init_database():
    """Initialise la base de données DuckDB"""
    conn = duckdb.connect(DB_PATH)
    
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS correspondances_id_seq START 1
    """)
    
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

def get_all_correspondances() -> pd.DataFrame:
    """Récupère toutes les correspondances"""
    conn = init_database()
    return conn.execute("""
        SELECT id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm 
        FROM correspondances 
        ORDER BY id
    """).df()

def add_correspondance(denomination: str, forme_panneau: str, 
                       couleur_int: str, couleur_ext: str, epaisseur_mm: float) -> bool:
    """Ajoute une correspondance si elle n'existe pas déjà"""
    conn = init_database()
    
    result = conn.execute("""
        SELECT COUNT(*) FROM correspondances 
        WHERE denomination = ? AND forme_panneau = ? 
        AND couleur_int = ? AND couleur_ext = ? AND epaisseur_mm = ?
    """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm]).fetchone()
    
    if result[0] == 0:
        conn.execute("""
            INSERT INTO correspondances 
            (denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
            VALUES (?, ?, ?, ?, ?)
        """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm])
        st.cache_resource.clear()
        return True
    return False

def update_correspondance(id: int, denomination: str, forme_panneau: str,
                          couleur_int: str, couleur_ext: str, epaisseur_mm: float):
    """Met à jour une correspondance"""
    conn = init_database()
    conn.execute("""
        UPDATE correspondances 
        SET denomination = ?, forme_panneau = ?, couleur_int = ?, couleur_ext = ?, epaisseur_mm = ?
        WHERE id = ?
    """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm, id])
    st.cache_resource.clear()

def delete_correspondance(id: int):
    """Supprime une correspondance"""
    conn = init_database()
    conn.execute("DELETE FROM correspondances WHERE id = ?", [id])
    st.cache_resource.clear()

def get_correspondance_by_id(id: int) -> Optional[pd.Series]:
    """Récupère une correspondance par son ID"""
    conn = init_database()
    df = conn.execute("""
        SELECT id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm 
        FROM correspondances 
        WHERE id = ?
    """, [id]).df()
    
    if len(df) > 0:
        return df.iloc[0]
    return None

def search_correspondances(search_term: str) -> pd.DataFrame:
    """Recherche des correspondances"""
    conn = init_database()
    search_pattern = f"%{search_term}%"
    return conn.execute("""
        SELECT id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm 
        FROM correspondances 
        WHERE denomination LIKE ? OR forme_panneau LIKE ? OR couleur_int LIKE ? OR couleur_ext LIKE ?
        ORDER BY id
    """, [search_pattern, search_pattern, search_pattern, search_pattern]).df()

def export_correspondances_to_excel() -> io.BytesIO:
    """Exporte les correspondances vers Excel"""
    df = get_all_correspondances()
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer

def export_correspondances_to_csv() -> io.StringIO:
    """Exporte les correspondances vers CSV"""
    df = get_all_correspondances()
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, sep=';')
    buffer.seek(0)
    return buffer

# ==============================================================================
# LECTURE DES FICHIERS
# ==============================================================================

def read_file(uploaded_file) -> pd.DataFrame:
    """Lit un fichier CSV ou Excel"""
    if uploaded_file.name.endswith('.csv'):
        return _read_csv_with_multiple_encodings(uploaded_file)
    else:
        return pd.read_excel(uploaded_file, header=None)

def _read_csv_with_multiple_encodings(uploaded_file) -> pd.DataFrame:
    """Lit un CSV en essayant plusieurs encodages"""
    for encoding in ENCODINGS:
        for sep in [';', ',']:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, sep=sep, header=None, encoding=encoding)
                st.info(f"✅ Fichier lu avec l'encodage : {encoding}, séparateur : {sep}")
                return df
            except (UnicodeDecodeError, Exception):
                continue
    
    st.error("Impossible de lire le fichier avec les encodages supportés.")
    st.stop()
    return pd.DataFrame()

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prépare le dataframe avec les colonnes appropriées"""
    if len(df.columns) >= 11:
        # Exclure colonne 3 (Libelle_Quantite)
        df = df.iloc[:, [0, 1, 2, 4, 5, 6, 7, 8, 9, 10]]
        df.columns = COLUMN_NAMES
        st.success("✅ Colonnes renommées avec succès (Libelle_Quantite supprimée)")
    return df

# ==============================================================================
# TRANSFORMATIONS DE DONNÉES
# ==============================================================================

def clean_height_column(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie la colonne Hauteur"""
    df_result = df.copy()
    height_col = find_column(df_result, 'Hauteur', fallback_index=6)
    
    if height_col:
        df_result[height_col] = (
            df_result[height_col]
            .astype(str)
            .str.replace('*', '', regex=False)
            .str.strip()
        )
        st.info("✅ Colonne 'Hauteur' nettoyée")
    
    return df_result

def split_reference_column(df: pd.DataFrame) -> pd.DataFrame:
    """Éclate la colonne Reference en N de cde et Extension"""
    df_result = df.copy()
    
    if len(df.columns) < 2:
        return df_result
    
    ref_col = find_column(df, 'Reference', fallback_index=1)
    if not ref_col:
        return df_result
    
    # Séparer les valeurs
    left_values, right_values = zip(*[split_on_dot(v) for v in df_result[ref_col]])
    
    # Renommer et ajouter les colonnes
    df_result = df_result.rename(columns={ref_col: 'N de cde'})
    df_result['N de cde'] = list(left_values)
    df_result.insert(2, 'Extension', list(right_values))
    
    return df_result

def add_sector_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes de secteurs"""
    df_result = df.copy()
    
    if len(df.columns) < 3:
        return df_result
    
    extension_col = find_column(df, 'Extension', fallback_index=2)
    if not extension_col:
        return df_result
    
    extensions = df_result[extension_col].astype(str)
    
    sector_pe = []
    sector_alu = []
    sector_tex = []
    
    for ext in extensions:
        ext_upper = str(ext).upper()
        is_empty_ext = is_empty(ext)
        
        sector_pe.append('PE' if not is_empty_ext and 'P' in ext_upper else '')
        sector_alu.append('ALU' if not is_empty_ext and (ext_upper.startswith('U') or ext_upper.startswith('Y')) else '')
        sector_tex.append('TEX' if not is_empty_ext and any(c in ext_upper for c in ['H', 'Z', 'X']) else '')
    
    df_result.insert(3, 'Secteur ligne vitrage textural', sector_tex)
    df_result.insert(3, 'Secteur ligne vitrage alu', sector_alu)
    df_result.insert(3, 'Secteur ligne vitrage pe', sector_pe)
    
    return df_result

def add_laquage_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la colonne Laquage face alu"""
    df_result = df.copy()
    
    if len(df.columns) < 10:
        return df_result
    
    denomination_col = find_column(df, 'Denomination', fallback_index=9)
    if not denomination_col:
        return df_result
    
    denominations = df_result[denomination_col].astype(str)
    
    laquage_values = []
    
    for denom in denominations:
        denom_upper = str(denom).upper()
        # Vérifie si la dénomination contient lq, laq, ivoi, ano
        if any(keyword in denom_upper for keyword in ['LQ', 'LAQ', 'IVOI', 'ANO']):
            laquage_values.append('oui')
        else:
            laquage_values.append('')
    
    df_result.insert(len(df_result.columns), 'Laquage face alu', laquage_values)
    
    return df_result

def fill_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remplit les colonnes Date et Denomination vides"""
    df_result = df.copy()
    
    if len(df.columns) < 6:
        return df_result
    
    col_a = find_column(df, 'Date', fallback_index=0)
    col_b = find_column(df, 'N de cde', 'Reference', fallback_index=1)
    col_c = find_column(df, 'Code', fallback_index=6)
    col_f = find_column(df, 'Denomination', fallback_index=9)
    
    if not all([col_a, col_b, col_c, col_f]):
        return df_result
    
    for idx in df_result.index:
        val_a, val_f = df_result.loc[idx, col_a], df_result.loc[idx, col_f]
        
        if is_empty(val_a) and is_empty(val_f):
            val_b, val_c = df_result.loc[idx, col_b], df_result.loc[idx, col_c]
            
            for other_idx in df_result.index:
                if other_idx != idx:
                    other_b = df_result.loc[other_idx, col_b]
                    other_c = df_result.loc[other_idx, col_c]
                    other_a = df_result.loc[other_idx, col_a]
                    other_f = df_result.loc[other_idx, col_f]
                    
                    if val_b == other_b and val_c == other_c:
                        if not is_empty(other_a) and not is_empty(other_f):
                            df_result.loc[idx, col_a] = other_a
                            df_result.loc[idx, col_f] = other_f
                            break
    
    return df_result

def merge_with_correspondances(df: pd.DataFrame) -> pd.DataFrame:
    """Effectue un merge avec la table de correspondances"""
    df_result = df.copy()
    
    if len(df.columns) < 10:
        st.warning("⚠️ Le fichier doit avoir au moins 10 colonnes pour le merge")
        return df_result
    
    df_correspondances = get_all_correspondances()
    
    if len(df_correspondances) == 0:
        st.warning("⚠️ Aucune correspondance trouvée dans la base de données")
        return df_result
    
    denomination_col = find_column(df, 'Denomination', fallback_index=9)
    if not denomination_col:
        return df_result
    
    df_result = df_result.reset_index(drop=True)
    df_result['denomination_key'] = df_result[denomination_col].astype(str).str.strip()
    df_correspondances['denomination_key'] = df_correspondances['denomination'].astype(str).str.strip()
    
    df_merged = pd.merge(
        df_result,
        df_correspondances[['denomination_key', 'forme_panneau', 'couleur_int', 'couleur_ext', 'epaisseur_mm']],
        on='denomination_key',
        how='left'
    )
    
    matched_count = df_merged['forme_panneau'].notna().sum()
    st.info(f"📊 {matched_count} correspondances trouvées sur {len(df_merged)} lignes")
    
    return df_merged.drop(columns=['denomination_key'])

def add_concatenated_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la colonne concaténée"""
    df_result = df.copy()
    
    if len(df.columns) < 7:
        st.warning("⚠️ Le fichier doit avoir au moins 7 colonnes pour la concaténation")
        return df_result
    
    col_1 = find_column(df, 'N de cde', 'Reference', fallback_index=1)
    col_ext = find_column(df, 'Extension', fallback_index=2)
    col_2 = find_column(df, 'Code', fallback_index=6)
    
    if not all([col_1, col_ext, col_2]):
        return df_result
    
    # Colonnes de secteurs
    col_pe = df.columns[3] if len(df.columns) > 3 else None
    col_alu = df.columns[4] if len(df.columns) > 4 else None
    col_tex = df.columns[5] if len(df.columns) > 5 else None
    
    concat_values = []
    
    for idx in df_result.index:
        val_1 = clean_string(df_result.loc[idx, col_1])
        val_ext = clean_string(df_result.loc[idx, col_ext])
        val_pos = clean_string(df_result.loc[idx, col_2])
        
        val_pe = clean_string(df_result.loc[idx, col_pe] if col_pe else '')
        val_alu = clean_string(df_result.loc[idx, col_alu] if col_alu else '')
        val_tex = clean_string(df_result.loc[idx, col_tex] if col_tex else '')
        
        # Priorité : ALU > PE > TEX
        secteur = val_alu or val_pe or val_tex
        
        parts = []
        if val_1 and val_ext:
            parts.append(f"{val_1}.{val_ext}")
        elif val_1:
            parts.append(val_1)
        
        if val_pos:
            parts.append(val_pos)
        
        if secteur:
            parts.append(secteur)
        
        concat_values.append('/'.join(parts))
    
    # Supprimer l'ancienne colonne Reference si elle existe
    if 'Reference' in df_result.columns:
        df_result = df_result.drop(columns=['Reference'])
    
    df_result.insert(0, 'Informations à noter sur étiquette', concat_values)
    
    return df_result

# ==============================================================================
# PIPELINE DE TRANSFORMATION
# ==============================================================================

def transform_file(df: pd.DataFrame) -> pd.DataFrame:
    """Pipeline complet de transformation"""
    df = clean_height_column(df)
    df = split_reference_column(df)
    df = add_sector_columns(df)
    df = fill_empty_columns(df)
    df = merge_with_correspondances(df)
    df = add_concatenated_column(df)
    df = add_laquage_column(df)
    return df

# ==============================================================================
# INTERFACE STREAMLIT - TRANSFORMATION
# ==============================================================================

def render_transformation_tab():
    """Onglet de transformation de fichiers"""
    st.subheader("📁 Importer votre fichier")
    
    uploaded_file = st.file_uploader(
        "Glissez-déposez votre fichier CSV ou Excel ici",
        type=['csv', 'xlsx', 'xls'],
        help="Formats acceptés : CSV, Excel (.xlsx, .xls). Le traitement démarre automatiquement."
    )
    
    if uploaded_file is not None:
        try:
            with st.spinner("📥 Lecture et préparation du fichier..."):
                df = read_file(uploaded_file)
                df = prepare_dataframe(df)
            
            # Transformation automatique
            with st.spinner("🔄 Transformation en cours..."):
                df_transformed = transform_file(df)
            
            # Afficher uniquement le fichier transformé
            st.subheader("✅ Fichier transformé")
            st.dataframe(df_transformed, use_container_width=True)
            
            # Téléchargement
            st.markdown("---")
            st.subheader("💾 Télécharger le résultat")
            _render_download_buttons(df_transformed, uploaded_file.name)
        
        except Exception as e:
            st.error(f"❌ Erreur lors du traitement du fichier : {str(e)}")
            st.exception(e)
    else:
        _render_instructions()

def _render_download_buttons(df: pd.DataFrame, original_filename: str):
    """Affiche les boutons de téléchargement"""
    col1, col2 = st.columns(2)
    
    with col1:
        # Préparer le CSV selon les spécifications
        df_csv = prepare_csv_for_export(df.copy())
        csv_buffer = io.StringIO()
        # Utiliser UTF-8-SIG pour Excel et UTF-8 pour compatibilité
        df_csv.to_csv(csv_buffer, index=False, sep=';', encoding='utf-8-sig')
        st.download_button(
            label="📥 Télécharger en CSV",
            data=csv_buffer.getvalue().encode('utf-8-sig'),
            file_name=f"transforme_{original_filename.replace('.xlsx', '.csv').replace('.xls', '.csv')}",
            mime="text/csv; charset=utf-8",
            use_container_width=True
        )
    
    with col2:
        excel_buffer = io.BytesIO()
        df.to_excel(excel_buffer, index=False, header=False, engine='openpyxl')
        st.download_button(
            label="📥 Télécharger en Excel",
            data=excel_buffer.getvalue(),
            file_name=f"transforme_{original_filename.replace('.csv', '.xlsx')}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

def prepare_csv_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """Prépare le dataframe pour l'export CSV avec les modifications spécifiées"""
    df_result = df.copy()
    
    # 1. Renommer Date en Jour de livraison souhaitée
    if 'Date' in df_result.columns:
        df_result = df_result.rename(columns={'Date': 'Jour de livraison souhaitée'})
    
    # 2. Supprimer la colonne Denomination
    if 'Denomination' in df_result.columns:
        df_result = df_result.drop(columns=['Denomination'])
    
    # 3. Supprimer Reference_Dupliquee
    if 'Reference_Dupliquee' in df_result.columns:
        df_result = df_result.drop(columns=['Reference_Dupliquee'])
    
    # 4. Supprimer les 3 colonnes Secteur
    for col in df_result.columns:
        if 'Secteur' in col:
            df_result = df_result.drop(columns=[col])
    
    # 5. Déplacer epaisseur_mm à gauche de Largeur si les deux colonnes existent
    if 'epaisseur_mm' in df_result.columns and 'Largeur' in df_result.columns:
        # Obtenir l'index de Largeur
        largeur_idx = df_result.columns.get_loc('Largeur')
        
        # Supprimer epaisseur_mm
        epaisseur = df_result.pop('epaisseur_mm')
        
        # Insérer epaisseur_mm avant Largeur
        df_result.insert(largeur_idx, 'epaisseur_mm', epaisseur)
    
    return df_result

def _render_instructions():
    """Affiche les instructions"""
    st.info("""
    👆 **Instructions :**
    1. Glissez-déposez votre fichier CSV ou Excel ci-dessus
    2. Le traitement démarre automatiquement
    3. Visualisez le fichier transformé
    4. Téléchargez le résultat
    """)

# ==============================================================================
# INTERFACE STREAMLIT - CORRESPONDANCES
# ==============================================================================

def render_correspondences_tab():
    """Onglet de gestion des correspondances"""
    st.subheader("🗂️ Gestion des correspondances")
    init_database()
    
    # Onglets pour les différentes actions
    action_tab1, action_tab2, action_tab3, action_tab4 = st.tabs([
        "📋 Liste", 
        "➕ Ajouter", 
        "✏️ Modifier", 
        "🗑️ Supprimer"
    ])
    
    df_correspondances = get_all_correspondances()
    
    with action_tab1:
        _render_list_tab(df_correspondances)
    
    with action_tab2:
        _render_add_tab()
    
    with action_tab3:
        _render_edit_tab(df_correspondances)
    
    with action_tab4:
        _render_delete_tab(df_correspondances)
    
    st.markdown("---")
    
    # Import en bas de page
    with st.expander("📥 Importer depuis un fichier Excel ou CSV", expanded=False):
        _render_import_section()

def _render_import_section():
    """Section d'import"""
    uploaded_file = st.file_uploader(
        "Glissez-déposez votre fichier Excel ou CSV de correspondances",
        type=['xlsx', 'xls', 'csv'],
        help="Format attendu : Dénomination | Forme de panneau | Couleur int | Couleur ext | Epaisseur mm"
    )
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_import = _read_csv_with_multiple_encodings(uploaded_file)
            else:
                df_import = pd.read_excel(uploaded_file)
            
            if len(df_import.columns) < 5:
                st.error("❌ Le fichier doit contenir au moins 5 colonnes")
            else:
                st.success(f"✅ Fichier chargé : {len(df_import)} lignes détectées")
                st.dataframe(df_import.head(10), use_container_width=True)
                
                if st.button("📥 Importer les données", type="primary", use_container_width=True):
                    _import_correspondences(df_import)
        
        except Exception as e:
            st.error(f"❌ Erreur lors de l'import : {str(e)}")
            st.exception(e)

def _import_correspondences(df: pd.DataFrame):
    """Importe les correspondances"""
    progress_bar = st.progress(0)
    imported_count = duplicate_count = error_count = 0
    
    for idx, row in df.iterrows():
        try:
            denomination = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            forme_panneau = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            couleur_int = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
            couleur_ext = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
            
            try:
                epaisseur_mm = float(row.iloc[4]) if pd.notna(row.iloc[4]) else 0.0
            except:
                epaisseur_mm = 0.0
            
            if denomination and denomination != "nan" and denomination.strip():
                if add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
                    imported_count += 1
                else:
                    duplicate_count += 1
        except Exception as e:
            error_count += 1
            st.warning(f"Erreur ligne {idx + 2}: {str(e)}")
        
        progress_bar.progress((idx + 1) / len(df))
    
    if imported_count > 0:
        st.success(f"✅ {imported_count} correspondances importées !")
    if duplicate_count > 0:
        st.info(f"ℹ️ {duplicate_count} doublons ignorés")
    if error_count > 0:
        st.warning(f"⚠️ {error_count} erreurs")
    
    st.rerun()

def _render_list_tab(df_correspondances: pd.DataFrame):
    """Onglet d'affichage de la liste"""
    st.markdown("### 📋 Liste des correspondances")
    
    if len(df_correspondances) > 0:
        # Barre de recherche
        col_search, col_action = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 Rechercher", placeholder="Rechercher dans les correspondances...")
        with col_action:
            st.write("")  # Alignement vertical
            if st.button("Effacer", use_container_width=True):
                st.rerun()
        
        # Filtrer les résultats
        if search_term:
            filtered_df = df_correspondances[
                df_correspondances['denomination'].str.contains(search_term, case=False, na=False) |
                df_correspondances['forme_panneau'].str.contains(search_term, case=False, na=False) |
                df_correspondances['couleur_int'].str.contains(search_term, case=False, na=False) |
                df_correspondances['couleur_ext'].str.contains(search_term, case=False, na=False)
            ]
            display_df = filtered_df
        else:
            display_df = df_correspondances
        
        st.markdown("---")
        
        if len(display_df) > 0:
            st.dataframe(
                display_df,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            st.markdown("---")
            
            # Boutons d'export
            st.markdown("#### 💾 Exporter les correspondances")
            col_export1, col_export2 = st.columns(2)
            with col_export1:
                excel_buffer = export_correspondances_to_excel()
                st.download_button(
                    label="📥 Exporter en Excel",
                    data=excel_buffer,
                    file_name="correspondances.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            with col_export2:
                csv_buffer = export_correspondances_to_csv()
                st.download_button(
                    label="📥 Exporter en CSV",
                    data=csv_buffer.getvalue(),
                    file_name="correspondances.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # Statistiques
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total correspondances", len(df_correspondances))
            with col2:
                st.metric("Correspondances affichées", len(display_df))
            with col3:
                if search_term:
                    st.metric("Résultats trouvés", len(display_df))
                else:
                    unique_denominations = df_correspondances['denomination'].nunique()
                    st.metric("Dénominations uniques", unique_denominations)
        else:
            st.warning("⚠️ Aucun résultat trouvé pour votre recherche")
    else:
        st.info("ℹ️ Aucune correspondance enregistrée pour le moment.")

def _render_add_tab():
    """Onglet d'ajout"""
    st.markdown("### ➕ Ajouter une nouvelle correspondance")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        denomination = st.text_input("Dénomination *", help="Ex: Alu blanc")
        forme_panneau = st.text_input("Forme de panneau *", help="Ex: Plat")
        couleur_int = st.text_input("Couleur int *", help="Ex: Blanc")
    with col2:
        couleur_ext = st.text_input("Couleur ext *", help="Ex: Gris")
        epaisseur_mm = st.number_input("Epaisseur (mm) *", value=0.0, min_value=0.0, step=0.1, help="Epaisseur en millimètres")
    
    st.markdown("---")
    
    if st.button("➕ Ajouter la correspondance", type="primary", use_container_width=True):
        if denomination and forme_panneau and couleur_int and couleur_ext:
            if add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm):
                st.success("✅ Correspondance ajoutée avec succès !")
                st.rerun()
            else:
                st.warning("⚠️ Cette correspondance existe déjà dans la base de données")
        else:
            st.error("❌ Veuillez remplir tous les champs obligatoires")

def _render_edit_tab(df_correspondances: pd.DataFrame):
    """Onglet de modification"""
    st.markdown("### ✏️ Modifier une correspondance existante")
    st.markdown("---")
    
    if len(df_correspondances) == 0:
        st.info("ℹ️ Aucune correspondance à modifier pour le moment.")
        return
    
    # Sélection de la correspondance à modifier
    df_display = df_correspondances.copy()
    df_display['affichage'] = df_display['id'].astype(str) + " - " + df_display['denomination']
    
    selected_display = st.selectbox(
        "Sélectionner la correspondance à modifier",
        options=df_display['affichage'].tolist()
    )
    
    selected_id = int(selected_display.split(" - ")[0])
    row = df_correspondances[df_correspondances['id'] == selected_id].iloc[0]
    
    st.markdown("---")
    st.markdown("#### Informations actuelles")
    
    col1, col2 = st.columns(2)
    with col1:
        denomination = st.text_input("Dénomination", value=row['denomination'], key="edit_denomination")
        forme_panneau = st.text_input("Forme de panneau", value=row['forme_panneau'], key="edit_forme")
        couleur_int = st.text_input("Couleur int", value=row['couleur_int'], key="edit_couleur_int")
    with col2:
        couleur_ext = st.text_input("Couleur ext", value=row['couleur_ext'], key="edit_couleur_ext")
        epaisseur_mm = st.number_input(
            "Epaisseur (mm)",
            value=float(row['epaisseur_mm']) if pd.notna(row['epaisseur_mm']) else 0.0,
            min_value=0.0,
            step=0.1,
            key="edit_epaisseur"
        )
    
    st.markdown("---")
    
    if st.button("💾 Mettre à jour la correspondance", type="primary", use_container_width=True):
        update_correspondance(selected_id, denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
        st.success("✅ Correspondance mise à jour avec succès !")
        st.rerun()

def _render_delete_tab(df_correspondances: pd.DataFrame):
    """Onglet de suppression"""
    st.markdown("### 🗑️ Supprimer une correspondance")
    st.markdown("---")
    
    if len(df_correspondances) == 0:
        st.info("ℹ️ Aucune correspondance à supprimer pour le moment.")
        return
    
    # Sélection de la correspondance à supprimer
    df_display = df_correspondances.copy()
    df_display['affichage'] = (
        df_display['id'].astype(str) + " - " + 
        df_display['denomination'] + " (" + 
        df_display['forme_panneau'].fillna('N/A').astype(str) + ")"
    )
    
    selected_display = st.selectbox(
        "Sélectionner la correspondance à supprimer",
        options=df_display['affichage'].tolist()
    )
    
    selected_id = int(selected_display.split(" - ")[0])
    row = df_correspondances[df_correspondances['id'] == selected_id].iloc[0]
    
    st.markdown("---")
    st.markdown("#### 📋 Informations de la correspondance")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**Dénomination:** {row['denomination']}")
        st.info(f"**Forme de panneau:** {row['forme_panneau']}")
        st.info(f"**Couleur int:** {row['couleur_int']}")
    with col2:
        st.info(f"**Couleur ext:** {row['couleur_ext']}")
        st.info(f"**Epaisseur (mm):** {row['epaisseur_mm']}")
    
    st.markdown("---")
    
    st.warning("⚠️ Cette action est irréversible. Êtes-vous sûr de vouloir supprimer cette correspondance ?")
    
    if st.button("🗑️ Supprimer définitivement", type="primary", use_container_width=True):
        delete_correspondance(selected_id)
        st.success("✅ Correspondance supprimée avec succès !")
        st.rerun()

# ==============================================================================
# APPLICATION PRINCIPALE
# ==============================================================================

def main():
    """Point d'entrée principal"""
    tab1, tab2 = st.tabs(["🔄 Transformation de fichiers", "🗂️ Gestion des correspondances"])
    
    with tab1:
        render_transformation_tab()
    
    with tab2:
        render_correspondences_tab()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """<div style='text-align: center; color: #888;'>Développé avec ❤️ en Streamlit</div>""",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
else:
    main()
