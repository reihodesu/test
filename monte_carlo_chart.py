"""Generate an interactive HTML chart for Monte Carlo pi estimation."""

import math
import json
import numpy as np


def run_simulation(total_samples, num_checkpoints=80):
    powers_of_10 = [10**i for i in range(11) if 10**i <= total_samples]
    checkpoints = sorted(set(
        np.geomspace(1, total_samples, num_checkpoints).astype(int).tolist()
        + powers_of_10
    ))

    inside_circle = 0
    generated = 0
    results = []

    for cp in checkpoints:
        need = cp - generated
        if need <= 0:
            continue
        if need > 1000:
            x = np.random.random(need)
            y = np.random.random(need)
            inside_circle += int(np.sum(x * x + y * y <= 1.0))
        else:
            for _ in range(need):
                x, y = np.random.random(), np.random.random()
                if x * x + y * y <= 1.0:
                    inside_circle += 1
        generated = cp
        pi_est = 4.0 * inside_circle / generated
        error = abs(pi_est - math.pi)
        results.append({"n": int(generated), "pi": round(pi_est, 10), "error": max(error, 1e-15)})

    return results


def generate_html(results, output_path="monte_carlo_chart.html"):
    # Theoretical line
    theory = [{"n": r["n"], "error": 1.0 / math.sqrt(r["n"])} for r in results]

    powers = {10**i for i in range(11)}
    table_rows = "".join(
        f'<tr><td>{r["n"]:,}</td><td>{r["pi"]:.8f}</td><td>{r["error"]:.8f}</td></tr>'
        for r in results if r["n"] in powers
    )

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monte Carlo π</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body {{
    margin: 0; padding: 16px;
    background: #1a1a2e; color: #eee;
    font-family: -apple-system, sans-serif;
  }}
  h2 {{ text-align: center; font-size: 1.1em; margin-bottom: 4px; }}
  p  {{ text-align: center; font-size: 0.85em; color: #aaa; margin-top: 0; }}
  .chart-wrap {{ position: relative; width: 100%; max-width: 700px; margin: 0 auto; }}
  table {{
    margin: 20px auto; border-collapse: collapse;
    font-size: 0.85em; width: 90%; max-width: 500px;
  }}
  th, td {{ padding: 6px 10px; border-bottom: 1px solid #333; text-align: right; }}
  th {{ color: #aaa; font-weight: normal; }}
</style>
</head>
<body>
<h2>Monte Carlo π Estimation</h2>
<p>Error convergence — log-log scale</p>
<div class="chart-wrap">
  <canvas id="chart"></canvas>
</div>

<table>
  <tr><th>N</th><th>π estimate</th><th>|error|</th></tr>
  {table_rows}
</table>

<script>
const measured = {json.dumps([{"x": r["n"], "y": r["error"]} for r in results])};
const theory  = {json.dumps([{"x": t["n"], "y": t["error"]} for t in theory])};

new Chart(document.getElementById('chart'), {{
  type: 'scatter',
  data: {{
    datasets: [
      {{
        label: 'Measured error',
        data: measured,
        backgroundColor: 'rgba(33,150,243,0.7)',
        pointRadius: 3,
      }},
      {{
        label: 'O(1/√N) theory',
        data: theory,
        borderColor: 'rgba(244,67,54,0.8)',
        backgroundColor: 'transparent',
        pointRadius: 0,
        borderWidth: 2,
        showLine: true,
        borderDash: [6, 3],
      }}
    ]
  }},
  options: {{
    responsive: true,
    scales: {{
      x: {{
        type: 'logarithmic',
        title: {{ display: true, text: 'Samples (N)', color: '#aaa' }},
        grid: {{ color: 'rgba(255,255,255,0.08)' }},
        ticks: {{ color: '#aaa' }}
      }},
      y: {{
        type: 'logarithmic',
        title: {{ display: true, text: '|π estimate − π|', color: '#aaa' }},
        grid: {{ color: 'rgba(255,255,255,0.08)' }},
        ticks: {{ color: '#aaa' }}
      }}
    }},
    plugins: {{
      legend: {{ labels: {{ color: '#ccc' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"Chart saved to {output_path}")


def main():
    total = 100_000_000
    print(f"Computing {total:,} samples...")
    results = run_simulation(total, num_checkpoints=80)
    generate_html(results)


if __name__ == "__main__":
    main()
