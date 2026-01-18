import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path

st.set_page_config(page_title="Baseline vs Managed Comparison", layout="wide")

st.title("🚀 Baseline vs Managed vLLM Infrastructure Comparison")

# Sidebar configuration
st.sidebar.header("⚙️ Configuration")

# Benchmark type selector
benchmark_type = st.sidebar.selectbox(
    "Benchmark Type",
    ["Custom Benchmark", "GenAI-Perf", "Both (Comparison)"],
    help="Select which benchmark results to display"
)

view_mode = st.sidebar.radio(
    "View Mode",
    ["Single Environment", "Side-by-Side Comparison", "Overlay Comparison"],
    index=1
)

# Load results function
def load_results(env_name, bench_type="custom"):
    """Load results for a given environment and benchmark type"""
    if bench_type == "custom":
        results_file = Path(f"../results/{env_name}/k8s/all-models-results.json")
    else:  # genai-perf
        results_file = Path(f"../results/{env_name}/k8s/genai-perf-results.json")

    if results_file.exists():
        with open(results_file) as f:
            return json.load(f), True, str(results_file)
    return None, False, str(results_file)

# Load results based on selected benchmark type
if benchmark_type == "Custom Benchmark":
    baseline_results, baseline_exists, baseline_file = load_results("baseline", "custom")
    managed_results, managed_exists, managed_file = load_results("managed", "custom")
    results_label = "Custom Benchmark"
elif benchmark_type == "GenAI-Perf":
    baseline_results, baseline_exists, baseline_file = load_results("baseline", "genai-perf")
    managed_results, managed_exists, managed_file = load_results("managed", "genai-perf")
    results_label = "GenAI-Perf"
else:  # Both
    baseline_custom, baseline_custom_exists, _ = load_results("baseline", "custom")
    baseline_genai, baseline_genai_exists, _ = load_results("baseline", "genai-perf")
    managed_custom, managed_custom_exists, _ = load_results("managed", "custom")
    managed_genai, managed_genai_exists, _ = load_results("managed", "genai-perf")

    # For "Both" mode, use custom as primary, we'll add comparison later
    baseline_results, baseline_exists, baseline_file = baseline_custom, baseline_custom_exists, "custom"
    managed_results, managed_exists, managed_file = managed_custom, managed_custom_exists, "custom"
    results_label = "Both Benchmarks"

# Function to create comparison dataframe
def create_comparison_df(results, env_name):
    """Create a dataframe from results for a specific environment"""
    if not results:
        return pd.DataFrame()

    data = []
    for result in results:
        model_short_name = result['model'].split('/')[-1]
        data.append({
            'Environment': env_name,
            'Model': model_short_name,
            'Full Model Name': result['model'],
            'Requests/sec': result['requests_per_second'],
            'Mean Latency (s)': result['latency']['mean'],
            'Median Latency (s)': result['latency']['median'],
            'P95 Latency (s)': result['latency']['p95'],
            'P99 Latency (s)': result['latency']['p99'],
            'Min Latency (s)': result['latency']['min'],
            'Max Latency (s)': result['latency']['max'],
            'Tokens/sec': result['throughput_tokens_per_sec']['total'],
            'Mean Tokens/sec': result['throughput_tokens_per_sec']['mean'],
            'Total Tokens': result['tokens']['total'],
            'Success Rate %': (result['successful_requests']/result['total_requests']) * 100,
            'Total Requests': result['total_requests'],
            'Successful Requests': result['successful_requests'],
            'Failed Requests': result['failed_requests'],
            'Total Time (s)': result['total_time']
        })
    return pd.DataFrame(data)

# Display benchmark type info
st.info(f"📊 Displaying: **{results_label}** results")

# Check what data is available
if not baseline_exists and not managed_exists:
    st.error(f"❌ No results found for either baseline or managed environments ({results_label})")
    st.info("""
    To generate results:
    1. Run benchmarks for baseline: `k8s/benchmark_k8s.py` (already done)
    2. Run benchmarks for managed: Deploy managed K8s and run benchmarks
    """)
    st.stop()

# Create dataframes
df_baseline = create_comparison_df(baseline_results, "Baseline") if baseline_exists else pd.DataFrame()
df_managed = create_comparison_df(managed_results, "Managed") if managed_exists else pd.DataFrame()
df_combined = pd.concat([df_baseline, df_managed], ignore_index=True)

