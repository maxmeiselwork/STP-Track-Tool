"""
Plan Analysis Module
Handles analysis and visualization of full satellite tracking plans.
"""

from flask import render_template, request, flash, redirect, url_for
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

def analyze_plan_txt_file(file_obj):
    """Analyze a plan TXT file and extract track data."""
    try:
        # Read the file content
        try:
            file_content = file_obj.read().decode('utf-8')
        except UnicodeDecodeError:
            file_obj.seek(0)
            file_content = file_obj.read().decode('utf-8', errors='ignore')
        
        # Split into lines and strip whitespace and check file length
        lines = [line.strip() for line in file_content.splitlines() if line.strip()]
        if len(lines) < 3:
            raise ValueError("File too short - needs at least 3 lines (epoch, deploy time, and one gateway)")
        
        # Find the first gateway line
        gateway_start = None
        for i, line in enumerate(lines):
            if line.startswith('GS_'):
                gateway_start = i
                break
        
        if gateway_start is None:
            raise ValueError("No gateway entries found (lines starting with 'GS_')")
        
        # Process tracks by gateway first
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
                    start_str = parts[3].split('.')[0]  
                    end_str = parts[4].split('.')[0]
                    
                    start_time = datetime.strptime(start_str, "%Y%m%d%H%M%S")
                    end_time = datetime.strptime(end_str, "%Y%m%d%H%M%S")
                    duration = (end_time - start_time).total_seconds() / 60.0
                    
                    # Check duration flags
                    flags = [] 
                    if duration < 24:
                        flags.append("SHORT")
                    elif duration > 45:
                        flags.append("LONG")
                    
                    flag = ", ".join(flags) if flags else "OK"
                    
                    gateway_data[current_gateway].append([current_gateway, parts[0], start_time, end_time, duration, flag])
                except ValueError as e:
                    print(f"Skipping line due to error: {line}\nError: {str(e)}")
                    continue
        
        # Check for overlaps within each gateway
        all_data = []
        for gateway, tracks in gateway_data.items():
            if not tracks:
                continue
                
            tracks.sort(key=lambda x: x[2])  

            # Check for overlaps within this gateway
            for i in range(len(tracks)):
                current_start = tracks[i][2]
                current_end = tracks[i][3]
                
                overlaps_prev = True
                overlaps_next = True
                
                # Check overlap with previous satellite in this gateway
                if i > 0:
                    prev_end = tracks[i - 1][3]
                    overlaps_prev = current_start <= prev_end
                
                # Check overlap with next satellite in this gateway
                if i < len(tracks) - 1:
                    next_start = tracks[i + 1][2]
                    overlaps_next = current_end >= next_start
                
                # Add NO OVERLAP flag if needed
                if (not overlaps_prev or not overlaps_next):
                    current_flags = tracks[i][5].split(", ") if tracks[i][5] != "OK" else []
                    if "NO OVERLAP" not in current_flags:
                        current_flags.append("NO OVERLAP")
                    tracks[i][5] = ", ".join(current_flags) if current_flags else "OK"
            
            all_data.extend(tracks)
        
        if not all_data:
            raise ValueError("No valid track entries found in file")
            
        # Create DataFrame and sort chronologically for display
        base_df = pd.DataFrame(all_data, columns=["Gateway", "Satellite", "Start", "End", "Duration", "Flag"])
        base_df = base_df.sort_values(['Start']).reset_index(drop=True)
        
        return base_df
        
    except Exception as e:
        raise ValueError(f"Error processing file: {str(e)}")

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
        
        try:
            df = analyze_plan_txt_file(full_plan_file.stream)
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
        
        # Generate the Gantt chart
        tabs = generate_gantt_multi_gateway(df)
        
        return render_template('plan_analysis.html', table=styled_table_html, stats=stats, tabs=tabs)

    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('index'))
    except Exception as e:
        flash(f"Error processing plan analysis file: {str(e)}", "error")
        return redirect(url_for('index'))