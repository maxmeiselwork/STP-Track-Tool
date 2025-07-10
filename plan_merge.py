#!/usr/bin/env python3
"""
Plan Merge Module
Handles merging of satellite tracking plans.
"""

from flask import render_template, request, send_file, flash, redirect, url_for
from datetime import datetime, timedelta
from io import BytesIO

# Global memory buffer for merged plan
stored_merged_plan = BytesIO()
download_used = {'merged': False}

def parse_plan_for_merge(file_content):
    """Parse plan file and extract gateway data."""
    try:
        lines = file_content.strip().split('\n')
        
        if len(lines) < 3:
            raise ValueError("Invalid plan file format - insufficient lines")
        
        # Process tracks by gateway
        gateways = {}
        current_gateway = None
        
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue
                
            # Check if this is a gateway line
            if line.startswith('GS_'):
                current_gateway = line
                gateways[current_gateway] = []
            else:
                # This is a track line
                if current_gateway:
                    gateways[current_gateway].append(line)
        
        return gateways
    except Exception as e:
        raise ValueError(f"Error parsing plan file: {str(e)}")

def update_track_dates(track_lines, new_date_str):
    """Update dates in track lines with next day handling."""
    new_date = datetime.strptime(new_date_str, "%Y%m%d")
    next_day = new_date + timedelta(days=1)
    next_day_str = next_day.strftime("%Y%m%d")
    
    updated_lines = []
    for line in track_lines:
        parts = line.split()
        if len(parts) >= 5:
            # Parse original times to check if they cross midnight
            start_time = parts[3]  
            end_time = parts[4]
            
            # Extract original date and time components
            orig_start_date = start_time[:8]
            orig_end_date = end_time[:8]
            start_time_part = start_time[8:] 
            end_time_part = end_time[8:]
            
            # Check if end time is on a different day than start time
            if orig_end_date != orig_start_date:
                # End time is on next day - use next_day_str for end time
                new_start = new_date_str + start_time_part
                new_end = next_day_str + end_time_part
            else:
                # Both times are on same day - use new_date_str for both
                new_start = new_date_str + start_time_part
                new_end = new_date_str + end_time_part
            
            # Reconstruct the line
            parts[3] = new_start
            parts[4] = new_end
            updated_lines.append(' '.join(parts))
        else:
            updated_lines.append(line)
    
    return updated_lines

def merge_plans(old_plan_content, new_gateway_content):
    """Merge old plan with new gateway data."""
    global stored_merged_plan, download_used
    
    try:
        # Parse the new gateway file
        new_lines = new_gateway_content.strip().split('\n')
        if len(new_lines) < 3:
            raise ValueError("Invalid new gateway file format")
            
        new_epoch = new_lines[0]
        new_now_time = new_lines[1]
        new_gateway_name = new_lines[2]
        new_tracks = new_lines[3:]
        
        # Extract date from new gateway's now time
        new_date_str = new_now_time[:8]  # YYYYMMDD
        
        # Parse the old plan
        old_gateways = parse_plan_for_merge(old_plan_content)
        
        # Update all gateway dates to match the new date and replace matching gateway
        updated_gateways = {}
        gateway_updated = False
        for gateway_name, tracks in old_gateways.items():
            if gateway_name == new_gateway_name:
                # REPLACE with new gateway data
                updated_gateways[gateway_name] = new_tracks
                gateway_updated = True
            else:
                # Update dates but keep existing tracks
                updated_gateways[gateway_name] = update_track_dates(tracks, new_date_str)
        
        # Generate the merged plan with proper ordering
        merged_content = f"{new_epoch}\n{new_now_time}\n"
        
        # Use the original gateway order from old plan
        for gateway_name in old_gateways.keys():
            merged_content += f"{gateway_name}\n"
            for track in updated_gateways[gateway_name]:
                merged_content += f"{track}\n"
        
        # If the new gateway was not in the old plan, add it at the end
        if not gateway_updated:
            merged_content += f"{new_gateway_name}\n"
            for track in new_tracks:
                merged_content += f"{track}\n"
        
        # Store in memory buffer
        stored_merged_plan = BytesIO()
        stored_merged_plan.write(merged_content.encode("utf-8"))
        stored_merged_plan.seek(0)
        download_used['merged'] = False
        
        return merged_content
    except Exception as e:
        raise ValueError(f"Error merging plans: {str(e)}")

def handle_plan_merge(request):
    """Handle plan merge form submission."""
    try:
        old_plan_file = request.files['old_plan']
        new_gateway_file = request.files['new_gateway']
        
        if not old_plan_file or not new_gateway_file:
            flash("Missing old plan file or new gateway file", "error")
            return redirect(url_for('index'))
        
        # Check file extensions
        if not old_plan_file.filename.lower().endswith('.txt'):
            flash("Wrong file type for old plan. Please upload a TXT file.", "error")
            return redirect(url_for('index'))
            
        if not new_gateway_file.filename.lower().endswith('.txt'):
            flash("Wrong file type for new gateway. Please upload a TXT file.", "error")
            return redirect(url_for('index'))
        
        old_plan_content = old_plan_file.read().decode('utf-8')
        new_gateway_content = new_gateway_file.read().decode('utf-8')
        
        merged_content = merge_plans(old_plan_content, new_gateway_content)
        
        # Display success message and preview
        preview_lines = merged_content.split('\n')[:50]  # Show first 50 lines
        preview = '\n'.join(preview_lines)
        if len(merged_content.split('\n')) > 50:
            preview += '\n... (truncated)'
        
        return render_template('plan_merge.html', preview=preview)
        
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('index'))
    except Exception as e:
        flash("Error with file", "error")
        return redirect(url_for('index'))

def download_merged():
    """Download merged plan file."""
    global stored_merged_plan, download_used
    if download_used['merged']:
        flash("File already downloaded", "error")
        return redirect(url_for('index'))
    
    stored_merged_plan.seek(0)
    download_used['merged'] = True
    return send_file(stored_merged_plan, mimetype='text/plain', as_attachment=True, download_name='merged_plan.txt')