import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import plotly.graph_objects as go
import pandas as pd

def plot_synergy_bar_chart(df, title, focus_hero=None):
    """Generates a styled horizontal bar chart for synergy/anti-synergy."""
    if df.empty:
        st.warning("No data to plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 0.35 * len(df) + 1.2))

    if focus_hero:
        # Show only the partner hero in the label if a focus hero is selected
        y_labels = [h2 if h1 == focus_hero else h1 for h1, h2 in zip(df["Hero 1"], df["Hero 2"])]
    else:
        y_labels = [f"{h1} + {h2}" for h1, h2 in zip(df["Hero 1"], df["Hero 2"])]
    
    win_rates = df["Win Rate (%)"]
    colors = ['#43a047' if x >= 55 else '#e53935' if x <= 45 else '#ffb300' for x in win_rates]

    ax.barh(y_labels, win_rates, color=colors)

    # Add annotations
    for i, value in enumerate(win_rates):
        ax.text(value + 0.5, i, f'{value:.1f}%', va='center', fontsize=10, fontweight='bold')

    ax.set_xlabel("Win Rate (%)", fontsize=11, fontweight='bold')
    ax.set_title(title, fontsize=15, fontweight='bold', pad=12)
    ax.xaxis.grid(True, linestyle=':', alpha=0.5)
    ax.set_facecolor('#f7f7f7') # Light gray background for contrast
    sns.despine(left=True, bottom=True)
    ax.tick_params(axis='y', labelsize=11)
    
    # Invert y-axis to show the highest value at the top
    ax.invert_yaxis()
    
    plt.tight_layout()
    st.pyplot(fig)


def plot_counter_heatmap(df, title):
    """Generates a styled heatmap for counter matchups."""
    if df.empty or len(df) < 2:
        st.warning("Not enough data to generate a meaningful heatmap.")
        return

    pivot_df = df.pivot(index="Ally Hero", columns="Enemy Hero", values="Win Rate (%)")
    
    # Limit heatmap size for readability
    max_heroes = 15
    if pivot_df.shape[0] > max_heroes:
        top_allies = pivot_df.sum(axis=1).nlargest(max_heroes).index
        pivot_df = pivot_df.loc[top_allies]
    if pivot_df.shape[1] > max_heroes:
        top_enemies = pivot_df.sum(axis=0).nlargest(max_heroes).index
        pivot_df = pivot_df[top_enemies]

    height = min(0.6 * pivot_df.shape[0] + 1.5, 12)
    width = min(0.6 * pivot_df.shape[1] + 2.5, 15)
    
    fig, ax = plt.subplots(figsize=(width, height))
    
    sns.heatmap(
        pivot_df,
        annot=True,
        fmt=".1f",
        cmap="coolwarm",
        linewidths=0.5,
        ax=ax,
        cbar_kws={'label': 'Win Rate (%)'}
    )
    
    ax.set_title(title, fontsize=15, fontweight='bold', pad=13)
    ax.set_xlabel("Enemy Hero", fontsize=12, fontweight='bold')
    ax.set_ylabel("Ally Hero", fontsize=12, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    
    st.pyplot(fig)

def plot_synergy_bar_chart_interactive(df, title, chart_type='top'):
    """
    Creates an interactive bar chart for synergy analysis with enhanced visual polish.
    """
    
    if df.empty:
        st.warning("No data to plot.")
        return None, None

    # --- MODIFICATION START: Ensure data is sorted for plotting ---
    # Because the y-axis is reversed, sorting ascending places the highest value at the top.
    if chart_type == 'top':
        sort_column = 'Win Rate (%)'
    else: # trending charts
        sort_column = 'Change (%)' if chart_type == 'trending_up' else 'Change (%)'
    
    # For trending down, we want the biggest negative change at the top, so we sort ascending by change
    df = df.sort_values(by=sort_column, ascending=(chart_type != 'trending_down'))
    # --- MODIFICATION END ---

    # Prepare data based on chart type
    if chart_type == 'top':
        y_labels = [f"{h1} + {h2}" for h1, h2 in zip(df["Hero 1"], df["Hero 2"])]
        x_values = df["Win Rate (%)"]
        
        # Text on bars with better formatting
        text_labels = [f"<b>{wr:.1f}%</b> ({g})" for wr, g in 
                      zip(df["Win Rate (%)"], df["Games Together"])]
        
        # Enhanced hover text
        hover_texts = []
        for idx, row in df.iterrows():
            wins = row["Wins"]
            losses = row["Games Together"] - wins
            
            hover_text = f"<b style='font-size:14px'>{row['Hero 1']} + {row['Hero 2']}</b><br><br>"
            hover_text += f"<b>Performance:</b><br>"
            hover_text += f"Win Rate: <b>{row['Win Rate (%)']}%</b><br>"
            hover_text += f"Record: <b style='color:#43a047'>{wins}W</b> - <b style='color:#e53935'>{losses}L</b><br>"
            hover_text += f"Total Games: <b>{row['Games Together']}</b><br><br>"
            
            if 'Most Used By' in row and row['Most Used By'] != 'N/A':
                hover_text += f"<b>Team Info:</b><br>"
                hover_text += f"Most used by: {row['Most Used By']}<br>"
            
            if 'Last Played' in row and row['Last Played'] != 'N/A':
                hover_text += f"Last played: <i>{row['Last Played']}</i>"
            
            hover_texts.append(hover_text)
    
    elif chart_type in ['trending_up', 'trending_down']:
        y_labels = [f"{h1} + {h2}" for h1, h2 in zip(df["Hero 1"], df["Hero 2"])]
        x_values = df["Current Win Rate (%)"]
        
        # Enhanced text labels with arrows
        text_labels = []
        for change, prev, curr in zip(df["Change (%)"], df["Previous Win Rate (%)"], df["Current Win Rate (%)"]):
            arrow = '↑' if change > 0 else '↓'
            color = '#43a047' if change > 0 else '#e53935'
            text_labels.append(
                f"<b>{curr:.1f}%</b> <span style='color:{color}'>{arrow}{abs(change):.1f}%</span>"
            )
        
        # Hover text for trending
        hover_texts = []
        for idx, row in df.iterrows():
            change_color = '#43a047' if row['Change (%)'] > 0 else '#e53935'
            arrow = '↑' if row['Change (%)'] > 0 else '↓'
            
            hover_text = f"<b style='font-size:14px'>{row['Hero 1']} + {row['Hero 2']}</b><br><br>"
            hover_text += f"<b>Trend Analysis:</b><br>"
            hover_text += f"Current: <b>{row['Current Win Rate (%)']}%</b> ({row['Current Games']} games)<br>"
            hover_text += f"Previous: {row['Previous Win Rate (%)']}% ({row['Previous Games']} games)<br>"
            hover_text += f"Change: <b style='color:{change_color}'>{arrow} {abs(row['Change (%)']):.1f}% points</b><br><br>"
            
            if 'Most Used By' in row and row['Most Used By'] != 'N/A':
                hover_text += f"<b>Current Usage:</b><br>"
                hover_text += f"Most used by: {row['Most Used By']}"
            
            hover_texts.append(hover_text)
    
    # Enhanced color mapping with gradients
    def get_color(win_rate):
        if win_rate >= 85:
            return '#2e7d32'  # Dark green
        elif win_rate >= 80:
            return '#43a047'  # Green
        elif win_rate >= 70:
            return '#66bb6a'  # Light green
        elif win_rate >= 60:
            return '#ffb300'  # Yellow
        elif win_rate >= 50:
            return '#ff8f00'  # Dark yellow
        else:
            return '#e53935'  # Red
    
    colors = [get_color(wr) for wr in x_values]
    
    # Create the figure with enhanced styling
    fig = go.Figure()
    
    # Add bars with better styling
    fig.add_trace(go.Bar(
        y=y_labels,
        x=x_values,
        orientation='h',
        text=text_labels,
        textposition='outside',
        textfont=dict(size=11, family='Arial',color='#1a1a1a'),
        marker=dict(
            color=colors,
            line=dict(color='rgba(0,0,0,0.1)', width=1)  # Subtle border
        ),
        hovertext=hover_texts,
        hoverinfo='text',
        showlegend=False,
        texttemplate='%{text}',
        width=0.7  # Slightly thinner bars
    ))
    
    # Enhanced layout
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=16, color='#1f1f1f'),  # Slightly smaller for consistency
            x=0.5,
            xanchor='center',
            y=0.98,
            yanchor='top'
        ),
        height=400,  # Fixed height
        width=1000,  # Let Streamlit handle width
        margin=dict(l=160, r=80, t=60, b=40),  # Reduced right margin
        xaxis=dict(
            title=dict(
                text='<b>Win Rate (%)</b>' if chart_type == 'top' else '<b>Current Win Rate (%)</b>',
                font=dict(size=12, color='#555555')
            ),
            range=[0, 105],  # Consistent range
            showgrid=True,
            gridcolor='rgba(200, 200, 200, 0.3)',
            gridwidth=1,
            zeroline=True,
            zerolinecolor='rgba(128, 128, 128, 0.4)',
            tickfont=dict(size=10, color='#666666'),
            tickformat='.0f'
        ),
        yaxis=dict(
            showgrid=False,
            autorange='reversed',
            tickfont=dict(size=11, color='#333333'),
            tickmode='linear'
        ),
        plot_bgcolor='#fafafa',
        paper_bgcolor='white',
        hoverlabel=dict(
            bgcolor="white",
            font=dict(size=12, color='#333333'),
            bordercolor='#333333'
        ),
        autosize=False,  # Important: let the chart auto-size
        transition=dict(duration=500)
    )
    
    # Add multiple reference lines for context
    # Average line
    fig.add_vline(
        x=50,
        line=dict(dash="dash", color="gray", width=2),
        opacity=0.7,
        annotation=dict(
            text="<b>Average</b>",
            font=dict(size=10, color='gray'),
            showarrow=False,
            yshift=-20
        )
    )
    
    # Excellence threshold
    fig.add_vline(
        x=80,
        line=dict(dash="dot", color="#43a047", width=1.5),
        opacity=0.5,
        annotation=dict(
            text="<b>Excellent</b>",
            font=dict(size=10, color='#43a047'),
            showarrow=False,
            yshift=-20
        )
    )
    
    # Add subtle background shading for performance zones
    fig.add_shape(
        type="rect",
        x0=0, x1=50,
        y0=-0.5, y1=len(df)-0.5,
        fillcolor="rgba(229, 57, 53, 0.05)",
        line=dict(width=0),
        layer="below"
    )
    
    fig.add_shape(
        type="rect",
        x0=50, x1=60,
        y0=-0.5, y1=len(df)-0.5,
        fillcolor="rgba(255, 179, 0, 0.05)",
        line=dict(width=0),
        layer="below"
    )
    
    fig.add_shape(
        type="rect",
        x0=60, x1=80,
        y0=-0.5, y1=len(df)-0.5,
        fillcolor="rgba(255, 235, 59, 0.05)",
        line=dict(width=0),
        layer="below"
    )
    
    fig.add_shape(
        type="rect",
        x0=80, x1=110,
        y0=-0.5, y1=len(df)-0.5,
        fillcolor="rgba(67, 160, 71, 0.05)",
        line=dict(width=0),
        layer="below"
    )
    
    # --- MODIFICATION START: Disable scroll zoom ---
    config = {
        'scrollZoom': False, # This disables zooming with the scroll wheel
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d', 'autoScale2d', 'zoomIn2d', 'zoomOut2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': f'synergy_analysis_{chart_type}',
            'height': 500,
            'width': 800,
            'scale': 2
        }
    }
    # --- MODIFICATION END ---
    
    return fig, config

