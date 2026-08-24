import streamlit as st
import time

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Custom Book Creator", page_icon="📚", layout="wide")

st.title("📚 Build Your Custom Activity Book")
st.write("Configure the options below to generate a personalized tracing and coloring book instantly.")

# --- SIDEBAR CONTROLS (Customer Options) ---
with st.sidebar:
    st.header("1. Personalization")
    child_name = st.text_input("Child's Name", value="Aarav")
    child_age = st.number_input("Child's Age", min_value=2, max_value=8, value=4)
    child_class = st.selectbox("Class", ["Pre-K", "Nursery", "LKG", "UKG", "Class 1"])
    
    st.header("2. Book Specifications")
    book_title = st.text_input("Custom Book Title", value=f"{child_name}'s Big Book of ABCs")
    paper_size = st.selectbox("Paper Size", ["A4 (Standard Print)", "US Letter (8.5 x 11)"])
    color_mode = st.radio("Ink Type", ["Black & White (Coloring Focus)", "Full Color Images"])
    font_style = st.selectbox("Font Style", ["Standard Print (Helvetica)", "Dyslexia-Friendly"])
    
    st.divider()
    generate_button = st.button("🚀 Generate PDF Now", use_container_width=True, type="primary")

# --- MAIN PREVIEW AREA ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Your Current Configuration")
    st.info(f"**Title:** {book_title}")
    st.write(f"**Prepared For:** {child_name}, Age {child_age} ({child_class})")
    st.write(f"**Format:** {paper_size} | {color_mode} | {font_style}")

with col2:
    st.subheader("Live Cover Preview")
    # In a real deployment, use Pillow to generate a dynamic thumbnail here
    st.image("https://placehold.co/400x550/e2e8f0/0f172a?text=Cover+Preview", caption="Template Visualization")

# --- FAST GENERATION LOGIC ---
if generate_button:
    with st.spinner("Compiling custom book from local assets... (Zero Internet Required)"):
        # Mock delay to represent local PDF assembly
        time.sleep(1.5) 
        
        # Here the ReportLab code will run, routing strictly to local files: 
        # e.g., c.drawImage(f"assets/{letter}_color.png", ...)
        
        st.success("✅ Book Generated Successfully!")
        st.download_button(
            label=f"📥 Download {child_name}'s Book",
            data=b"Mock PDF Data", 
            file_name=f"{child_name}_Custom_Workbook.pdf",
            mime="application/pdf"
        )
