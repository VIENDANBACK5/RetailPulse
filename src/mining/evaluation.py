"""Observed model metrics only, with predeclared model selection and stability."""
from itertools import combinations
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from threadpoolctl import threadpool_limits
from src.mining.clustering import FEATURES, preprocess_rfm, rule_based_segments

DEFAULT_SEEDS = (42, 123, 7, 19, 31, 53, 71, 89, 101, 137)


def measured_silhouette(features, labels, indices):
    selected_labels = np.asarray(labels)[indices]
    if len(np.unique(selected_labels)) < 2 or len(np.unique(selected_labels)) >= len(indices):
        return None
    return float(silhouette_score(features[indices], selected_labels))


def evaluate_k_selection(rfm_df, k_range=range(2, 7), random_state=42,
                         output_dir=None, seeds=DEFAULT_SEEDS):
    features, _ = preprocess_rfm(rfm_df)
    if rfm_df.customer_key.duplicated().any():
        raise ValueError("Stability requires exactly one row per aligned customer")
    distinct_points = len(np.unique(features, axis=0))
    candidates = [int(k) for k in k_range if 2 <= k < len(features) and k <= distinct_points]
    if not candidates:
        raise ValueError("At least three eligible customers and two distinct RFM points are required")
    seeds = tuple(dict.fromkeys([int(random_state), *map(int, seeds)]))
    if len(seeds) < 2:
        raise ValueError("Stability evaluation requires at least two seeds")
    # Fixed customer sample shared by K values, seeds and baseline; no fabricated scores.
    indices = np.sort(np.random.default_rng(42).choice(len(features), min(1000, len(features)), replace=False))
    runs, pairwise, summary = [], [], []
    with threadpool_limits(limits=1):
        for k in candidates:
            labels_by_seed = {}
            for seed in seeds:
                model = KMeans(n_clusters=k, n_init=20, max_iter=300, random_state=seed)
                labels = model.fit_predict(features)
                if len(np.unique(labels)) != k:
                    continue
                labels_by_seed[seed] = labels
                counts = np.bincount(labels, minlength=k)
                runs.append({"k": k, "seed": seed, "inertia": float(model.inertia_),
                    "silhouette_score": measured_silhouette(features, labels, indices),
                    "cluster_sizes": counts.tolist(), "sorted_cluster_sizes": sorted(counts.tolist()),
                    "min_cluster_pct": float(counts.min() / len(features) * 100),
                    "max_cluster_pct": float(counts.max() / len(features) * 100)})
            ari_values = []
            for first, second in combinations(labels_by_seed, 2):
                ari = float(adjusted_rand_score(labels_by_seed[first], labels_by_seed[second]))
                pairwise.append({"k": k, "seed_a": first, "seed_b": second, "ari": ari})
                ari_values.append(ari)
            current = [row for row in runs if row["k"] == k]
            scores = [row["silhouette_score"] for row in current if row["silhouette_score"] is not None]
            if not scores or not ari_values:
                continue
            size_matrix = np.asarray([row["sorted_cluster_sizes"] for row in current])
            summary.append({"k": k, "inertia": float(np.mean([row["inertia"] for row in current])),
                "inertia_std": float(np.std([row["inertia"] for row in current])),
                "silhouette_score": float(np.mean(scores)), "silhouette_std": float(np.std(scores)),
                "min_cluster_pct": min(row["min_cluster_pct"] for row in current),
                "max_cluster_pct": max(row["max_cluster_pct"] for row in current),
                "stability_ari_mean": float(np.mean(ari_values)), "stability_ari_min": float(min(ari_values)),
                "cluster_size_rank_std": size_matrix.std(axis=0).tolist(),
                "seed_count": len(current), "pair_count": len(ari_values)})
    if not summary:
        raise ValueError("No valid clustering evaluation; check duplicate or constant RFM features")
    # The guard is an analysis policy, never a claim that these thresholds guarantee quality.
    eligible = [row for row in summary if row["min_cluster_pct"] >= 1 and row["stability_ari_mean"] >= .8]
    pool = eligible or summary
    chosen = sorted(pool, key=lambda row: (-row["silhouette_score"], row["k"]))[0]
    baseline, thresholds = rule_based_segments(rfm_df)
    baseline_labels, names = pd.factorize(baseline.baseline_segment, sort=True)
    baseline_score = measured_silhouette(features, baseline_labels, indices)
    result = {"k_values": [r["k"] for r in summary], "recommended_k": chosen["k"],
        "selection_rule": "Max mean silhouette among K with minimum cluster >=1% at every seed and mean pairwise ARI>=0.8; tie: lower K. If none qualifies, highest mean silhouette with warning.",
        "selection_warning": None if eligible else "No candidate meets stability/size guard; conclusions exploratory",
        "summary_table": summary, "seed_runs": runs, "pairwise_ari": pairwise,
        "seeds": list(seeds), "n_init": 20, "silhouette_sample_customers": len(indices),
        "baseline": {"method": "observation-cohort median rules v1", "thresholds": thresholds,
            "silhouette_same_feature_space": baseline_score,
            "segment_sizes": baseline.baseline_segment.value_counts().to_dict()},
        "inertias": [r["inertia"] for r in summary],
        "silhouette_scores": [r["silhouette_score"] for r in summary]}
    if output_dir is not None:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(summary).to_csv(directory / "k_comparison_summary.csv", index=False)
        pd.DataFrame(runs).to_csv(directory / "seed_metrics.csv", index=False)
        pd.DataFrame(pairwise).to_csv(directory / "pairwise_ari.csv", index=False)
        (directory / "evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        axes[0].errorbar(result["k_values"], result["inertias"], yerr=[r["inertia_std"] for r in summary], marker="o")
        axes[0].set(title="K-means inertia: 10 seed experiments", xlabel="K", ylabel="Inertia")
        axes[1].errorbar(result["k_values"], result["silhouette_scores"], yerr=[r["silhouette_std"] for r in summary], marker="o")
        axes[1].set(title="Silhouette in log-scaled RFM", xlabel="K", ylabel="Silhouette")
        fig.tight_layout()
        plot_path = directory / "elbow_silhouette.png"
        fig.savefig(plot_path, dpi=150)
        plt.close(fig)
        result["plot_path"] = str(plot_path)
    return result


def save_eda(rfm_df, output_dir):
    directory = Path(output_dir)
    summary = {"customer_count": len(rfm_df), "missing": rfm_df[FEATURES].isna().sum().to_dict(),
        "distribution": rfm_df[FEATURES].describe().to_dict(),
        "correlation": rfm_df[FEATURES].corr().fillna(0).to_dict(),
        "outlier_policy": "Retain all eligible customers; IQR flagged for reporting only", "iqr_outliers": {}}
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for col, feature in enumerate(FEATURES):
        values = rfm_df[feature]
        q1, q3 = values.quantile([.25, .75])
        summary["iqr_outliers"][feature] = int(((values < q1-1.5*(q3-q1)) | (values > q3+1.5*(q3-q1))).sum())
        axes[0, col].hist(values, bins=40)
        axes[0, col].set_title(f"Original {feature}")
        axes[1, col].hist(np.log1p(values), bins=40)
        axes[1, col].set_title(f"log1p {feature}")
    fig.tight_layout()
    fig.savefig(directory / "rfm_distributions.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(5, 4))
    image = ax.imshow(rfm_df[FEATURES].corr().fillna(0), vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(3), FEATURES)
    ax.set_yticks(range(3), FEATURES)
    fig.colorbar(image)
    fig.tight_layout()
    fig.savefig(directory / "rfm_correlation.png", dpi=150)
    plt.close(fig)
    (directory / "eda.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