# === SINGLE ENVIRONMENT VIEW ===
if view_mode == "Single Environment":
    available_envs = []
    if baseline_exists:
        available_envs.append("Baseline")
    if managed_exists:
        available_envs.append("Managed")

    selected_env = st.sidebar.selectbox("Select Environment", available_envs)

    df_selected = df_baseline if selected_env == "Baseline" else df_managed
    results_selected = baseline_results if selected_env == "Baseline" else managed_results

    st.header(f"📊 {selected_env} Environment Results")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Models Tested", len(df_selected))
    with col2:
        st.metric("Total Requests", int(df_selected['Total Requests'].sum()))
    with col3:
        st.metric("Avg Requests/sec", f"{df_selected['Requests/sec'].mean():.2f}")
    with col4:
        st.metric("Avg Success Rate", f"{df_selected['Success Rate %'].mean():.1f}%")

    # Display table
    st.subheader("Performance Metrics")
    display_cols = ['Model', 'Requests/sec', 'Mean Latency (s)', 'P95 Latency (s)',
                   'Tokens/sec', 'Success Rate %']
    st.dataframe(df_selected[display_cols], use_container_width=True)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(df_selected, x='Model', y='Requests/sec',
                    title="Requests per Second", color='Model')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(df_selected, x='Model', y='Mean Latency (s)',
                    title="Mean Latency", color='Model')
        st.plotly_chart(fig, use_container_width=True)

# === SIDE-BY-SIDE COMPARISON ===
elif view_mode == "Side-by-Side Comparison":
    if not baseline_exists or not managed_exists:
        st.warning("⚠️ Side-by-side comparison requires both baseline and managed results")
        st.info(f"Available: {'Baseline' if baseline_exists else ''} {'Managed' if managed_exists else ''}")

        if baseline_exists:
            st.subheader("📊 Baseline Results (Available)")
            st.dataframe(df_baseline[['Model', 'Requests/sec', 'Mean Latency (s)', 'Tokens/sec']])
        if managed_exists:
            st.subheader("📊 Managed Results (Available)")
            st.dataframe(df_managed[['Model', 'Requests/sec', 'Mean Latency (s)', 'Tokens/sec']])
        st.stop()

    st.header("🔀 Side-by-Side Environment Comparison")

    # Overall comparison
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔵 Baseline")
        st.metric("Avg Requests/sec", f"{df_baseline['Requests/sec'].mean():.2f}")
        st.metric("Avg Latency", f"{df_baseline['Mean Latency (s)'].mean():.2f}s")
        st.metric("Avg Tokens/sec", f"{df_baseline['Tokens/sec'].mean():.0f}")

    with col2:
        st.subheader("🟢 Managed")
        baseline_avg_rps = df_baseline['Requests/sec'].mean()
        managed_avg_rps = df_managed['Requests/sec'].mean()
        improvement_rps = ((managed_avg_rps - baseline_avg_rps) / baseline_avg_rps) * 100

        baseline_avg_lat = df_baseline['Mean Latency (s)'].mean()
        managed_avg_lat = df_managed['Mean Latency (s)'].mean()
        improvement_lat = ((baseline_avg_lat - managed_avg_lat) / baseline_avg_lat) * 100

        baseline_avg_tokens = df_baseline['Tokens/sec'].mean()
        managed_avg_tokens = df_managed['Tokens/sec'].mean()
        improvement_tokens = ((managed_avg_tokens - baseline_avg_tokens) / baseline_avg_tokens) * 100

        st.metric("Avg Requests/sec", f"{managed_avg_rps:.2f}",
                 delta=f"{improvement_rps:+.1f}%")
        st.metric("Avg Latency", f"{managed_avg_lat:.2f}s",
                 delta=f"{improvement_lat:+.1f}% (lower is better)",
                 delta_color="inverse")
        st.metric("Avg Tokens/sec", f"{managed_avg_tokens:.0f}",
                 delta=f"{improvement_tokens:+.1f}%")

    # Per-model comparison table
    st.subheader("📋 Per-Model Comparison")

    comparison_data = []
    for model in df_baseline['Model'].unique():
        baseline_row = df_baseline[df_baseline['Model'] == model].iloc[0]
        managed_row = df_managed[df_managed['Model'] == model].iloc[0] if model in df_managed['Model'].values else None

        if managed_row is not None:
            rps_improvement = ((managed_row['Requests/sec'] - baseline_row['Requests/sec']) / baseline_row['Requests/sec']) * 100
            lat_improvement = ((baseline_row['Mean Latency (s)'] - managed_row['Mean Latency (s)']) / baseline_row['Mean Latency (s)']) * 100
            tokens_improvement = ((managed_row['Tokens/sec'] - baseline_row['Tokens/sec']) / baseline_row['Tokens/sec']) * 100

            comparison_data.append({
                'Model': model,
                'Baseline Req/s': f"{baseline_row['Requests/sec']:.2f}",
                'Managed Req/s': f"{managed_row['Requests/sec']:.2f}",
                'Req/s Δ%': f"{rps_improvement:+.1f}%",
                'Baseline Latency': f"{baseline_row['Mean Latency (s)']:.2f}s",
                'Managed Latency': f"{managed_row['Mean Latency (s)']:.2f}s",
                'Latency Δ%': f"{lat_improvement:+.1f}%",
                'Baseline Tokens/s': f"{baseline_row['Tokens/sec']:.0f}",
                'Managed Tokens/s': f"{managed_row['Tokens/sec']:.0f}",
                'Tokens/s Δ%': f"{tokens_improvement:+.1f}%"
            })

    df_comparison_table = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison_table, use_container_width=True)

