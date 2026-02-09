"""Monte Carlo simulation to estimate the value of pi."""

import math
import numpy as np
import matplotlib.pyplot as plt


def estimate_pi(num_samples: int) -> float:
    """Estimate pi using the Monte Carlo method.

    Args:
        num_samples: Number of random points to generate.

    Returns:
        Estimated value of pi.
    """
    inside_circle = 0
    for _ in range(num_samples):
        x, y = np.random.random(), np.random.random()
        if x * x + y * y <= 1.0:
            inside_circle += 1
    return 4.0 * inside_circle / num_samples


def run_incremental(total_samples: int, num_checkpoints: int = 200):
    """Run Monte Carlo incrementally, recording error at log-spaced checkpoints.

    Uses numpy chunks for speed and accumulates results to avoid redundant work.
    """
    checkpoints = np.unique(np.geomspace(1, total_samples, num_checkpoints).astype(int))
    chunk_size = 10_000_000  # process 10M points at a time

    inside_circle = 0
    generated = 0
    results_n = []
    results_error = []
    cp_idx = 0

    while generated < total_samples and cp_idx < len(checkpoints):
        # Generate a chunk, but don't overshoot total
        remaining = total_samples - generated
        n = min(chunk_size, remaining)
        x = np.random.random(n)
        y = np.random.random(n)
        inside_circle += int(np.sum(x * x + y * y <= 1.0))
        generated += n

        # Record any checkpoints we've passed
        while cp_idx < len(checkpoints) and checkpoints[cp_idx] <= generated:
            pi_est = 4.0 * inside_circle / generated
            error = abs(pi_est - math.pi)
            results_n.append(generated)
            results_error.append(error)
            cp_idx += 1

        if generated % 100_000_000 == 0:
            print(f"  {generated:>14,} / {total_samples:,}  "
                  f"pi ≈ {4.0 * inside_circle / generated:.8f}")

    return np.array(results_n), np.array(results_error)


def plot_error(samples, errors, output_path="monte_carlo_error.png"):
    """Plot pi estimation error vs sample size on a log-log scale."""
    fig, ax = plt.subplots(figsize=(12, 7))

    ax.loglog(samples, errors, color="#2196F3", linewidth=0.8, alpha=0.8, label="Measured error")

    # Theoretical 1/sqrt(N) convergence line
    ref_x = np.array([samples[0], samples[-1]])
    ref_y = 1.0 / np.sqrt(ref_x)
    ax.loglog(ref_x, ref_y, "--", color="#F44336", linewidth=1.5,
              label=r"Theoretical $O(1/\sqrt{N})$")

    ax.set_xlabel("Number of samples", fontsize=13)
    ax.set_ylabel("|Estimated π − π|", fontsize=13)
    ax.set_title("Monte Carlo π Estimation — Error Convergence (1 to 10¹⁰)", fontsize=15)
    ax.legend(fontsize=12)
    ax.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    print(f"\nGraph saved to {output_path}")


def main() -> None:
    total = 10_000_000_000  # 10^10
    print(f"Monte Carlo Pi Estimation — {total:,} samples")
    print("=" * 50)

    samples, errors = run_incremental(total, num_checkpoints=300)
    plot_error(samples, errors)

    pi_final = math.pi  # just for display
    final_est = 4.0  # recalc not needed, last error is enough
    print(f"\nFinal error at 10^10 samples: {errors[-1]:.10f}")


if __name__ == "__main__":
    main()
