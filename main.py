"""
STPTrackTool - Main Flask Application
Entry point for the satellite tracking tool web application.
"""

from flask import Flask, render_template, request, redirect, url_for, flash
import os
from xml_analysis import handle_xml_analysis, download_txt
from plan_merge import handle_plan_merge, download_merged
from plan_analysis import handle_plan_analysis, download_updated_plan

# Create Flask app instance
app = Flask("STPTrackTool")
app.secret_key = os.urandom(24)

@app.route('/', methods=['GET', 'POST'])
def index():
    """Main route handler that delegates to appropriate page handlers."""
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'xml_analysis':
            return handle_xml_analysis(request)
        elif form_type == 'plan_merge':
            return handle_plan_merge(request)
        elif form_type == 'plan_analysis':
            return handle_plan_analysis(request)
    
    return render_template('index.html')

@app.route('/download_txt')
def download_txt_file():
    """Download generated TXT file from XML analysis."""
    return download_txt()

@app.route('/download_merged')
def download_merged_file():
    """Download merged plan file."""
    return download_merged()


@app.route('/download_updated_plan')
def download_updated_plan_file():
    """Download updated plan file with new dates."""
    return download_updated_plan()


if __name__ == '__main__':
    app.run(debug=True)