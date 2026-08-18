import io
import base64
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, render_template, request, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)

def generate_pdf_report(df, meter_id, start_date, end_date, chart_buf):
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=15
    )
    story.append(Paragraph("Energy Usage Summary Report", title_style))
    story.append(Spacer(1, 10))

    # Metadata Table
    meta_data = [
        [Paragraph("<b>Meter ID (ESIID):</b>", styles['Normal']), Paragraph(str(meter_id), styles['Normal'])],
        [Paragraph("<b>Start Date:</b>", styles['Normal']), Paragraph(str(start_date), styles['Normal'])],
        [Paragraph("<b>End Date:</b>", styles['Normal']), Paragraph(str(end_date), styles['Normal'])],
    ]
    meta_table = Table(meta_data, colWidths=[150, 350])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Date parsing and monthly tag creation
    df['USAGE_DATE'] = pd.to_datetime(df['USAGE_DATE'], format='%m/%d/%Y', errors='coerce')
    df['Year_Month'] = df['USAGE_DATE'].dt.strftime('%Y-%m')
    
    # Overall Summary Metrics
    total_consumption = df[df['CONSUMPTION_SURPLUSGENERATION'] == 'Consumption']['USAGE_KWH'].sum()
    total_surplus = df[df['CONSUMPTION_SURPLUSGENERATION'] == 'Surplus Generation']['USAGE_KWH'].sum()
    net_usage = total_consumption - total_surplus

    summary_data = [
        [Paragraph("<b>Metric</b>", styles['Normal']), Paragraph("<b>Total Value (kWh)</b>", styles['Normal'])],
        [Paragraph("Total Consumption", styles['Normal']), Paragraph(f"{total_consumption:,.2f}", styles['Normal'])],
        [Paragraph("Total Surplus Generation", styles['Normal']), Paragraph(f"{total_surplus:,.2f}", styles['Normal'])],
        [Paragraph("Net Grid Usage", styles['Normal']), Paragraph(f"{net_usage:,.2f}", styles['Normal'])],
    ]
    summary_table = Table(summary_data, colWidths=[250, 250])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Add Chart Image
    chart_buf.seek(0)
    img = Image(chart_buf, width=540, height=220)
    story.append(img)
    story.append(Spacer(1, 20))

    # --- Monthly Aggregation & Table ---
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=10
    )
    story.append(Paragraph("Monthly Summary Breakdown", section_heading))

    # Pivot table to sum consumption & surplus generation per month
    monthly_df = df.pivot_table(
        index='Year_Month',
        columns='CONSUMPTION_SURPLUSGENERATION',
        values='USAGE_KWH',
        aggfunc='sum',
        fill_value=0
    ).reset_index()

    # Ensure required columns exist if a category is missing
    if 'Consumption' not in monthly_df.columns:
        monthly_df['Consumption'] = 0.0
    if 'Surplus Generation' not in monthly_df.columns:
        monthly_df['Surplus Generation'] = 0.0

    # Calculate net monthly usage
    monthly_df['Net Usage'] = monthly_df['Consumption'] - monthly_df['Surplus Generation']

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        textColor=colors.white,
        fontName='Helvetica-Bold'
    )

    monthly_table_data = [
        [
            Paragraph("<b>Month</b>", header_style),
            Paragraph("<b>Consumption (kWh)</b>", header_style),
            Paragraph("<b>Surplus Gen. (kWh)</b>", header_style),
            Paragraph("<b>Net Usage (kWh)</b>", header_style)
        ]
    ]

    for _, row in monthly_df.iterrows():
        monthly_table_data.append([
            Paragraph(str(row['Year_Month']), styles['Normal']),
            Paragraph(f"{row['Consumption']:,.2f}", styles['Normal']),
            Paragraph(f"{row['Surplus Generation']:,.2f}", styles['Normal']),
            Paragraph(f"{row['Net Usage']:,.2f}", styles['Normal'])
        ])

    # Construct and style the monthly breakdown table
    monthly_table = Table(monthly_table_data, colWidths=[110, 130, 130, 130])
    monthly_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    story.append(monthly_table)

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf

