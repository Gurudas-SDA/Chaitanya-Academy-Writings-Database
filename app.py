# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import re
import unicodedata
import os

st.set_page_config(page_title="Chaitanya Academy Writings Database", layout="wide")

# === Ceļš uz datubāzi (Excel blakus app.py) ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_FILE = os.path.join(SCRIPT_DIR, "250928Versebase_app.xlsx")

# === CSS ===
st.markdown("""
<style>
/* pamatteksts */
p { margin: 0; line-height: 1.2; }

/* Virsraksts */
.sv-title { font-size: 2rem; font-weight: 700; margin: 0.5rem 0 0.75rem 0; }

/* ATSTARPES KONTROLE */
:root{
  --verse-line-gap: 0.15rem;
  --verse-block-gap: 0.6rem;
}
.verse-line { margin: 0 0 var(--verse-line-gap) 0; line-height: 1.2; }
.verse-gap  { height: var(--verse-block-gap); }

.block-container { padding-top: 1rem; }

/* Dropdown width */
div[data-baseweb="select"] { max-width: 100%; }
</style>
""", unsafe_allow_html=True)

# === Palīgfunkcijas ===
def clean_verse_text(text: str) -> str:
    """Notīra Excel encoding artefaktus un citus nevēlamus simbolus"""
    if not text:
        return ""
    text = text.replace('_x000D_', '').replace('_x000A_', '')
    text = re.sub(r'\s*\(\d+\)\s*$', '', text)
    return text.strip()

@st.cache_data
def load_database_from_file(file_path: str):
    """Ielādē datubāzi no Excel faila"""
    df = pd.read_excel(file_path, sheet_name=0)
    database = []
    for _, row in df.iterrows():
        if pd.notna(row.get('IAST Verse')) and str(row.get('IAST Verse')).strip():
            database.append({
                'iast_verse': clean_verse_text(str(row.get('IAST Verse', '')).strip()),
                'original_source': str(row.get('Original Source', '')).strip() if pd.notna(row.get('Original Source')) else '',
                'author': str(row.get('Author', '')).strip() if pd.notna(row.get('Author')) else '',
                'context': str(row.get('Context', '')).strip() if pd.notna(row.get('Context')) else '',
                'english_translation': clean_verse_text(str(row.get('Translation', '')).strip()) if pd.notna(row.get('Translation')) else '',
                'cited_in': str(row.get('Cited In', '')).strip() if pd.notna(row.get('Cited In')) else ''
            })
    return database, len(database)

def get_unique_sources(database):
    """Iegūst unikālos Source nosaukumus (no Cited In)"""
    sources = set()
    for entry in database:
        if entry['cited_in']:
            sources.add(entry['cited_in'])
    return sorted(list(sources))

def get_original_sources_for_cited(database, cited_source):
    """Iegūst visus Original Source ierakstus konkrētajam Cited In avotam"""
    original_sources = []
    for entry in database:
        if entry['cited_in'] == cited_source and entry['original_source']:
            if entry['original_source'] not in original_sources:
                original_sources.append(entry['original_source'])
    return sorted(original_sources)

def get_verses_by_source(database, cited_source, original_source, max_verses):
    """Iegūst pantus sākot no izvēlētā Original Source un turpina nākamos no tā paša Cited In"""
    verses = []
    found_start = False
    
    for entry in database:
        # Meklē tikai ierakstus ar pareizo Cited In
        if entry['cited_in'] == cited_source:
            # Kad atrod izvēlēto Original Source, sāk vākt
            if entry['original_source'] == original_source:
                found_start = True
            
            # Vāc pantus tikai pēc tam, kad ir atrasts sākuma punkts
            if found_start:
                verses.append(entry)
                if len(verses) >= max_verses:
                    break
    
    return verses

def clean_author(author: str) -> str:
    """Attīra autora vārdu no 'by' un nederīgām vērtībām"""
    if not author: 
        return ""
    author_str = str(author).strip()
    if author_str.lower() in ['nan', 'none', 'null', '']:
        return ""
    return re.sub(r'^\s*by\s+', '', author_str, flags=re.I).strip()

def format_source_and_author(source, author) -> str:
    """Formatē avota un autora informāciju"""
    a = clean_author(author)
    if source and a: return f"{source} (by {a})"
    if source: return source
    if a: return f"(by {a})"
    return "NOT AVAILABLE"

_by_regex = re.compile(r"\s+by\s+", re.IGNORECASE)
def render_cited_item(text: str) -> str:
    """Formatē citēto avotu ar HTML"""
    if not text or str(text).strip().lower() in ['nan', 'none', 'null', '']:
        return ""
    parts = _by_regex.split(text, maxsplit=1)
    if len(parts) == 2:
        title, author = parts[0].strip(), parts[1].strip()
        return f"<em><strong>{title}</strong> by {author}</em>"
    return f"<em>{text}</em>"

def verse_lines_from_cell(cell: str):
    """Iegūst panta rindas no Excel šūnas"""
    if not cell: return []
    cell = clean_verse_text(cell)
    raw_lines = [clean_verse_text(ln) for ln in str(cell).split("\n") if ln.strip()]
    starred = [ln[1:-1].strip() for ln in raw_lines if ln.startswith("*") and ln.endswith("*") and len(ln) >= 2]
    return starred if starred else raw_lines

# === App ===
def main():
    st.markdown("<h1>Chaitanya Academy Writings Database</h1>", unsafe_allow_html=True)

    # Automātiska ielāde
    if 'database' not in st.session_state and os.path.exists(DEFAULT_DB_FILE):
        with st.spinner('Ielādē datu bāzi...'):
            data, cnt = load_database_from_file(DEFAULT_DB_FILE)
            if data:
                st.session_state['database'] = data
                st.session_state['db_source'] = os.path.basename(DEFAULT_DB_FILE)
                st.session_state['db_count'] = cnt

    if 'database' not in st.session_state:
        st.error("Datu bāze nav pieejama")
        st.stop()

    database = st.session_state['database']
    
    # Iegūst visus source nosaukumus
    all_sources = get_unique_sources(database)
    
    # Sānjosla ar Max verse number slider
    with st.sidebar:
        max_verses = st.slider("Max verse number", 1, 50, 10)
    
    # Galvenā daļa
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Sources")
        if all_sources:
            selected_source = st.selectbox(
                "Select Source",
                options=[""] + all_sources,
                format_func=lambda x: "-- Select Source --" if x == "" else x,
                key="source_select"
            )
        else:
            st.warning("Nav atrasti avoti datubāzē")
            selected_source = ""
    
    with col2:
        st.markdown("### Original source")
        if selected_source and selected_source != "":
            original_sources = get_original_sources_for_cited(database, selected_source)
            if original_sources:
                selected_original = st.selectbox(
                    "Select Original Source",
                    options=[""] + original_sources,
                    format_func=lambda x: "-- Select Original Source --" if x == "" else x,
                    key="original_select"
                )
            else:
                st.info("Nav atrasti Original Source ieraksti šim avotam")
                selected_original = ""
        else:
            st.info("Vispirms izvēlies Source")
            selected_original = ""
    
    # Find the verses poga
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Find the verses", type="primary", disabled=(not selected_source or not selected_original)):
        if selected_source and selected_original:
            with st.spinner('Meklē pantus...'):
                verses = get_verses_by_source(database, selected_source, selected_original, max_verses)
            
            if not verses:
                st.warning("Nav atrasti panti ar šiem parametriem")
            else:
                st.markdown(f"<p><b>FOUND:</b> {len(verses)} verses</p>", unsafe_allow_html=True)
                st.markdown("---")
                
                for verse_data in verses:
                    # Izveido divas kolonnas: kreisā pantam, labā tulkojumam
                    col_verse, col_trans = st.columns([1.2, 1])
                    
                    with col_verse:
                        # Pantus drukājam pa rindām
                        lines = verse_lines_from_cell(verse_data['iast_verse'])
                        if lines:
                            for ln in lines:
                                st.markdown(f"<p class='verse-line'>{ln}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p class='verse-line'>{verse_data['iast_verse']}</p>", unsafe_allow_html=True)
                        
                        # Atstarpe starp pantu un avotiem
                        st.markdown("<div class='verse-gap'></div>", unsafe_allow_html=True)
                        
                        # Primārais avots
                        st.markdown(f"<p>{format_source_and_author(verse_data['original_source'], verse_data['author'])}</p>",
                                    unsafe_allow_html=True)
                        # Sekundārais avots
                        if verse_data['cited_in']:
                            cited_html = render_cited_item(verse_data['cited_in'])
                            if cited_html:
                                st.markdown(f"<p>{cited_html}</p>", unsafe_allow_html=True)
                    
                    with col_trans:
                        st.markdown("<p><b>Translation</b></p>", unsafe_allow_html=True)
                        if verse_data['english_translation']:
                            st.markdown(f"<p>{verse_data['english_translation']}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p style='color: #9ca3af;'>No translation available</p>", unsafe_allow_html=True)
                    
                    st.markdown("---")

if __name__ == "__main__":
    main()
