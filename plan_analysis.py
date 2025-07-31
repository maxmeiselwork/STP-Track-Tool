"""
Plan Analysis Module
Handles analysis and visualization of full satellite tracking plans.
"""

from flask import render_template, request, flash, redirect, url_for, send_file
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from io import BytesIO

# Global memory buffer for updated plan download
stored_updated_plan = BytesIO()
download_used = {'plan': False}

# --- [Function: update_plan_dates_new] ---
def update_plan_dates_new(file_content, new_deploy_date, new_deploy_time):
    """Update plan dates similar to XML analysis - preserve times, update dates."""
    lines = file_content.strip().split('\n')
    if len(lines) < 3:
        raise ValueError("Invalid plan file format")

    # Parse deploy datetime
    new_deploy_datetime = datetime.combine(new_deploy_date.date(), new_deploy_time.time())
    new_deploy_str = new_deploy_datetime.strftime("%Y%m%d%H%M%S.000")
    
    # Find gateway section and collect all tracks
    gateway_start = next((i for i, line in enumerate(lines) if line.startswith('GS_')), None)
    if gateway_start is None:
        raise ValueError("No gateway lines found")
    
    tracks = []
    current_gateway = None
    
    for line in lines[gateway_start:]:
        line = line.strip()
        if line.startswith('GS_'):
            current_gateway = line
            continue
        
        parts = line.split()
        if len(parts) >= 5 and parts[1] == 'DAT' and parts[2] == 'RECUR':
            try:
                original_start = datetime.strptime(parts[3].split('.')[0], "%Y%m%d%H%M%S")
                original_end = datetime.strptime(parts[4].split('.')[0], "%Y%m%d%H%M%S")
                
                # Extract time components
                start_time = original_start.time()
                end_time = original_end.time()
                
                # Create new datetime with deploy date but original times
                new_start = datetime.combine(new_deploy_date.date(), start_time)
                
                # Handle end time - if end time is earlier than start time, it's next day
                if end_time < start_time:
                    new_end = datetime.combine(new_deploy_date.date() + timedelta(days=1), end_time)
                else:
                    new_end = datetime.combine(new_deploy_date.date(), end_time)
                
                tracks.append({
                    'gateway': current_gateway,
                    'satellite': parts[0],
                    'data': parts[1],
                    'recur': parts[2],
                    'start': new_start,
                    'end': new_end,
                    'original_line': line
                })
            except Exception:
                # Keep non-track lines as is
                tracks.append({
                    'gateway': current_gateway,
                    'original_line': line,
                    'is_track': False
                })
    
    if not any(t.get('start') for t in tracks):
        raise ValueError("No valid tracks found for date update")
    
    # Find first track time for new epoch
    first_track_time = min(t['start'] for t in tracks if t.get('start'))
    new_epoch_millis = int(first_track_time.timestamp() * 1000)
    
    # Build updated content
    updated_lines = [str(new_epoch_millis), new_deploy_str]
    
    current_gateway = None
    for track in tracks:
        if track['gateway'] != current_gateway:
            current_gateway = track['gateway']
            updated_lines.append(current_gateway)
        
        if track.get('start'):  # It's a track line
            start_str = track['start'].strftime("%Y%m%d%H%M%S.000")
            end_str = track['end'].strftime("%Y%m%d%H%M%S.000")
            updated_lines.append(f"{track['satellite']} {track['data']} {track['recur']} {start_str} {end_str}")
        else:  # Non-track line
            updated_lines.append(track['original_line'])
    
    return '\n'.join(updated_lines)

