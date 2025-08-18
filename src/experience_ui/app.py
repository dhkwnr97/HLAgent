"""
HLAgent Multi-Page Streamlit Application.
Main entry point that organizes different UI functionalities into separate pages.
"""

import streamlit as st
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add the project root to Python path
project_root = os.getenv("HLAGENT_MAIN_DIRECTORY")
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure Streamlit page
st.set_page_config(
    page_title="HLAgent Multi-Page App",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

def main():
    """Main application with page navigation."""
    
    # Main title
    st.title("🤖 HLAgent Multi-Agent System")
    st.markdown("**HLAgent: Crew of HLA Specialist Agents**")
    
    # Navigation info
    st.markdown("""
    ### 📑 Available Pages:
    
    - **🤖 p.1_Chatting**: Multi-agent chatting with Supervisor and specialized agents
    - **⚙️ p.2_ParameterChat**: Interactive YAML parameter modification (Web UI instead of console)
    - **📊 p.3_ReportViewer**: Beautiful viewer for HTML reports, plots, and images
    
    **👈 Use the sidebar to navigate between pages**
    """)
    
    # Page descriptions
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🤖 Multi-Agent Chatting")
        st.markdown("""
        **Features:**
        - Chat with Supervisor agent
        - Automatic delegation to specialist agents
        - HLA Teacher, File Converter, Parameter Handler, etc.
        - Streaming responses for HLA Teacher
        - Session management and handover tracking
        """)
    
    with col2:
        st.subheader("⚙️ Parameter Handler Chat")
        st.markdown("""
        **Features:**
        - Interactive YAML parameter modification
        - Web UI instead of console chatting
        - Natural language parameter changes
        - "Done!" → "Are you sure?" → "Yes" workflow
        - Real-time file content display
        """)
    
    with col3:
        st.subheader("📊 Report Viewer")
        st.markdown("""
        **Features:**
        - Beautiful HTML report viewer
        - Interactive Plotly plots display
        - Image and PDF file viewer
        - Recursive folder scanning
        - File filtering by prefix/suffix
        - Folder-based descriptions
        """)
    
    st.divider()
    
    # System information
    st.subheader("ℹ️ System Information")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Project Structure:**
        - `src/experience_ui/app.py` - Main multipage app
        - `src/experience_ui/pages/p.1_Chatting.py` - Multi-agent chat
        - `src/experience_ui/pages/p.2_ParameterChat.py` - Parameter handler UI
        - `src/experience_ui/pages/p.3_ReportViewer.py` - Report viewer UI
        """)
    
    with col2:
        st.markdown(f"""
        **Environment:**
        - Project Root: `{project_root}`
        - Python Path: Added to sys.path
        - Environment Variables: Loaded from .env
        """)
    
    # Quick start guide
    st.divider()
    st.subheader("🚀 Quick Start Guide")
    
    tab1, tab2, tab3 = st.tabs(["Multi-Agent Chat", "Parameter Chat", "Report Viewer"])
    
    with tab1:
        st.markdown("""
        ### How to use Multi-Agent Chatting:
        
        1. **Navigate** to **p.1_Chatting** page using the sidebar
        2. **Chat** with the Supervisor agent
        3. **Automatic delegation** - Supervisor routes queries to appropriate agents
        4. **Specialized agents** handle specific tasks (HLA, file conversion, etc.)
        5. **Type "Done!"** to return control to Supervisor from any specialist
        
        **Example queries:**
        - "I want to see HLA teacher agent" → Delegates to HLA Teacher
        - "Let's do HLA fine mapping analysis" → Delegates to HLA Fine Mapping
        - "I want to do file converting" → Delegates to File Converter
        """)
    
    with tab2:
        st.markdown("""
        ### How to use Parameter Handler Chat:
        
        1. **Navigate** to **p.2_ParameterChat** page using the sidebar  
        2. **Enter YAML file path** in the sidebar (e.g., `data/configs/example_orig.yaml`)
        3. **Click "Start Parameter Session"** to initialize
        4. **Chat** with Parameter Handler to modify parameters:
           - "Change line 19 to 18"
           - "Set line 47 to ['A', 'B', 'C']"
        5. **Type "Done!"** when finished
        6. **Confirm with "Yes"** to complete the session
        
        **Key Benefits:**
        - **No more console chatting** - Everything in web UI
        - **Natural language** parameter modifications
        - **Visual feedback** with file content display
        - **Safe workflow** with confirmation step
        """)
    
    with tab3:
        st.markdown("""
        ### How to use Report Viewer:
        
        1. **Navigate** to **p.3_ReportViewer** page using the sidebar
        2. **Configure filters** in the sidebar:
           - **Prefixes**: File name prefixes (e.g., "heatmap", "manhattan")  
           - **Extensions**: File types (e.g., .html, .png, .pdf)
        3. **Click "Scan data/output Folder"** to find matching files
        4. **Select a file** from the dropdown list to view it
        5. **Switch between files** easily using the dropdown
        
        **Supported File Types:**
        - **📊 Interactive HTML plots** (Plotly, matplotlib) 
        - **🖼️ Image files** (PNG, JPG, JPEG)
        - **📄 PDF reports** (embedded viewer)
        
        **Key Benefits:**
        - **Beautiful display** of analysis results
        - **Recursive scanning** of all subdirectories
        - **Smart filtering** by prefixes and extensions
        - **Folder descriptions** explaining each analysis type
        - **File download** capability
        """)

if __name__ == "__main__":
    main()