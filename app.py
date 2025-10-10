import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Transformation CSV/Excel",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Transformation de fichiers CSV/Excel")
st.markdown("---")

def fill_empty_columns(df):
    """
    Remplit les colonnes A et F vides en se basant sur les paires de valeurs B-C.
    Si une ligne a les colonnes A et F vides, cherche une autre ligne avec les mêmes
    valeurs B et C et copie les valeurs A et F de cette ligne.
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
                
                df_transformed = fill_empty_columns(df)
                
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
    - Si une ligne a les mêmes valeurs dans les colonnes B et C qu'une autre ligne,
      les valeurs A et F de cette autre ligne sont copiées dans la ligne vide
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