# --- [Function: analyze_plan_txt_file] ---
def analyze_plan_txt_file(file_obj, new_deploy_date=None, new_deploy_time=None):
    try:
        file_obj.seek(0)
        try:
            content = file_obj.read().decode('utf-8')
        except UnicodeDecodeError:
            file_obj.seek(0)
            content = file_obj.read().decode('utf-8', errors='ignore')

        dates_updated = False
        if new_deploy_date and new_deploy_time:
            try:
                content = update_plan_dates_new(content, new_deploy_date, new_deploy_time)
                global stored_updated_plan, download_used
                stored_updated_plan = BytesIO()
                stored_updated_plan.write(content.encode("utf-8"))
                stored_updated_plan.seek(0)
                download_used['plan'] = False
                dates_updated = True
            except Exception as e:
                raise ValueError(f"Date update failed: {str(e)}")

        lines = [l.strip() for l in content.splitlines() if l.strip()]
        if len(lines) < 3:
            raise ValueError("File too short")

        gateway_start = next((i for i, line in enumerate(lines) if line.startswith('GS_')), None)
        if gateway_start is None:
            raise ValueError("No gateway lines found")

        gateway_data = {}
        current_gateway = None
        for line in lines[gateway_start:]:
            if line.startswith('GS_'):
                current_gateway = line
                gateway_data[current_gateway] = []
                continue
            parts = line.split()
            if len(parts) >= 5 and parts[1] == 'DAT' and parts[2] == 'RECUR':
                try:
                    start = datetime.strptime(parts[3].split('.')[0], "%Y%m%d%H%M%S")
                    end = datetime.strptime(parts[4].split('.')[0], "%Y%m%d%H%M%S")
                    duration = (end - start).total_seconds() / 60.0
                    if duration < 0:
                        duration += 1440
                    flags = []
                    if duration < 24: flags.append("SHORT")
                    if duration > 45: flags.append("LONG")
                    gateway_data[current_gateway].append([current_gateway, parts[0], start, end, duration, ", ".join(flags) or "OK"])
                except: continue

        all_data = []
        for gateway, tracks in gateway_data.items():
            tracks.sort(key=lambda x: x[2])
            for i in range(len(tracks)):
                overlaps_prev = i == 0 or tracks[i][2] <= tracks[i-1][3]
                overlaps_next = i == len(tracks)-1 or tracks[i][3] >= tracks[i+1][2]
                if not (overlaps_prev and overlaps_next):
                    flags = tracks[i][5].split(', ') if tracks[i][5] != "OK" else []
                    if "NO OVERLAP" not in flags:
                        flags.append("NO OVERLAP")
                        tracks[i][5] = ", ".join(sorted(set(flags)))
            all_data.extend(tracks)

        if not all_data:
            raise ValueError("No valid tracks found")

        df = pd.DataFrame(all_data, columns=["Gateway", "Satellite", "Start", "End", "Duration", "Flag"])
        return df.sort_values("Start").reset_index(drop=True), dates_updated
    except Exception as e:
        raise ValueError(f"Error processing plan: {str(e)}")

