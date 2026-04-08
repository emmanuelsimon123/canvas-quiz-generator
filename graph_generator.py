import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
import types
from simpleeval import SimpleEval

def generate_graph(graph_data):
    fig, ax = plt.subplots(1, 1, figsize=(6, 4), dpi=150)

    equations = graph_data.get("equations", [])
    x_range = graph_data.get("x_range", [-10, 10])
    y_range = graph_data.get("y_range", None)
    title = graph_data.get("title", "")
    labels = graph_data.get("labels", [])
    show_points = graph_data.get("show_points", [])

    x = np.linspace(x_range[0], x_range[1], 2000)

    colors = ['#2196F3', '#F44336', '#4CAF50', '#FF9800', '#9C27B0']

    _np = types.SimpleNamespace(
        sin=np.sin, cos=np.cos, tan=np.tan,
        sqrt=np.sqrt, abs=np.abs, log=np.log,
        log10=np.log10, exp=np.exp, pi=np.pi, e=np.e,
    )
    safe_names = {
        "x": x,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "sqrt": np.sqrt, "abs": np.abs, "log": np.log,
        "log10": np.log10, "exp": np.exp, "pi": np.pi,
        "e": np.e,
        "np": _np,
    }

    equation_plotted = False

    for i, eq in enumerate(equations):
        try:
            evaluator = SimpleEval()
            evaluator.names = safe_names
            y = evaluator.eval(eq)

            if not hasattr(y, '__len__'):
                y = np.full_like(x, y)

            y = np.array(y, dtype=float)

            # Only handle true asymptotes (like tan), not regular lines
            if "tan" in eq or "1/" in eq or "/x" in eq:
                dy = np.diff(y)
                large_jumps = np.abs(dy) > 50
                y[1:][large_jumps] = np.nan

            # Clip extreme values to keep graph readable
            if y_range:
                clip_min = y_range[0] - 10
                clip_max = y_range[1] + 10
            else:
                clip_min = -100
                clip_max = 100
            y = np.clip(y, clip_min, clip_max)

            label = labels[i] if i < len(labels) else None
            ax.plot(x, y, color=colors[i % len(colors)], linewidth=2.5, label=label)
            equation_plotted = True
        except Exception:
            continue

    # If no equation was plotted but we have points, connect them with a line
    if not equation_plotted and len(show_points) >= 2:
        try:
            px = [p.get("x", 0) for p in show_points]
            py = [p.get("y", 0) for p in show_points]

            # Sort by x
            sorted_pairs = sorted(zip(px, py))
            px = [p[0] for p in sorted_pairs]
            py = [p[1] for p in sorted_pairs]

            # Extend the line beyond the points to fill the graph
            if len(px) == 2:
                slope = (py[1] - py[0]) / (px[1] - px[0]) if px[1] != px[0] else None
                if slope is not None:
                    x_extended = np.linspace(x_range[0], x_range[1], 2000)
                    y_extended = py[0] + slope * (x_extended - px[0])
                    ax.plot(x_extended, y_extended, color=colors[0], linewidth=2.5)
                else:
                    ax.axvline(x=px[0], color=colors[0], linewidth=2.5)
            else:
                ax.plot(px, py, color=colors[0], linewidth=2.5)

            equation_plotted = True
        except Exception:
            pass

    # Even if equation plotted, if we have 2+ points try connecting with a line as backup
    if equation_plotted and not equations and len(show_points) >= 2:
        pass  # Already handled above

    # Plot specific points
    for point in show_points:
        try:
            px, py = point.get("x", 0), point.get("y", 0)
            point_label = point.get("label", "")
            ax.plot(px, py, 'o', color='#F44336', markersize=8, zorder=5)
            if point_label:
                ax.annotate(point_label, (px, py), textcoords="offset points",
                          xytext=(10, 10), fontsize=10, fontweight='bold')
        except Exception:
            continue

    # Styling
    ax.set_xlabel("x", fontsize=12)
    ax.set_ylabel("y", fontsize=12)
    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axhline(y=0, color='black', linewidth=0.8)
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.grid(True, alpha=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    if y_range:
        ax.set_ylim(y_range)

    if labels and any(labels):
        ax.legend(fontsize=10)

    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode()