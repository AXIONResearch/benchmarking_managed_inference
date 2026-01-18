import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json

st.set_page_config(page_title="vLLM Benchmark Results", layout="wide")

st.title("🚀 Baseline vs Optimized vLLM Benchmark Comparison")

# Sidebar for configuration
st.sidebar.header("Configuration")
results_dir = Path("../results")
env_type = st.sidebar.selectbox("Environment", ["baseline", "managed"], index=0)

# Load results
results_path = results_dir / env_type
if not results_path.exists():
    st.error(f"No results found for {env_type} environment at {results_path}")
    st.stop()

# Find all GenAI-Perf result directories
genai_perf_dirs = sorted(results_path.glob("genai_perf_*"), reverse=True)

if not genai_perf_dirs:
    st.warning(f"No benchmark results found in {results_path}")
    st.info("Run benchmarks using: `./scripts/benchmark_all_models.sh baseline`")
    st.stop()

# Select benchmark run
selected_run = st.sidebar.selectbox(
    "Benchmark Run",
    options=[d.name for d in genai_perf_dirs],
    index=0
)

selected_dir = results_path / selected_run

# Load CSV results
csv_file = selected_dir / "profile_export.csv"
json_file = selected_dir / "profile_export.json"

if not csv_file.exists():
    st.error(f"Results file not found: {csv_file}")
    st.stop()

# Load data
df = pd.read_csv(csv_file)
if json_file.exists():
    with open(json_file) as f:
        json_data = json.load(f)
else:
    json_data = None

# Display key metrics
st.header("📊 Key Performance Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    avg_ttft = df['time_to_first_token_ms'].mean()
    st.metric("Avg Time to First Token (TTFT)", f"{avg_ttft:.2f} ms")

with col2:
    avg_itl = df['inter_token_latency_ms'].mean()
    st.metric("Avg Inter-Token Latency (ITL)", f"{avg_itl:.2f} ms")

with col3:
    avg_e2e = df['end_to_end_latency_ms'].mean()
    st.metric("Avg End-to-End Latency", f"{avg_e2e:.2f} ms")

with col4:
    if 'request_throughput' in df.columns:
        throughput = df['request_throughput'].mean()
        st.metric("Throughput", f"{throughput:.2f} req/s")
    else:
        total_time = df['end_to_end_latency_ms'].sum() / 1000
        throughput = len(df) / total_time if total_time > 0 else 0
        st.metric("Est. Throughput", f"{throughput:.2f} req/s")

# Distribution plots
st.header("📈 Latency Distributions")

col1, col2 = st.columns(2)

with col1:
    fig_ttft = px.histogram(
        df,
        x='time_to_first_token_ms',
        nbins=30,
        title="Time to First Token Distribution",
        labels={'time_to_first_token_ms': 'TTFT (ms)'}
    )
    fig_ttft.update_layout(showlegend=False)
    st.plotly_chart(fig_ttft, use_container_width=True)

with col2:
    fig_itl = px.histogram(
        df,
        x='inter_token_latency_ms',
        nbins=30,
        title="Inter-Token Latency Distribution",
        labels={'inter_token_latency_ms': 'ITL (ms)'}
    )
    fig_itl.update_layout(showlegend=False)
    st.plotly_chart(fig_itl, use_container_width=True)

# End-to-end latency over time
st.header("⏱️ Latency Over Time")
fig_timeline = px.scatter(
    df.reset_index(),
    x='index',
    y='end_to_end_latency_ms',
    title="End-to-End Latency per Request",
    labels={'index': 'Request Number', 'end_to_end_latency_ms': 'Latency (ms)'}
)
fig_timeline.add_hline(
    y=df['end_to_end_latency_ms'].mean(),
    line_dash="dash",
    annotation_text=f"Mean: {df['end_to_end_latency_ms'].mean():.2f} ms"
)
st.plotly_chart(fig_timeline, use_container_width=True)

# Percentiles
st.header("📊 Latency Percentiles")
percentiles = [50, 90, 95, 99]
perc_data = []

for metric in ['time_to_first_token_ms', 'inter_token_latency_ms', 'end_to_end_latency_ms']:
    for p in percentiles:
        val = df[metric].quantile(p/100)
        perc_data.append({
            'Metric': metric.replace('_', ' ').title().replace('Ms', '(ms)'),
            'Percentile': f'P{p}',
            'Value': val
        })

perc_df = pd.DataFrame(perc_data)
fig_perc = px.bar(
    perc_df,
    x='Percentile',
    y='Value',
    color='Metric',
    barmode='group',
    title="Latency Percentiles Comparison"
)
st.plotly_chart(fig_perc, use_container_width=True)

# Token statistics
st.header("🔢 Token Statistics")
col1, col2 = st.columns(2)

with col1:
    if 'num_input_tokens' in df.columns:
        st.metric("Avg Input Tokens", f"{df['num_input_tokens'].mean():.0f}")
        fig_input = px.histogram(df, x='num_input_tokens', title="Input Token Distribution")
        st.plotly_chart(fig_input, use_container_width=True)

with col2:
    if 'num_output_tokens' in df.columns:
        st.metric("Avg Output Tokens", f"{df['num_output_tokens'].mean():.0f}")
        fig_output = px.histogram(df, x='num_output_tokens', title="Output Token Distribution")
        st.plotly_chart(fig_output, use_container_width=True)

# Raw data
with st.expander("📄 View Raw Data"):
    st.dataframe(df)

# JSON metadata if available
if json_data:
    with st.expander("🔍 Benchmark Configuration"):
        st.json(json_data.get('config', json_data))
