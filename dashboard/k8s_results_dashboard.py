import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
from pathlib import Path

st.set_page_config(page_title="K8s Baseline Benchmark Results", layout="wide")

st.title("🚀 Kubernetes Baseline vLLM Benchmark Results")

# Load K8s benchmark results
results_file = Path("../results/baseline/k8s/all-models-results.json")

if not results_file.exists():
    st.error(f"Results file not found: {results_file}")
    st.stop()

with open(results_file) as f:
    results = json.load(f)

# Display summary
st.header("📊 Overview")
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Total Models Tested", len(results))
with col2:
    total_requests = sum(r['total_requests'] for r in results)
    st.metric("Total Requests", total_requests)
with col3:
    avg_success_rate = sum(r['successful_requests']/r['total_requests'] for r in results) / len(results) * 100
    st.metric("Avg Success Rate", f"{avg_success_rate:.1f}%")

# Model comparison
st.header("📈 Model Performance Comparison")

# Prepare data for comparison
comparison_data = []
for result in results:
    model_short_name = result['model'].split('/')[-1]
    comparison_data.append({
        'Model': model_short_name,
        'Requests/sec': result['requests_per_second'],
        'Mean Latency (s)': result['latency']['mean'],
        'P95 Latency (s)': result['latency']['p95'],
        'P99 Latency (s)': result['latency']['p99'],
        'Tokens/sec': result['throughput_tokens_per_sec']['total'],
        'Success Rate %': (result['successful_requests']/result['total_requests']) * 100
    })

df_comparison = pd.DataFrame(comparison_data)

# Display metrics table
st.dataframe(df_comparison, use_container_width=True)

# Visualizations
col1, col2 = st.columns(2)

with col1:
    # Throughput comparison
    fig_throughput = px.bar(
        df_comparison,
        x='Model',
        y='Requests/sec',
        title="Requests per Second",
        color='Model',
        text='Requests/sec'
    )
    fig_throughput.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig_throughput.update_layout(showlegend=False)
    st.plotly_chart(fig_throughput, use_container_width=True)

with col2:
    # Latency comparison
    fig_latency = px.bar(
        df_comparison,
        x='Model',
        y='Mean Latency (s)',
        title="Mean Latency (seconds)",
        color='Model',
        text='Mean Latency (s)'
    )
    fig_latency.update_traces(texttemplate='%{text:.2f}', textposition='outside')
    fig_latency.update_layout(showlegend=False)
    st.plotly_chart(fig_latency, use_container_width=True)

col3, col4 = st.columns(2)

with col3:
    # Token throughput
    fig_tokens = px.bar(
        df_comparison,
        x='Model',
        y='Tokens/sec',
        title="Token Throughput (tokens/sec)",
        color='Model',
        text='Tokens/sec'
    )
    fig_tokens.update_traces(texttemplate='%{text:.0f}', textposition='outside')
    fig_tokens.update_layout(showlegend=False)
    st.plotly_chart(fig_tokens, use_container_width=True)

with col4:
    # Latency percentiles
    latency_perc_data = []
    for _, row in df_comparison.iterrows():
        latency_perc_data.append({'Model': row['Model'], 'Percentile': 'Mean', 'Latency (s)': row['Mean Latency (s)']})
        latency_perc_data.append({'Model': row['Model'], 'Percentile': 'P95', 'Latency (s)': row['P95 Latency (s)']})
        latency_perc_data.append({'Model': row['Model'], 'Percentile': 'P99', 'Latency (s)': row['P99 Latency (s)']})
    
    df_latency_perc = pd.DataFrame(latency_perc_data)
    fig_perc = px.bar(
        df_latency_perc,
        x='Model',
        y='Latency (s)',
        color='Percentile',
        barmode='group',
        title="Latency Percentiles Comparison"
    )
    st.plotly_chart(fig_perc, use_container_width=True)

# Detailed model results
st.header("🔍 Detailed Results by Model")

for result in results:
    model_name = result['model']
    with st.expander(f"📦 {model_name}"):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Requests", result['total_requests'])
            st.metric("Successful", result['successful_requests'])
            st.metric("Failed", result['failed_requests'])
        
        with col2:
            st.metric("Total Time", f"{result['total_time']:.2f}s")
            st.metric("Requests/sec", f"{result['requests_per_second']:.2f}")
        
        with col3:
            st.metric("Mean Latency", f"{result['latency']['mean']:.3f}s")
            st.metric("Median Latency", f"{result['latency']['median']:.3f}s")
            st.metric("Min Latency", f"{result['latency']['min']:.3f}s")
            st.metric("Max Latency", f"{result['latency']['max']:.3f}s")
        
        with col4:
            st.metric("P95 Latency", f"{result['latency']['p95']:.3f}s")
            st.metric("P99 Latency", f"{result['latency']['p99']:.3f}s")
            st.metric("Total Tokens", result['tokens']['total'])
            st.metric("Tokens/sec", f"{result['throughput_tokens_per_sec']['total']:.2f}")
        
        st.json(result)

# Infrastructure info
st.header("⚙️ Infrastructure")
st.markdown("""
- **Platform**: Kubernetes (K3s v1.34.3)
- **GPUs**: 8x L4 GPUs (6 allocated)
- **Load Balancing**: Native kube-proxy (ClusterIP Services)
- **Test Configuration**: 100 requests, 10 concurrent, 100 max tokens
""")
