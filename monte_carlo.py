"""Monte Carlo simulation to estimate the value of pi."""

import random


def estimate_pi(num_samples: int) -> float:
    """Estimate pi using the Monte Carlo method.

    Randomly scatter points in a 1x1 square and count how many fall
    inside a quarter circle of radius 1. The ratio approximates pi/4.

    Args:
        num_samples: Number of random points to generate.

    Returns:
        Estimated value of pi.
    """
    inside_circle = 0

    for _ in range(num_samples):
        x = random.random()
        y = random.random()
        if x * x + y * y <= 1.0:
            inside_circle += 1

    return 4.0 * inside_circle / num_samples


def main() -> None:
    sample_sizes = [1_000, 10_000, 100_000, 1_000_000]

    print("Monte Carlo Pi Estimation")
    print("-" * 40)
    print(f"{'Samples':>12}  {'Estimated Pi':>14}  {'Error':>10}")
    print("-" * 40)

    for n in sample_sizes:
        pi_estimate = estimate_pi(n)
        error = abs(pi_estimate - 3.141592653589793)
        print(f"{n:>12,}  {pi_estimate:>14.6f}  {error:>10.6f}")


if __name__ == "__main__":
    main()
