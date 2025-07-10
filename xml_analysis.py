#!/usr/bin/env python3
"""
XML Analysis Module
Handles XML file processing, validation, and visualization.
"""

from flask import render_template, request, send_file, flash, redirect, url_for
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go
from io import BytesIO

# Global memory buffers for file downloads
stored_txt_file = BytesIO()
download_used = {'txt': False}

def parse_xml(file_stream, deploy_date):
    """Parse XML file and expand 6-hour schedule to 24-hour format."""
    try:
        tree = ET.parse(file_stream)
        root = tree.getroot()
        rows = []
        total_duration = 0

        # Parse original 6-hour track entries from XML
        for track in root.findall("Track"):
            satellite = track.attrib.get("Satellite", "").replace("O3B ", "")
            data_type = "DAT"
            recurrence = "RECUR"
            start_time = datetime.strptime(track.attrib.get("StartTime"), "%m/%d/%Y %H:%M:%S")
            end_time = datetime.strptime(track.attrib.get("EndTime"), "%m/%d/%Y %H:%M:%S")
            
            # Calculate duration in minutes
            duration = (end_time - start_time).total_seconds() / 60.0
            total_duration += duration
            
            # Check duration flags
            flags = []
            if duration < 24:
                flags.append("SHORT")
            elif duration > 45:
                flags.append("LONG")
            
            flag = ", ".join(flags) if flags else "OK"
            rows.append([satellite, data_type, recurrence, start_time, end_time, duration, flag])

        if not rows:
            raise ValueError("No valid Track elements found in XML")

        base_df = pd.DataFrame(rows, columns=["Satellite", "Data", "Reccurance", "Start", "End", "Duration", "Flag"])
        base_date = deploy_date.date()
        earliest_date = min(row["Start"].date() for _, row in base_df.iterrows())

        # Expand to 24 hours by repeating pattern 4 times
        if total_duration < 420:
            extended_rows = []
            for i in range(4):
                shift = timedelta(hours=i * 6)
                for index, row in base_df.iterrows():
                    time_of_day = row["Start"].time()
                    delta_days = (row["Start"].date() - earliest_date).days
                    shifted_start = datetime.combine(base_date + timedelta(days=delta_days), time_of_day) + shift
                    shifted_end = shifted_start + timedelta(minutes=row["Duration"])
                    new_row = row.copy()
                    new_row["Start"] = shifted_start
                    new_row["End"] = shifted_end
                    extended_rows.append((index + i * len(base_df), new_row))
        else:
            extended_rows = [(i, row) for i, row in enumerate(base_df.itertuples(index=False, name=None))]
        
        # Create and sort dataframe
        df = pd.DataFrame([r[1] for r in sorted(extended_rows, key=lambda x: x[0])], 
                          columns=["Satellite", "Data", "Reccurance", "Start", "End", "Duration", "Flag"])

        df['time_of_day'] = df['Start'].dt.time
        df['date'] = df['Start'].dt.date
        df = df.sort_values(['time_of_day', 'date']).reset_index(drop=True)
        
        # Adjust dates to same day
        df['Start'] = df.apply(lambda row: datetime.combine(base_date, row['time_of_day']), axis=1)
        df['End'] = df['Start'] + pd.to_timedelta(df['Duration'], unit='minutes')
        df = df.drop(['time_of_day', 'date'], axis=1)

        # Add overlap detection
        for i in range(len(df)):
            current_start = df.iloc[i]["Start"]
            current_end = df.iloc[i]["End"]
            
            overlaps_prev = True
            overlaps_next = True
            
            if i > 0:
                prev_end = df.iloc[i - 1]["End"]
                overlaps_prev = current_start <= prev_end
            
            if i < len(df) - 1:
                next_start = df.iloc[i + 1]["Start"]
                overlaps_next = current_end >= next_start
            
            if (not overlaps_prev or not overlaps_next):
                current_flags = df.iloc[i]["Flag"].split(", ") if df.iloc[i]["Flag"] != "OK" else []
                if "NO OVERLAP" not in current_flags:
                    current_flags.append("NO OVERLAP")
                df.at[i, "Flag"] = ", ".join(current_flags) if current_flags else "OK"

        return df
    except ET.ParseError:
        raise ValueError("Invalid XML file format")
    except Exception as e:
        raise ValueError(f"Error parsing XML: {str(e)}")