# === OVERLAY COMPARISON ===
elif view_mode == "Overlay Comparison":
    if not baseline_exists or not managed_exists:
        st.warning("⚠️ Overlay comparison requires both baseline and managed results")
        st.info(f"Available: {'Baseline' if baseline_exists else ''} {'Managed' if managed_exists else ''}")
        st.stop()

    st.header("📊 Overlay Comparison Charts")

    # Requests/sec comparison
    fig_rps = go.Figure()
    fig_rps.add_trace(go.Bar(
        name='Baseline',
        x=df_baseline['Model'],
        y=df_baseline['Requests/sec'],
        marker_color='lightblue'
    ))
    fig_rps.add_trace(go.Bar(
        name='Managed',
        x=df_managed['Model'],
        y=df_managed['Requests/sec'],
        marker_color='lightgreen'
    ))
    fig_rps.update_layout(
        title='Requests per Second Comparison',
        xaxis_title='Model',
        yaxis_title='Requests/sec',
        barmode='group'
    )
    st.plotly_chart(fig_rps, use_container_width=True)

    # Latency comparison
    col1, col2 = st.columns(2)

    with col1:
        fig_lat = go.Figure()
        fig_lat.add_trace(go.Bar(
            name='Baseline',
            x=df_baseline['Model'],
            y=df_baseline['Mean Latency (s)'],
            marker_color='lightblue'
        ))
        fig_lat.add_trace(go.Bar(
            name='Managed',
            x=df_managed['Model'],
            y=df_managed['Mean Latency (s)'],
            marker_color='lightgreen'
        ))
        fig_lat.update_layout(
            title='Mean Latency Comparison',
            xaxis_title='Model',
            yaxis_title='Latency (s)',
            barmode='group'
        )
        st.plotly_chart(fig_lat, use_container_width=True)

    with col2:
        fig_tokens = go.Figure()
        fig_tokens.add_trace(go.Bar(
            name='Baseline',
            x=df_baseline['Model'],
            y=df_baseline['Tokens/sec'],
            marker_color='lightblue'
        ))
        fig_tokens.add_trace(go.Bar(
            name='Managed',
            x=df_managed['Model'],
            y=df_managed['Tokens/sec'],
            marker_color='lightgreen'
        ))
        fig_tokens.update_layout(
            title='Token Throughput Comparison',
            xaxis_title='Model',
            yaxis_title='Tokens/sec',
            barmode='group'
        )
        st.plotly_chart(fig_tokens, use_container_width=True)

    # Latency percentiles comparison
    st.subheader("Latency Percentiles Comparison")

    percentile_data = []
    for env, df in [("Baseline", df_baseline), ("Managed", df_managed)]:
        for _, row in df.iterrows():
            percentile_data.extend([
                {'Environment': env, 'Model': row['Model'], 'Percentile': 'Mean', 'Latency (s)': row['Mean Latency (s)']},
                {'Environment': env, 'Model': row['Model'], 'Percentile': 'P95', 'Latency (s)': row['P95 Latency (s)']},
                {'Environment': env, 'Model': row['Model'], 'Percentile': 'P99', 'Latency (s)': row['P99 Latency (s)']},
            ])

    df_percentiles = pd.DataFrame(percentile_data)
    fig_perc = px.bar(
        df_percentiles,
        x='Model',
        y='Latency (s)',
        color='Environment',
        pattern_shape='Percentile',
        barmode='group',
        title='Latency Percentiles by Environment'
    )
    st.plotly_chart(fig_perc, use_container_width=True)

# Detailed results expander
with st.expander("🔍 View Detailed Raw Results"):
    if baseline_exists:
        st.subheader("Baseline Results")
        st.json(baseline_results)
    if managed_exists:
        st.subheader("Managed Results")
        st.json(managed_results)

# Infrastructure info
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ About")
st.sidebar.markdown("""
**Infrastructure:**
- Platform: Kubernetes (K3s)
- Load Balancing: kube-proxy (baseline) / smart LB (managed)
- GPUs: 8x L4 (6 allocated)

**Benchmark Types:**
- **Custom**: Simple OpenAI client benchmark
- **GenAI-Perf**: NVIDIA's official benchmarking tool

**Test Config:**
- 100 requests per model
- 10 concurrent requests
- 100 max tokens (custom) / variable (GenAI-Perf)
""")