def generate_gantt_multi_gateway(df):
    gateways = df['Gateway'].unique()
    
    # Create separate figures for each gateway
    gateway_figures = {}
    
    flag_colors = {
        'OK': '#2ca02c',      # Green
        'SHORT': '#ff7f0e',   # Orange  
        'LONG': '#1f77b4',    # Blue
        'NO OVERLAP': '#d62728'  # Red
    }

    for gateway in gateways:
        gateway_df = df[df['Gateway'] == gateway].copy()
        unique_satellites = gateway_df['Satellite'].unique()
        
        fig = go.Figure()
        legend_added = set()
        
        satellite_to_y = {sat: i for i, sat in enumerate(unique_satellites)}
        
        # Find the maximum end time for this gateway to set x-axis range
        max_end_time = 0
        for _, entry in gateway_df.iterrows():
            end_hour = entry['End'].hour + entry['End'].minute/60 + entry['End'].second/3600
            start_hour = entry['Start'].hour + entry['Start'].minute/60 + entry['Start'].second/3600
            if end_hour < start_hour:
                end_hour += 24
            max_end_time = max(max_end_time, end_hour)
        
        for _, entry in gateway_df.iterrows():
            satellite = entry['Satellite']
            flags = entry['Flag'].split(', ') if entry['Flag'] != 'OK' else ['OK']
            
            # Determine color and pattern based on flags
            if len(flags) == 1 and flags[0] == 'OK':
                color = flag_colors['OK']
                pattern = None
                legend_name = 'OK'
            elif len(flags) == 1:
                color = flag_colors.get(flags[0], '#gray')
                pattern = None
                legend_name = flags[0]
            else:
                # Multiple flags - create alternating stripes
                primary_flag = [f for f in flags if f != 'OK'][0] if any(f != 'OK' for f in flags) else flags[0]
                secondary_flag = [f for f in flags if f != 'OK' and f != primary_flag]
                secondary_flag = secondary_flag[0] if secondary_flag else 'OK'
                
                color = flag_colors.get(primary_flag, '#gray')
                legend_name = f"{primary_flag} + {secondary_flag}"
            
            # Convert times to hour format for proper x-axis alignment
            start_hour = entry['Start'].hour + entry['Start'].minute/60 + entry['Start'].second/3600
            end_hour = entry['End'].hour + entry['End'].minute/60 + entry['End'].second/3600
            
            # Handle case where end time is next day
            if end_hour < start_hour:
                end_hour += 24
            
            # Use the fixed y-position for this satellite
            y_position = satellite_to_y[satellite]
            
            # Add rectangle shape for the time bar
            fig.add_shape(
                type="rect",
                x0=start_hour,
                y0=y_position - 0.4,  
                x1=end_hour,
                y1=y_position + 0.4,
                fillcolor=color,
                line=dict(color='black', width=1),
                layer="above"  
            )
            
            # Add invisible scatter trace for hover and legend
            showlegend = legend_name not in legend_added
            if showlegend:
                legend_added.add(legend_name)
            
            fig.add_trace(go.Scatter(
                x=[start_hour + (end_hour - start_hour)/2], 
                y=[y_position],
                mode='markers',
                marker=dict(
                    color=color,
                    size=10,
                    opacity=0  
                ),
                name=legend_name,
                hovertemplate=(
                    f"<b>{satellite}</b><br>" +
                    f"Start: {entry['Start'].strftime('%H:%M:%S')}<br>" +
                    f"End: {entry['End'].strftime('%H:%M:%S')}<br>" +
                    f"Duration: {entry['Duration']:.1f} min<br>" +
                    f"Flags: {entry['Flag']}<br>" +
                    "<extra></extra>"
                ),
                showlegend=showlegend
            ))
        
        # Update layout for this gateway's figure
        fig.update_layout(
            title=f"Satellite Coverage Timeline - {gateway}",
            xaxis_title="Time (Hours)",
            yaxis_title="Satellites",
            height=max(500, len(unique_satellites) * 60),  
            width=1200,  
            margin=dict(t=60, l=120, r=150, b=60), 
            yaxis=dict(
                tickmode='array',
                tickvals=list(range(len(unique_satellites))),
                ticktext=unique_satellites,
                type='linear',
                range=[-0.5, len(unique_satellites) - 0.5],
                automargin=True,
                showgrid=False,  
                showline=False,  
                zeroline=False  
            ),
            xaxis=dict(
                range=[0, max_end_time * 1.02],  
                tickmode='linear',
                tick0=0,
                dtick=1,
                tickformat='%H:%M', 
                title="Time (24-hour format)",
                showgrid=True,  
                gridcolor='white',  
                gridwidth=1,
                showline=False,  
                zeroline=False  
            ),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="Black",
                borderwidth=1
            ),
            plot_bgcolor='#f0f0f0'  
        )
        
        gateway_figures[gateway] = fig
    
    # Create tabs structure
    tabs = []
    for gateway, fig in gateway_figures.items():
        tab_content = fig.to_html(full_html=False, div_id=f"chart_{gateway.replace(' ', '_')}")
        tabs.append({
            'label': gateway,
            'content': tab_content  
        })
    
    return tabs

