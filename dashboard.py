import subprocess
import json
import time

import pandas as pd
import streamlit as st


def run_cmd(cmd, cwd=None):
    """
    Run a shell command and return (stdout, stderr, returncode).
    """
    try:
        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        st.error(f"Command failed: {' '.join(cmd)}\n{e}")
        return "", str(e), 1


K3D_CLUSTER_NAME = "myk3s"
LAB_DIR = "/home/ubuntu/k3s-lab/k3s-lab"  # adjust if your repo lives elsewhere


def k3d_cluster_start():
    return run_cmd(["k3d", "cluster", "start", K3D_CLUSTER_NAME])


def k3d_cluster_stop():
    return run_cmd(["k3d", "cluster", "stop", K3D_CLUSTER_NAME])


def restart_microservices():
    # roll out restart of all nginx microservices
    return run_cmd([
        "kubectl", "rollout", "restart",
        "deployment", "-n", "default",
        "-l", "app=nginx-svc-"
    ])


def run_ansible_lab():
    # run your existing bash run.sh in the repo directory
    return run_cmd(["bash", "run.sh"], cwd=LAB_DIR)




def get_pods(namespace="default"):
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
    out = run_cmd(cmd)
    if not out:
        return pd.DataFrame()

    data = json.loads(out)
    rows = []
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})
        labels = meta.get("labels", {})

        rows.append({
            "microservice": labels.get("app", ""),
            "svc_id": labels.get("svc-id", ""),
            "pod": meta.get("name", ""),
            "node": spec.get("nodeName", ""),
            "phase": status.get("phase", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["microservice", "pod"])
    return df


def parse_resource_value(v):
    """
    Parse K8s style resource values like 123m, 100Mi, 512Ki.
    Return numeric core for cpu, bytes for memory.
    """
    if v is None or v == "":
        return 0.0

    v = str(v)

    # CPU
    if v.endswith("m"):
        return float(v[:-1]) / 1000.0
    if v.replace(".", "", 1).isdigit():
        return float(v)

    # Memory
    multipliers = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "K": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
    }

    for suffix, mult in multipliers.items():
        if v.endswith(suffix):
            try:
                return float(v[:-len(suffix)]) * mult
            except ValueError:
                return 0.0

    return 0.0


def get_node_info():
    # Basic node info
    cmd = ["kubectl", "get", "nodes", "-o", "json"]
    out = run_cmd(cmd)
    if not out:
        return pd.DataFrame(), pd.DataFrame()

    data = json.loads(out)
    rows = []
    for item in data.get("items", []):
        meta = item.get("metadata", {})
        status = item.get("status", {})
        name = meta.get("name", "")
        capacity = status.get("capacity", {})
        alloc = status.get("allocatable", {})

        rows.append({
            "node": name,
            "cpu_capacity_cores": parse_resource_value(capacity.get("cpu")),
            "mem_capacity_bytes": parse_resource_value(capacity.get("memory")),
            "cpu_alloc_cores": parse_resource_value(alloc.get("cpu")),
            "mem_alloc_bytes": parse_resource_value(alloc.get("memory")),
        })

    base_df = pd.DataFrame(rows)

    # Metrics from kubectl top nodes (if metrics server is available)
    cmd = ["kubectl", "top", "nodes", "--no-headers"]
    top_out = run_cmd(cmd)
    metric_rows = []
    if top_out:
        for line in top_out.splitlines():
            parts = line.split()
            if len(parts) >= 5:
                # NAME CPU(cores) CPU% MEMORY(bytes) MEMORY%
                node_name = parts[0]
                cpu_cores = parts[1]
                cpu_pct = parts[2]
                mem_bytes = parts[3]
                mem_pct = parts[4]
                metric_rows.append({
                    "node": node_name,
                    "cpu_used_cores_raw": cpu_cores,
                    "cpu_used_cores": parse_resource_value(cpu_cores),
                    "cpu_used_pct": cpu_pct,
                    "mem_used_bytes_raw": mem_bytes,
                    "mem_used_bytes": parse_resource_value(mem_bytes),
                    "mem_used_pct": mem_pct,
                })

    metrics_df = pd.DataFrame(metric_rows)
    if not base_df.empty and not metrics_df.empty:
        merged = pd.merge(base_df, metrics_df, on="node", how="left")
    else:
        merged = base_df

    return merged, metrics_df


def main():
    st.sidebar.header("Controls")
    interval = st.sidebar.slider("Auto refresh interval (seconds)", 5, 60, 10)
    st.sidebar.write("Last refresh:", time.strftime("%H:%M:%S"))

    st.sidebar.markdown("### Cluster actions")

    if st.sidebar.button("Start cluster"):
        out, err, rc = k3d_cluster_start()
        st.sidebar.write(f"Start cluster exit code: {rc}")
        if out:
            st.sidebar.code(out, language="bash")
        if err:
            st.sidebar.code(err, language="bash")

    if st.sidebar.button("Stop cluster"):
        out, err, rc = k3d_cluster_stop()
        st.sidebar.write(f"Stop cluster exit code: {rc}")
        if out:
            st.sidebar.code(out, language="bash")
        if err:
            st.sidebar.code(err, language="bash")

    if st.sidebar.button("Restart microservices"):
        out, err, rc = restart_microservices()
        st.sidebar.write(f"Restart microservices exit code: {rc}")
        if out:
            st.sidebar.code(out, language="bash")
        if err:
            st.sidebar.code(err, language="bash")

    st.sidebar.markdown("### Lab bootstrap")

    if st.sidebar.button("Run bash run.sh"):
        st.sidebar.write("Running bash run.sh, this may take a while...")
        out, err, rc = run_ansible_lab()
        st.sidebar.write(f"run.sh exit code: {rc}")
        if out:
            st.sidebar.code(out, language="bash")
        if err:
            st.sidebar.code(err, language="bash")


    # Load data
    pods_df = get_pods("default")
    nodes_df, metrics_df = get_node_info()

    if pods_df.empty:
        st.error("No pods found in namespace 'default'. Is the cluster up and nginx services deployed?")
        return

    # Summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Microservices", pods_df["microservice"].nunique())
    with col2:
        st.metric("Pods (default ns)", len(pods_df))
    with col3:
        st.metric("Nodes", nodes_df["node"].nunique() if not nodes_df.empty else 0)

    st.markdown("### Node overview")

    if not nodes_df.empty:
        display_df = nodes_df.copy()
        # add human readable memory fields
        display_df["mem_capacity_GiB"] = (display_df["mem_capacity_bytes"] / (1024**3)).round(2)
        if "mem_used_bytes" in display_df.columns:
            display_df["mem_used_GiB"] = (display_df["mem_used_bytes"] / (1024**3)).round(2)
        st.dataframe(display_df.set_index("node"))
    else:
        st.warning("Could not load node info. Check kubectl access.")

    st.markdown("### Microservices by node")

    # Group microservices per node
    ms_node_df = pods_df.groupby(["node", "microservice"]).size().reset_index(name="pods")
    pivot = ms_node_df.pivot(index="node", columns="microservice", values="pods").fillna(0).astype(int)
    st.dataframe(pivot)

    st.markdown("### Microservice instances")

    with st.expander("Pod level view"):
        st.dataframe(pods_df)

    st.markdown("### Pods per node")

    pods_per_node = pods_df.groupby("node").size().reset_index(name="pod_count")
    st.bar_chart(data=pods_per_node, x="node", y="pod_count")

    st.sidebar.info("Tip: run `streamlit run dashboard.py` and open the URL from your host browser.")

    # Trigger periodic refresh
    st.rerun()


if __name__ == "__main__":
    main()

