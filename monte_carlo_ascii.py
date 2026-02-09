"""Monte Carlo pi estimation with ASCII terminal graph."""

import math
import numpy as np


def run_simulation(total_samples, num_checkpoints=60):
    """Run Monte Carlo incrementally with adaptive chunk sizes."""
    # Include exact powers of 10 as checkpoints
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
            pi_est = 4.0 * inside_circle / generated
            results.append((generated, pi_est, max(abs(pi_est - math.pi), 1e-15)))
            continue
        # Use numpy for large chunks, plain loop for small
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
        results.append((generated, pi_est, max(error, 1e-15)))

    return results


def ascii_plot(results, width=58, height=20):
    """Draw a log-log ASCII scatter plot."""
    samples = [r[0] for r in results]
    errors  = [r[2] for r in results]

    log_s = [math.log10(max(s, 1)) for s in samples]
    log_e = [math.log10(e) for e in errors]

    x_min, x_max = min(log_s), max(log_s)
    y_min = math.floor(min(log_e))
    y_max = math.ceil(max(log_e))

    if x_max == x_min:
        x_max = x_min + 1

    grid = [[' '] * width for _ in range(height)]

    # Plot measured error
    for lx, ly in zip(log_s, log_e):
        col = int((lx - x_min) / (x_max - x_min) * (width - 1))
        row = int((1 - (ly - y_min) / (y_max - y_min)) * (height - 1))
        col = max(0, min(width - 1, col))
        row = max(0, min(height - 1, row))
        grid[row][col] = '*'

    # Plot theoretical O(1/sqrt(N))
    for i in range(width):
        lx = x_min + (x_max - x_min) * i / (width - 1)
        ly = -0.5 * lx
        if y_min <= ly <= y_max:
            row = int((1 - (ly - y_min) / (y_max - y_min)) * (height - 1))
            if 0 <= row < height and grid[row][i] == ' ':
                grid[row][i] = '.'

    # Print graph
    print()
    print("  Monte Carlo π — Error vs Samples (log-log)")
    print("  * = measured   . = O(1/√N) theory")
    print()

    for r in range(height):
        y_val = y_max - (y_max - y_min) * r / (height - 1)
        if abs(y_val - round(y_val)) < 0.05:
            label = f"1e{int(round(y_val))}"
        else:
            label = ""
        print(f" {label:>5} |{''.join(grid[r])}|")

    print(f" {'':>5} +{'-' * width}+")
    print(f" {'':>5}  10^{x_min:<5.0f}{' ' * (width - 16)}10^{x_max:.0f}")
    print(f" {'':>5}  {'Number of samples':^{width}}")

    # Summary table at powers of 10
    print()
    powers = {10**i for i in range(11)}
    table = [(s, pi, e) for s, pi, e in results if s in powers]
    if table:
        print(f"  {'N':>12}  {'π estimate':>14}  {'|error|':>12}")
        print(f"  {'─'*12}  {'─'*14}  {'─'*12}")
        for s, pi_est, e in table:
            print(f"  {s:>12,}  {pi_est:>14.8f}  {e:>12.8f}")
    print()


def main():
    total = 100_000_000
    print(f"\n  Computing {total:,} samples...")
    results = run_simulation(total, num_checkpoints=80)
    ascii_plot(results)


if __name__ == "__main__":
    main()
