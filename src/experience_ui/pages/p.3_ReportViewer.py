"""
Report Viewer for HLAgent outputs.
Beautiful viewer for HTML reports and image files from data/output folder.
"""

import streamlit as st
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import base64
from dotenv import load_dotenv

load_dotenv()

# Add the project root to Python path
project_root = os.getenv("HLAGENT_MAIN_DIRECTORY")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure Streamlit page
st.set_page_config(
    page_title="Report Viewer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Folder descriptions for different output directories
FOLDER_DESCRIPTIONS = {
    "BMarkerRegression": "This folder contains association analysis between HLA markers and disease phenotypes.",
    "BMarkerGenerator": "This folder contains binary marker panel(phenotype and SNPs regression) within chromosome 6 HLA region. Converts HLA typing data into binary marker format for association analysis.",
    "BMarkerStepwiseRegression": "This folder shows stepwise regression analysis results for binary marker panel. Identifies the most significant markers through iterative selection.",
    "HLAImputation": "This folder contains HLA imputation results from various tools (CookHLA, HLA-HD, Optitype etc.). Shows predicted HLA alleles from SNP data.",
    "ConvertGT": "This folder contains genotype conversion results. Shows files converted between different genomic data formats.",
    "ConvertHPED": "This folder contains HPED format conversion results. HPED is a specialized format for HLA fine mapping analysis.",
    "MetaAnalysis": "This folder shows meta-analysis results comparing multiple studies or datasets. Includes summary statistics.",
    "NomenCleaner": "This folder contains HLA nomenclature cleaning results. Standardizes HLA allele names according to official nomenclature.",
    "OmnibusTest": "This folder shows omnibus test results for amino acid HLA association analysis. Tests overall association across multiple HLA loci.",
    "Phasing": "This folder contains phasing results for genotype data. Shows haplotype reconstruction from unphased genotypes.",
    "Imgt2Seq": "This folder contains IMGT reference sequence mapping results. Maps HLA alleles to reference sequences.",
    "backups": "This folder contains backup files from various analysis runs."
}

def initialize_report_session_state():
    """Initialize session state variables for report viewer."""
    if "report_prefixes" not in st.session_state:
        st.session_state.report_prefixes = []
    
    if "report_suffixes" not in st.session_state:
        st.session_state.report_suffixes = [".html", ".png", ".jpg", ".jpeg", ".pdf"]
    
    if "report_filter_words" not in st.session_state:
        st.session_state.report_filter_words = []
    
    if "found_files" not in st.session_state:
        st.session_state.found_files = []
    
    if "selected_file" not in st.session_state:
        st.session_state.selected_file = None

def scan_output_folder(prefixes: List[str], suffixes: List[str], filter_words: List[str] = None) -> List[Dict[str, str]]:
    """
    Scan data/output folder for files matching criteria.
    
    Args:
        prefixes: List of file prefixes to match
        suffixes: List of file extensions to match
        filter_words: List of words that must be present in filename (AND condition)
        
    Returns:
        List of dictionaries with file info
    """
    output_dir = Path(project_root) / "data" / "output"
    found_files = []
    
    if not output_dir.exists():
        return found_files
    
    # Recursively scan all files
    for file_path in output_dir.rglob("*"):
        if file_path.is_file():
            file_name = file_path.name
            relative_path = file_path.relative_to(output_dir)
            parent_folder = relative_path.parts[0] if relative_path.parts else "root"
            
            # Check if file matches prefixes or suffixes
            matches_prefix = any(file_name.startswith(prefix) for prefix in prefixes) if prefixes else False
            matches_suffix = any(file_name.lower().endswith(suffix.lower()) for suffix in suffixes) if suffixes else False
            
            # Must match at least one of prefix OR suffix condition
            if not (matches_prefix or matches_suffix):
                continue
            
            # AND condition: ALL filter words must be present in filename
            if filter_words:
                matches_all_words = all(word.lower() in file_name.lower() for word in filter_words)
                if not matches_all_words:
                    continue
            
            found_files.append({
                "name": file_name,
                "path": str(file_path),
                "relative_path": str(relative_path),
                "parent_folder": parent_folder,
                "size": file_path.stat().st_size,
                "extension": file_path.suffix.lower()
            })
    
    # Sort by parent folder and then by name
    found_files.sort(key=lambda x: (x["parent_folder"], x["name"]))
    return found_files

def get_folder_description(folder_name: str) -> str:
    """Get description for a folder based on its name."""
    return FOLDER_DESCRIPTIONS.get(folder_name, f"This contains results from {folder_name} analysis.")

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def display_html_file(file_path: str):
    """Display HTML file content in Streamlit."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Use Streamlit's components to display HTML
        st.components.v1.html(html_content, height=800, scrolling=True)
        
    except Exception as e:
        st.error(f"Error displaying HTML file: {str(e)}")

def display_image_file(file_path: str):
    """Display image file in Streamlit."""
    try:
        st.image(file_path, use_column_width=True)
    except Exception as e:
        st.error(f"Error displaying image file: {str(e)}")

def display_pdf_file(file_path: str):
    """Display PDF file in Streamlit."""
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        pdf_display = f"""
        <iframe src="data:application/pdf;base64,{base64_pdf}" 
                width="100%" height="800" type="application/pdf">
        </iframe>
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error displaying PDF file: {str(e)}")
        st.info("You can download the PDF file using the download button.")

def create_report_sidebar():
    """Create sidebar for report viewer configuration."""
    with st.sidebar:
        st.header("📊 Report Viewer")
        
        # Step 1: Input configuration
        st.subheader("🔧 Step 1: Configure Filters")
        
        # Prefixes input
        st.markdown("**File Prefixes** (optional):")
        prefixes_input = st.text_area(
            "Enter prefixes (one per line)",
            value="\n".join(st.session_state.report_prefixes),
            height=80,
            placeholder="heatmap\nmanhattan",
            help="Files starting with these prefixes will be included"
        )
        
        # Suffixes input
        st.markdown("**File Extensions:**")
        suffixes_input = st.text_area(
            "Enter extensions (one per line)",
            value="\n".join(st.session_state.report_suffixes),
            height=80,
            placeholder=".html\n.png\n.pdf\n.jpg",
            help="Files with these extensions will be included"
        )
        
        # Filter words input (NEW)
        st.markdown("**Filter Words** (optional):")
        filter_words_input = st.text_area(
            "Enter filter words (one per line)",
            value="\n".join(st.session_state.report_filter_words),
            height=70,
            placeholder="RA\nCD\nhla",
            help="ALL these words must be present in filename (AND condition)"
        )
        
        # Update session state
        st.session_state.report_prefixes = [p.strip() for p in prefixes_input.split('\n') if p.strip()]
        st.session_state.report_suffixes = [s.strip() for s in suffixes_input.split('\n') if s.strip()]
        st.session_state.report_filter_words = [w.strip() for w in filter_words_input.split('\n') if w.strip()]
        
        # Show current filter logic
        st.markdown("**🔍 Filter Logic:**")
        if st.session_state.report_prefixes or st.session_state.report_suffixes:
            prefix_text = ", ".join(st.session_state.report_prefixes) if st.session_state.report_prefixes else "None"
            suffix_text = ", ".join(st.session_state.report_suffixes) if st.session_state.report_suffixes else "None"
            filter_text = ", ".join(st.session_state.report_filter_words) if st.session_state.report_filter_words else "None"
            
            st.info(f"**Logic**: (Prefixes: {prefix_text} OR Extensions: {suffix_text}) AND Filter Words: {filter_text}")
        else:
            st.warning("⚠️ Please set at least one prefix or extension")
        
        # Step 2: Scan button
        st.subheader("* Step 2: Scan Files")
        
        if st.button("🔍 Scan data/output Folder", type="primary"):
            if not st.session_state.report_prefixes and not st.session_state.report_suffixes:
                st.error("⚠️ Please set at least one prefix or extension before scanning!")
            else:
                with st.spinner("Scanning files..."):
                    found_files = scan_output_folder(
                        st.session_state.report_prefixes, 
                        st.session_state.report_suffixes,
                        st.session_state.report_filter_words
                    )
                    st.session_state.found_files = found_files
                    st.session_state.selected_file = None
                
                st.success(f"Found {len(found_files)} files!")
                st.rerun()
        
        # Step 3: File selection
        if st.session_state.found_files:
            st.subheader("* Step 3: Select File")
            
            # Group files by folder
            files_by_folder = {}
            for file_info in st.session_state.found_files:
                folder = file_info["parent_folder"]
                if folder not in files_by_folder:
                    files_by_folder[folder] = []
                files_by_folder[folder].append(file_info)
            
            # Create selection options with proper mapping
            selection_options = ["Select a file..."]  # Add placeholder
            file_mapping = {}  # Map selectbox indices to actual file indices
            
            option_index = 1  # Start after placeholder
            for folder, files in files_by_folder.items():
                for file_info in files:
                    size_str = format_file_size(file_info["size"])
                    display_text = f"{folder}/ → {file_info['name']} ({size_str})"
                    selection_options.append(display_text)
                    
                    # Find the actual index in found_files
                    actual_index = next(
                        i for i, f in enumerate(st.session_state.found_files) 
                        if f["path"] == file_info["path"]
                    )
                    file_mapping[option_index] = actual_index
                    option_index += 1
            
            selected_option_index = st.selectbox(
                "Choose a file to view:",
                range(len(selection_options)),
                format_func=lambda i: selection_options[i] if i < len(selection_options) else "",
                key="file_selector",
                index=0  # Start with placeholder
            )
            
            # Update selected file based on mapping
            if selected_option_index and selected_option_index > 0:  # Skip placeholder
                if selected_option_index in file_mapping:
                    actual_file_index = file_mapping[selected_option_index]
                    if actual_file_index < len(st.session_state.found_files):
                        new_selection = st.session_state.found_files[actual_file_index]
                        # Only update if it's a different file to avoid infinite reruns
                        if (not st.session_state.selected_file or 
                            st.session_state.selected_file["path"] != new_selection["path"]):
                            st.session_state.selected_file = new_selection
                            st.rerun()
        
        st.divider()
        
        # Current selection info
        if st.session_state.selected_file:
            st.subheader("* Current Selection")
            file_info = st.session_state.selected_file
            st.info(f"**File:** {file_info['name']}")
            st.info(f"**Folder:** {file_info['parent_folder']}")
            st.info(f"**Size:** {format_file_size(file_info['size'])}")
        
        # Statistics
        if st.session_state.found_files:
            st.divider()
            st.subheader("Statistics")
            
            total_files = len(st.session_state.found_files)
            folders = set(f["parent_folder"] for f in st.session_state.found_files)
            extensions = set(f["extension"] for f in st.session_state.found_files)
            
            st.metric("Total Files", total_files)
            st.metric("Folders", len(folders))
            st.metric("File Types", len(extensions))

def main():
    """Main Streamlit application for report viewer."""
    st.title("Report Viewer")
    st.markdown("**Beautiful viewer for HTML reports, plots, and images from HLAgent analysis results**")
    
    # Initialize session state
    initialize_report_session_state()
    
    # Create sidebar
    create_report_sidebar()
    
    # Main content area
    if not st.session_state.found_files:
        # Welcome screen
        st.info("Configure filters in the sidebar and click 'Scan' to find report files")
        
        st.markdown("""
        ### How to use Report Viewer:
        
        **Step 1: Configure Filters**
        - **Prefixes**: Files starting with these names (e.g., "heatmap", "manhattan")
        - **Extensions**: File types to include (e.g., .html, .png, .pdf)
        - **Filter Words**: ALL these words must be present in filename (AND condition)
        
        **Filter Logic**: (Prefixes OR Extensions) AND Filter Words
        - Example: filter words: "RA" → files containing "RA" AND (prefixes match "manhattan" OR extensions match ".html")
        
        **Step 2: Scan Files**
        - Click "Scan data/output Folder" to search for matching files
        - The scanner will recursively search all subdirectories
        
        **Step 3: Select and View**
        - Choose a file from the dropdown list
        - The file will be displayed beautifully in the main area
        - Switch between files easily using the dropdown
        
        ### Available Report Types:
        - ** Interactive HTML plots** (Plotly, matplotlib)
        - ** Image files** (PNG, JPG, JPEG)
        - ** PDF reports** (embedded viewer)
        - ** Analysis results** from all HLAgent tools
        """)
        
        # Show example folder structure
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Folder Structure")
            st.markdown("""
            ```
            data/output/
            - BMarkerRegression/
                - heatmap_A_heatmap.html
                - manhattan_plot.html
                - ...
            - MetaAnalysis/
                - forest_plot.png
                - funnel_plot.png
                - ...
            - HLAImputation/
                - results_summary.html
                - ...
            ```
            """)
        
        with col2:
            st.subheader("Example Filters")
            st.markdown("""
            **Common Prefixes:**
            - `heatmap` - for heatmap visualizations
            - `manhattan` - for Manhattan plots
            - `forest` - for forest plots
            - `results` - for result summaries
            
            **Common Extensions:**
            - `.html` - Interactive plots
            - `.png` - Static images
            - `.pdf` - PDF reports
            - `.jpg` - Image files
            """)
    
    elif not st.session_state.selected_file:
        # Files found but none selected
        st.info("**Select a file from the sidebar to view it**")
        
        # Show found files summary
        st.subheader(f"Found {len(st.session_state.found_files)} Files")
        
        # Group and display files by folder
        files_by_folder = {}
        for file_info in st.session_state.found_files:
            folder = file_info["parent_folder"]
            if folder not in files_by_folder:
                files_by_folder[folder] = []
            files_by_folder[folder].append(file_info)
        
        for folder, files in files_by_folder.items():
            with st.expander(f"{folder}/ ({len(files)} files)"):
                for file_info in files:
                    size_str = format_file_size(file_info["size"])
                    st.markdown(f"- **{file_info['name']}** ({size_str}) - {file_info['extension']}")
    
    else:
        # Display selected file
        file_info = st.session_state.selected_file
        
        # File header with info
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.subheader(f"{file_info['name']}")
        
        with col2:
            st.metric("Size", format_file_size(file_info['size']))
        
        with col3:
            # Download button
            with open(file_info['path'], 'rb') as f:
                st.download_button(
                    label="Download",
                    data=f.read(),
                    file_name=file_info['name'],
                    mime='application/octet-stream'
                )
        
        # File path and folder info
        st.markdown(f"**Location:** `{file_info['relative_path']}`")
        st.markdown(f"**Source Folder:** `{file_info['parent_folder']}/`")
        
        # Folder description
        folder_desc = get_folder_description(file_info['parent_folder'])
        st.info(f"**About this folder:** {folder_desc}")
        
        st.divider()
        
        # Display file content based on extension
        extension = file_info['extension'].lower()
        
        if extension == '.html':
            st.subheader("HTML Content")
            display_html_file(file_info['path'])
            
        elif extension in ['.png', '.jpg', '.jpeg']:
            st.subheader("Image Content")
            display_image_file(file_info['path'])
            
        elif extension == '.pdf':
            st.subheader("PDF Content")
            display_pdf_file(file_info['path'])
            
        else:
            st.warning(f"Preview not available for {extension} files. You can download the file using the button above.")
            
            # Try to display as text if it's small enough
            try:
                if file_info['size'] < 1024 * 1024:  # Less than 1MB
                    with open(file_info['path'], 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    st.subheader("Text Content Preview")
                    st.code(content, language='text')
                else:
                    st.info("File is too large for text preview.")
            except:
                st.info("Cannot preview this file type as text.")

if __name__ == "__main__":
    main()