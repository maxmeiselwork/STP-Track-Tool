# STP Track Tool

The **STP Track Tool** is a web-based application designed to analyze, merge, and visualize satellite tracking plans. It provides functionality for XML schedule analysis, full plan analysis, and merging of satellite tracking plans. The tool is built using Python and Flask, with additional support for data visualization using Plotly.

---

## Features

1. **XML Schedule Analysis**:
   - Upload an XML file to analyze satellite tracks.
   - Visualize satellite coverage in a Gantt chart.
   - Generate a `.txt` file with the expanded schedule.

2. **Plan Merging**:
   - Merge a new gateway schedule with an existing full schedule.
   - Automatically update dates and times in the merged plan.
   - Preview the merged plan and download it as a `.txt` file.

3. **Full Plan Analysis**:
   - Analyze a complete satellite tracking plan.
   - Optionally update deploy dates and times.
   - Visualize schedules and identify flagged tracks (e.g., short, long, or no overlap).

---

## Folder Structure
    ├── main.py # Entry point for the Flask application 
    ├── plan_analysis.py # Handles full plan analysis 
    ├── plan_merge.py # Handles merging of satellite tracking plans 
    ├── xml_analysis.py # Handles XML schedule analysis 
    ├── templates/ # HTML templates for the web interface 
    │ ├── index.html # Main page template 
    │ ├── plan_analysis.html # Template for full plan analysis results 
    │ ├── plan_merge.html # Template for merged plan results 
    │ ├── xml_analysis.html # Template for XML analysis results 
    ├── static/ # Static files (CSS and JavaScript) 
    │ ├── css/ 
    │ │ ├── dark_mode.css # Dark mode styles 
    │ │ ├── style.css # Additional custom styles 
    │ ├── js/ 
    │ │ ├── download_buttons.js # Handles download button interactions 
    │ │ ├── table_filters.js # Handles table filtering functionality 
    └── pycache/ # Compiled Python files (auto-generated)


---

## How to Launch the Application

### Prerequisites

1. **Python 3.7 or higher**: Ensure Python is installed on your system.
2. **Pip**: Ensure `pip` is installed to manage Python packages.
3. **Virtual Environment (Optional)**: It's recommended to use a virtual environment to isolate dependencies.

### Installation Steps

1. Clone the repository or download the source code.
2. Navigate to the project directory:
   ```bash
   cd path/to/project:
3. Install the required dependencies:
    ```bash
    pip install flask pandas plotly
4. Run the application:
    ```bash
    python main.py
5. Open your browser and navigate to:
    ```bash
    http://127.0.0.1:5000/

## Usage Instructions
1. **XML Schedule Analysis**:
    - Upload an XML file, specify the gateway name, deploy date, and deploy time. 
    - Analyze the schedule and visualize the satellite coverage.
    - Download the expanded schedule as a .txt file.
2. **Plan Merging**:
    - Upload the old complete schedule and the new gateway schedule.
    - Merge the plans and preview the result.
    - Download the merged plan as a .txt file.
3. **Full Plan Analysis**:
    - Upload a complete schedule file.
    - Optionally specify a new deploy date and time to update the schedule.
    - Analyze the schedule, visualize it, and identify flagged tracks.

## Notes
1. The application uses Bootstrap for styling and Plotly for data visualization.
2. All uploaded files must adhere to the expected formats (.xml for XML analysis and .txt for plan files).
3. The application runs in debug mode by default. For production, disable debug mode and use a production-ready server like Gunicorn.