def create_consolidated_gantt(df):
    """Create a consolidated Gantt chart visualization."""
    satellites_per_6h = len(df) // 4
    unique_satellites = df.iloc[:satellites_per_6h]['Satellite'].tolist()
    
    fig = go.Figure()
    
    flag_colors = {
        'OK': '#2ca02c',
        'SHORT': '#ff7f0e',
        'LONG': '#1f77b4',
        'NO OVERLAP': '#d62728'
    }
    
    legend_added = set()
    satellite_to_y = {sat: i for i, sat in enumerate(unique_satellites)}
    
    max_end_time = 0
    for sat_idx, satellite in enumerate(unique_satellites):
        for period in range(4):
            df_idx = sat_idx + (period * satellites_per_6h)
            if df_idx < len(df):
                entry = df.iloc[df_idx]
                end_hour = entry['End'].hour + entry['End'].minute/60 + entry['End'].second/3600
                start_hour = entry['Start'].hour + entry['Start'].minute/60 + entry['Start'].second/3600
                if end_hour < start_hour:
                    end_hour += 24
                max_end_time = max(max_end_time, end_hour)
    
    for sat_idx, satellite in enumerate(unique_satellites):
        sat_entries = []
        for period in range(4):
            df_idx = sat_idx + (period * satellites_per_6h)
            if df_idx < len(df):
                row = df.iloc[df_idx]
                sat_entries.append(row)
        
        for entry in sat_entries:
            flags = entry['Flag'].split(', ') if entry['Flag'] != 'OK' else ['OK']
            
            if len(flags) == 1 and flags[0] == 'OK':
                color = flag_colors['OK']
                legend_name = 'OK'
            elif len(flags) == 1:
                color = flag_colors.get(flags[0], '#gray')
                legend_name = flags[0]
            else:
                primary_flag = [f for f in flags if f != 'OK'][0] if any(f != 'OK' for f in flags) else flags[0]
                secondary_flag = [f for f in flags if f != 'OK' and f != primary_flag]
                secondary_flag = secondary_flag[0] if secondary_flag else 'OK'
                color = flag_colors.get(primary_flag, '#gray')
                legend_name = f"{primary_flag} + {secondary_flag}"
            
            start_hour = entry['Start'].hour + entry['Start'].minute/60 + entry['Start'].second/3600
            end_hour = entry['End'].hour + entry['End'].minute/60 + entry['End'].second/3600
            
            if end_hour < start_hour:
                end_hour += 24
            
            y_position = satellite_to_y[satellite]
            
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
            
            showlegend = legend_name not in legend_added
            if showlegend:
                legend_added.add(legend_name)
            
            fig.add_trace(go.Scatter(
                x=[start_hour + (end_hour - start_hour)/2],
                y=[y_position],
                mode='markers',
                marker=dict(color=color, size=10, opacity=0),
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
    
    fig.update_layout(
        title="Satellite Coverage Timeline - 24 Hour View",
        xaxis_title="Time (Hours)",
        yaxis_title="Satellites",
        height=max(600, len(unique_satellites) * 60),
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
    
    return fig

def generate_txt(df, gateway_name, deploy_date, deploy_time):
    """Generate TXT output file from DataFrame."""
    global stored_txt_file, download_used
    stored_txt_file = BytesIO()
    download_used['txt'] = False

    first_start_time = df.iloc[0]["Start"]
    epoch_millis = int(first_start_time.timestamp() * 1000)
    
    deploy_time = datetime.combine(deploy_date.date(), deploy_time.time())
    deploy_str = deploy_time.strftime("%Y%m%d%H%M%S.000")

    output = f"{epoch_millis}\n"
    output += f"{deploy_str}\n"
    output += f"{gateway_name}\n"

    for _, row in df.iterrows():
        start_str = row["Start"].strftime("%Y%m%d%H%M%S.000")
        end_str = row["End"].strftime("%Y%m%d%H%M%S.000")
        output += f"{row['Satellite']} {row['Data']} {row['Reccurance']} {start_str} {end_str}\n"

    stored_txt_file.write(output.encode("utf-8"))
    stored_txt_file.seek(0)

def handle_xml_analysis(request):
    """Handle XML analysis form submission."""
    try:
        xml_file = request.files['file']
        gateway_name = request.form['gateway']
        deploy_date_str = request.form['Deploy_Date']
        deploy_date = datetime.strptime(deploy_date_str, "%Y%m%d")
        deploy_time_str = request.form['Deploy_Time']
        deploy_time = datetime.strptime(deploy_time_str, "%H:%M:%S")

        if not xml_file or not gateway_name or not deploy_date_str or not deploy_time_str:
            flash("Missing file or gateway name or deploy date or deploy time", "error")
            return redirect(url_for('index'))

        if not xml_file.filename.lower().endswith('.xml'):
            flash("Wrong file type. Please upload an XML file.", "error")
            return redirect(url_for('index'))

        df = parse_xml(xml_file.stream, deploy_date)
        generate_txt(df, gateway_name, deploy_date, deploy_time)

        df_reset = df.reset_index(drop=True)

        def flag_color(v):
                    if 'SHORT' in v or 'LONG' in v or 'NO OVERLAP' in v:
                        return 'background-color: #f8d7da;'
                    return ''
        
        styled_table = df_reset.style \
            .set_table_attributes('class="table table-bordered table-sm table-hover"') \
            .hide(axis='index') \
            .applymap(flag_color, subset=['Flag'])

        styled_table_html = styled_table.to_html()

        # Create summary statistics
        first_start = df['Start'].min()
        last_start = df['Start'].max()
        time_span_hours = (last_start - first_start).total_seconds() / 3600

        short_count = sum(1 for flag in df['Flag'] if 'SHORT' in flag)
        long_count = sum(1 for flag in df['Flag'] if 'LONG' in flag)
        no_overlap_count = sum(1 for flag in df['Flag'] if 'NO OVERLAP' in flag)
        flagged_count = sum(1 for flag in df['Flag'] if flag != 'OK')
        
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

        fig = create_consolidated_gantt(df)
        gantt_html = fig.to_html(full_html=False)

        return render_template('xml_analysis.html', table=styled_table_html, stats=stats, chart=gantt_html, gateway_name=gateway_name)

    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for('index'))
    except Exception as e:
        flash("Error with file.", "error")
        return redirect(url_for('index'))

# Route to download the XML-generated output .txt file
def download_txt():
    """Download generated TXT file."""
    global stored_txt_file, download_used
    if download_used['txt']:
        flash("File already downloaded", "error")
        return redirect(url_for('index'))
    
    stored_txt_file.seek(0)
    download_used['txt'] = True
    return send_file(stored_txt_file, mimetype='text/plain', as_attachment=True, download_name='output.txt')