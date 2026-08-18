import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def generate_chart(csv_path, chart_type='bar', output_image_path="usage_chart.png"):
    if not os.path.exists(csv_path):
        print(f"Error: File '{csv_path}' not found.")
        return

    print("Reading data...")
    df = pd.read_csv(csv_path)

    df['USAGE_DATE'] = pd.to_datetime(df['USAGE_DATE'], format='%m/%d/%Y')
    df['Year-Month'] = df['USAGE_DATE'].dt.strftime('%Y-%m')

    if chart_type == 'pie':
        print("Generating pie chart...")
        total_summary = df.groupby('CONSUMPTION_SURPLUSGENERATION')['USAGE_KWH'].sum()
        
        plt.figure(figsize=(8, 8))
        colors = ['#1f77b4', '#2ca02c']
        wedges, texts, autotexts = plt.pie(
            total_summary,
            labels=total_summary.index,
            autopct='%1.1f%%',
            startangle=140,
            colors=colors,
            textprops=dict(color="black", weight="bold"),
            wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2)
        )
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(12)
        
        plt.title('Total Energy Breakdown: Consumption vs Surplus Generation', fontsize=14, fontweight='bold')
        plt.tight_layout()
    else:
        print("Generating monthly bar chart...")
        monthly_data = df.groupby(['Year-Month', 'CONSUMPTION_SURPLUSGENERATION'])['USAGE_KWH'].sum().reset_index()

        plt.figure(figsize=(14, 6))
        sns.barplot(
            data=monthly_data,
            x='Year-Month',
            y='USAGE_KWH',
            hue='CONSUMPTION_SURPLUSGENERATION',
            palette={'Consumption': '#1f77b4', 'Surplus Generation': '#2ca02c'}
        )

        plt.title('Monthly Energy Usage: Consumption vs Surplus Generation', fontsize=14, fontweight='bold')
        plt.xlabel('Month (YYYY-MM)', fontsize=12)
        plt.ylabel('Total Energy (kWh)', fontsize=12)
        plt.xticks(rotation=45)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()

    plt.savefig(output_image_path, dpi=300)
    print(f"Success! Chart saved to: {output_image_path}")

if __name__ == '__main__':
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'IntervalData (2).csv'
    chart_type = sys.argv[2] if len(sys.argv) > 2 else 'bar'
    generate_chart(csv_file, chart_type)