def create_counter_bars(df, title, color_scheme='green'):
    """
    Creates a bar chart for counter matchups.
    
    Args:
        df: DataFrame with counter data
        title: Chart title
        color_scheme: 'green' for counters, 'red' for countered by
    """
    if df.empty:
        return None
    
    # Prepare data
    y_labels = df["Enemy Hero"].tolist()
    x_values = df["Win Rate (%)"].tolist()
    
    # Text labels with better visibility
    text_labels = [f"<b>{wr:.1f}%</b> ({g})" for wr, g in 
                  zip(df["Win Rate (%)"], df["Games Against"])]
    
    # Hover text
    hover_texts = []
    for idx, row in df.iterrows():
        hover_text = (
            f"<b>{row['Enemy Hero']}</b><br><br>"
            f"Win Rate: <b>{row['Win Rate (%)']}%</b><br>"
            f"Games: {row['Games Against']}<br>"
            f"Wins: {row['Wins']}<br>"
            f"Losses: {row['Losses']}"
        )
        hover_texts.append(hover_text)
    
    # Color based on scheme
    if color_scheme == 'green':
        # Green gradient for counters
        colors = ['#2e7d32' if wr >= 70 else '#43a047' if wr >= 60 else '#66bb6a' 
                 for wr in x_values]
    else:
        # Red gradient for countered by
        colors = ['#b71c1c' if wr >= 70 else '#d32f2f' if wr >= 60 else '#ef5350' 
                 for wr in x_values]
    
    # Create figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=y_labels,
        x=x_values,
        orientation='h',
        text=text_labels,
        textposition='outside',
        textfont=dict(
            size=12,  # Larger text
            color='#000000',  # Black text for better visibility
            family='Arial Bold'  # Bold font
        ),
        marker=dict(
            color=colors,
            line=dict(color='rgba(0,0,0,0.1)', width=1)
        ),
        hovertext=hover_texts,
        hoverinfo='text',
        showlegend=False
    ))
    
    # Update layout with better spacing
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(size=14, color='#1f1f1f'),
            x=0.5,
            xanchor='center'
        ),
        height=300,  # Height for side-by-side display
        margin=dict(l=100, r=100, t=40, b=30),  # More right margin for text
        xaxis=dict(
            range=[0, 110],  # Extended range to show 100% labels
            showgrid=True,
            gridcolor='rgba(200, 200, 200, 0.3)',
            title=None,  # No axis title to save space
            tickfont=dict(size=10, color='#666666')
        ),
        yaxis=dict(
            showgrid=False,
            autorange='reversed',
            tickfont=dict(size=11, color='#000000')  # Darker y-axis labels
        ),
        plot_bgcolor='#fafafa',  # Slight background color
        paper_bgcolor='white'
    )
    
    # Add reference line at 50%
    fig.add_vline(
        x=50,
        line=dict(dash="dash", color="gray", width=1),
        opacity=0.5,
        annotation=dict(
            text="50%",
            font=dict(size=9, color='gray'),
            showarrow=False,
            yshift=-15
        )
    )
    
    # Add excellence line for context
    if color_scheme == 'green':
        fig.add_vline(
            x=60,
            line=dict(dash="dot", color="#43a047", width=1),
            opacity=0.3
        )
    
    return fig