def process_csv(file_stream, chart_type='bar', filter_meter='All', start_date='', end_date=''):
    df = pd.read_csv(file_stream)
    df['USAGE_DATE_DT'] = pd.to_datetime(df['USAGE_DATE'], format='%m/%d/%Y')

    # Get metadata dropdown options
    meters = ['All'] + sorted(df['ESIID'].astype(str).unique().tolist())

    # Filtering
    if filter_meter and filter_meter != 'All':
        df = df[df['ESIID'].astype(str) == filter_meter]

    if start_date:
        df = df[df['USAGE_DATE_DT'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['USAGE_DATE_DT'] <= pd.to_datetime(end_date)]

    actual_start = df['USAGE_DATE_DT'].min().strftime('%Y-%m-%d') if not df.empty else 'N/A'
    actual_end = df['USAGE_DATE_DT'].max().strftime('%Y-%m-%d') if not df.empty else 'N/A'
    actual_meter = filter_meter if filter_meter != 'All' else (df['ESIID'].astype(str).iloc[0] if not df.empty else 'N/A')

    df['Year_Month'] = df['USAGE_DATE_DT'].dt.strftime('%Y-%m')
    monthly_summary = df.groupby(['Year_Month', 'CONSUMPTION_SURPLUSGENERATION'])['USAGE_KWH'].sum().reset_index()

    plt.figure(figsize=(12, 5.5))
    if chart_type == 'pie':
        total_summary = df.groupby('CONSUMPTION_SURPLUSGENERATION')['USAGE_KWH'].sum()
        colors_list = ['#1f77b4', '#2ca02c']
        plt.pie(
            total_summary,
            labels=total_summary.index,
            autopct='%1.1f%%',
            startangle=140,
            colors=colors_list,
            textprops=dict(color="black", weight="bold"),
            wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2)
        )
        plt.title(f'Energy Breakdown ({actual_meter})', fontsize=14, fontweight='bold')
    else:
        sns.barplot(
            data=monthly_summary,
            x='Year_Month',
            y='USAGE_KWH',
            hue='CONSUMPTION_SURPLUSGENERATION',
            palette={'Consumption': '#1f77b4', 'Surplus Generation': '#2ca02c'}
        )
        plt.title(f'Monthly Energy Usage ({actual_meter})', fontsize=14, fontweight='bold')
        plt.xlabel('Month (YYYY-MM)', fontsize=12)
        plt.ylabel('Total Energy (kWh)', fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.legend(title='Category')

    plt.tight_layout()

    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150)
    img_buf.seek(0)
    plt.close()

    # Generate PDF
    pdf_buf = generate_pdf_report(df, actual_meter, actual_start, actual_end, img_buf)

    chart_base64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')
    pdf_base64 = base64.b64encode(pdf_buf.getvalue()).decode('utf-8')

    return chart_base64, pdf_base64, meters, actual_meter, actual_start, actual_end

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    chart_url = None
    pdf_url = None
    error = None
    meters = []
    selected_chart_type = 'bar'
    selected_meter = 'All'
    start_date = ''
    end_date = ''

    if request.method == 'POST':
        if 'file' not in request.files:
            error = "No file uploaded."
        else:
            file = request.files['file']
            selected_chart_type = request.form.get('chart_type', 'bar')
            selected_meter = request.form.get('meter_id', 'All')
            start_date = request.form.get('start_date', '')
            end_date = request.form.get('end_date', '')

            if file.filename == '':
                error = "No file selected."
            else:
                try:
                    chart_url, pdf_url, meters, selected_meter, start_date, end_date = process_csv(
                        file, selected_chart_type, selected_meter, start_date, end_date
                    )
                except Exception as e:
                    error = f"Error processing file: {str(e)}"

    return render_template(
        'index.html',
        chart_url=chart_url,
        pdf_url=pdf_url,
        error=error,
        meters=meters,
        selected_chart_type=selected_chart_type,
        selected_meter=selected_meter,
        start_date=start_date,
        end_date=end_date
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
