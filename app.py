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
            # Iegūst NR vērtību un pārveido par int
            nr_value = row.get('NR', 0)
            if pd.notna(nr_value):
                try:
                    nr_value = int(nr_value)
                except:
                    nr_value = 0
            else:
                nr_value = 0
                
            database.append({
                'nr': nr_value,
                'iast_verse': clean_verse_text(str(row.get('IAST Verse', '')).strip()),
                'original_source': str(row.get('Original Source', '')).strip() if pd.notna(row.get('Original Source')) else '',
                'author': str(row.get('Author', '')).strip() if pd.notna(row.get('Author')) else '',
                'context': str(row.get('Context', '')).strip() if pd.notna(row.get('Context')) else '',
                'english_translation': clean_verse_text(str(row.get('Translation', '')).strip()) if pd.notna(row.get('Translation')) else '',
                'cited_in': str(row.get('Cited In', '')).strip() if pd.notna(row.get('Cited In')) else '',
                'type': str(row.get('Type', '')).strip() if pd.notna(row.get('Type')) else '',
                'description': str(row.get('Description', '')).strip() if pd.notna(row.get('Description')) else '',
                'essence_gemini': str(row.get('Essence by Gemini 2.5 Pro', '')).strip() if pd.notna(row.get('Essence by Gemini 2.5 Pro')) else ''
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
    """Iegūst visus Original Source ierakstus konkrētajam Cited In avotam, sakārtotus pēc NR."""
    original_sources_with_nr = []
    seen = set()
    
    for entry in database:
        if entry['cited_in'] == cited_source and entry['original_source']:
            if entry['original_source'] not in seen:
                seen.add(entry['original_source'])
                original_sources_with_nr.append({
                    'source': entry['original_source'],
                    'nr': entry['nr']
                })
    
    # Sakārto pēc NR. un atgriež tikai source nosaukumus
    original_sources_with_nr.sort(key=lambda x: x['nr'])
    return [item['source'] for item in original_sources_with_nr]

def get_verses_by_source(database, cited_source, original_source, max_verses):
    """Iegūst pantus sākot no izvēlētā Original Source, izmantojot NR. no ABIEM parametriem"""
    
    # Atrod PRECĪZO NR. kas atbilst ABIEM: cited_source UN original_source
    start_nr = None
    for entry in database:
        if entry['cited_in'] == cited_source and entry['original_source'] == original_source:
            start_nr = entry['nr']
            break  # Ņem pirmo atbilstošo NR.
    
    if start_nr is None:
        return []
    
    # Tagad atlasa visus ierakstus ar pareizo Cited In un NR. >= start_nr
    matching_verses = []
    for entry in database:
        if entry['cited_in'] == cited_source and entry['nr'] >= start_nr:
            matching_verses.append(entry)
    
    # Sakārto pēc NR. un atgriež tikai max_verses daudzumu
    matching_verses.sort(key=lambda x: x['nr'])
    return matching_verses[:max_verses]

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
        
        # Cache clear poga
        if st.button("🔄 Reload Database", help="Clear cache and reload database from file"):
            st.cache_data.clear()
            st.rerun()
    
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
                        # Original Source PIRMS panta
                        st.markdown(f"<p>{format_source_and_author(verse_data['original_source'], verse_data['author'])}</p>",
                                    unsafe_allow_html=True)
                        
                        # DEBUG: Parādi visus key-value pārus
                        st.write("DEBUG - Available keys:", list(verse_data.keys()))
                        
                        # Papildu lauki zem Original Source (ja tie eksistē)
                        if verse_data.get('type'):
                            st.markdown(f"<p><strong>Type:</strong> {verse_data['type']}</p>", unsafe_allow_html=True)
                        
                        if verse_data.get('description'):
                            st.markdown(f"<p><strong>Description:</strong> {verse_data['description']}</p>", unsafe_allow_html=True)
                        
                        if verse_data.get('essence_gemini'):
                            st.markdown(f"<p><strong>Essence by Gemini 2.5 Pro:</strong> {verse_data['essence_gemini']}</p>", unsafe_allow_html=True)
                        
                        # Neliela atstarpe starp metadatiem un pantu
                        st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
                        
                        # Pantus drukājam pa rindām
                        lines = verse_lines_from_cell(verse_data['iast_verse'])
                        if lines:
                            for ln in lines:
                                st.markdown(f"<p class='verse-line'>{ln}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<p class='verse-line'>{verse_data['iast_verse']}</p>", unsafe_allow_html=True)
                    
                    with col_trans:
                        st.markdown("<p><b>Translation</b></p>", unsafe_allow_html=True)
                        if verse_data['english_translation']:
                            st.markdown(f"<p>{verse_data['english_translation']}</p>", unsafe_allow_html=True)
                        else:
                            st.markdown("<p style='color: #9ca3af;'>No translation available</p>", unsafe_allow_html=True)
                    
                    st.markdown("---")

if __name__ == "__main__":
    main()