def handle_plan_analysis(request):
    """Handle plan analysis form submission."""
    try:
        full_plan_file = request.files.get('full_plan')
        
        if not full_plan_file or full_plan_file.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('index'))
        
        # Check file extension
        if not full_plan_file.filename.lower().endswith('.txt'):
            flash("Please upload a .txt file", "error")
            return redirect(url_for('index'))
        
        # Get optional deploy date/time
        deploy_date_str = request.form.get('Deploy_Date', '').strip()
        deploy_time_str = request.form.get('Deploy_Time', '').strip()
        
        new_deploy_date = None
        new_deploy_time = None
        
        if deploy_date_str and deploy_time_str:
            try:
                new_deploy_date = datetime.strptime(deploy_date_str, "%Y%m%d")
                new_deploy_time = datetime.strptime(deploy_time_str, "%H:%M:%S")
            except ValueError:
                flash("Invalid deploy date or time format", "error")
                return redirect(url_for('index'))
        elif deploy_date_str or deploy_time_str:
            flash("Both deploy date and time must be provided if updating dates", "error")
            return redirect(url_for('index'))
        
        try:
            df, dates_updated = analyze_plan_txt_file(full_plan_file.stream, new_deploy_date, new_deploy_time)
            df_reset = df.reset_index(drop=True)

        except ValueError as e:
            flash(f"Error parsing file: {str(e)}", "error")
            return redirect(url_for('index'))
        
        if df.empty:
            flash("The file contains no valid track data", "error")
            return redirect(url_for('index'))

        def flag_color(v):
                    if 'SHORT' in v or 'LONG' in v or 'NO OVERLAP' in v:
                        return 'background-color: #f8d7da;'
                    return ''
        
        # Apply background styling to the Flag column 
        styled_table = df_reset.style \
            .set_table_attributes('class="table table-bordered table-sm table-hover"') \
            .hide(axis='index') \
            .applymap(flag_color, subset=['Flag'])

        styled_table_html = styled_table.to_html()

        # Create summary statistics
        first_start = df['Start'].min()
        last_start = df['Start'].max()
        time_span_hours = (last_start - first_start).total_seconds() / 3600

        # Count flags
        short_count = sum(1 for flag in df['Flag'] if 'SHORT' in flag)
        long_count = sum(1 for flag in df['Flag'] if 'LONG' in flag)
        no_overlap_count = sum(1 for flag in df['Flag'] if 'NO OVERLAP' in flag)
        flagged_count = sum(1 for flag in df['Flag'] if flag != 'OK')
        
        # Display stats
        stats = f"""
        <b>Summary:</b><br>
        Total tracks: {len(df)}<br>
        Time span (first to last start): {time_span_hours:.2f} hours<br>
        Short tracks (under 24 mins): {short_count}<br>
        Long tracks (over 45 mins): {long_count}<br>
        No Overlap (no satellite connected to the gateway): {no_overlap_count}<br>
        Tracks flagged: {flagged_count}<br>
        {"<span style='color: red;'>\u26a0 Schedule exceeds 24-hour period</span>" if time_span_hours > 24 else "\u2705 Schedule fits within a 24-hour period"}
        """
        
        # Add date update info if dates were updated
        if dates_updated:
            stats += f"<br><br><span style='color: green;'>\u2705 Dates updated to deploy date: {new_deploy_date.strftime('%Y-%m-%d')} at {new_deploy_time.strftime('%H:%M:%S')}</span>"
        
        # Generate the Gantt chart
        tabs = generate_gantt_multi_gateway(df)
        
        return render_template('plan_analysis.html', table=styled_table_html, stats=stats, tabs=tabs, dates_updated=dates_updated)

    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error processing plan analysis file: {str(e)}", "error")
        return redirect(url_for('index'))

def download_updated_plan():
    """Download updated plan file with new dates."""
    global stored_updated_plan, download_used
    if download_used['plan']:
        flash("File already downloaded", "error")
        return redirect(url_for('index'))
    
    stored_updated_plan.seek(0)
    download_used['plan'] = True
    return send_file(stored_updated_plan, mimetype='text/plain', as_attachment=True, download_name='updated_plan.txt')