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
    """Ajoute une nouvelle correspondance à la base de données"""
    conn = init_database()
    # L'ID est automatiquement généré grâce à la séquence
    conn.execute("""
        INSERT INTO correspondances (denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
        VALUES (?, ?, ?, ?, ?)
    """, [denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm])
    st.cache_resource.clear()

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
    Remplit les colonnes A et F vides en se basant sur les paires de valeurs B-C.
    Si une ligne a les colonnes A et F vides, cherche une autre ligne avec les mêmes
    valeurs B et C et copie les valeurs A et F de cette ligne.
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 10 colonnes (après split et ajout des secteurs)
    if len(df.columns) < 10:
        st.warning("Le fichier transformé doit avoir au moins 10 colonnes")
        return df_result
    
    # Obtenir les noms des colonnes 
    # Après split_column_1 et add_sector_columns: 
    # - index 0=A, 
    # - index 1=B partie gauche,
    # - index 2=Extension (partie droite de B),
    # - index 3=Secteur PE (nouveau),
    # - index 4=Secteur ALU (nouveau),
    # - index 5=Secteur TEX (nouveau),
    # - index 6=C (anciennement 2, décalé de 3 positions),
    # - index 9=F (anciennement 5, décalé de 3 positions)
    col_names = df.columns.tolist()
    col_a = col_names[0]  # Colonne A
    # Les colonnes B et C pour la correspondance sont maintenant aux index 1 et 6
    col_b = col_names[1]  # Colonne B (index 1 après split)
    col_c = col_names[6] if len(col_names) > 6 else col_names[3]  # Colonne C (index 6 après secteurs)
    col_f = col_names[9] if len(col_names) > 9 else col_names[6]  # Colonne F (index 9 après secteurs)
    
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
    Éclate la colonne 1 (colonne B) en deux colonnes en séparant à gauche et à droite du point.
    Exemple: "123.456" devient colonne 1: "123", colonne 2: "456"
    """
    # Créer une copie du dataframe
    df_result = df.copy()
    
    # Vérifier qu'il y a au moins 2 colonnes (colonne 0 et colonne 1)
    if len(df.columns) < 2:
        return df_result
    
    col_names = df.columns.tolist()
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
                    
                    # Éclater la colonne 1 en deux colonnes
                    df_transformed = split_column_1(df)
                    
                    # Ajouter les colonnes de secteurs
                    df_transformed = add_sector_columns(df_transformed)
                    
                    # Ensuite remplir les colonnes vides
                    df_transformed = fill_empty_columns(df_transformed)
                    
                    # Afficher le résultat
                    st.subheader("✅ Fichier transformé")
                    st.dataframe(df_transformed, use_container_width=True)
                    
                    # Compter les modifications
                    col_names = df_transformed.columns.tolist()
                    if len(col_names) >= 10:
                        col_a = col_names[0]
                        col_f = col_names[9] if len(col_names) > 9 else col_names[6]
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
                                st.success(f"🎉 Transformation terminée ! {original_empty_count - empty_after} lignes ont été remplies.")
                        except:
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
                                    add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
                                    imported_count += 1
                            except Exception as e:
                                error_count += 1
                                st.warning(f"Erreur ligne {idx + 2}: {str(e)}")
                            
                            # Mettre à jour la barre de progression
                            progress_bar.progress((idx + 1) / len(df_import))
                        
                        # Afficher les résultats
                        if imported_count > 0:
                            st.success(f"✅ {imported_count} correspondances importées avec succès !")
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
                    add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
                    st.success("✅ Correspondance ajoutée !")
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
                add_correspondance(denomination, forme_panneau, couleur_int, couleur_ext, epaisseur_mm)
                st.success("✅ Correspondance ajoutée !")
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
