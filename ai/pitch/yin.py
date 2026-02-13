"""
YIN pitch detection algorithm for monophonic audio.

Based on:
  de Cheveigné, A. & Kawahara, H. (2002).
  "YIN, a fundamental frequency estimator for speech and music."
  JASA 111(4), 1917-1930.

The algorithm applies a cumulative mean normalized difference function
(CMND) to find the fundamental period, then refines with parabolic
interpolation for sub-sample accuracy.
"""

import numpy as np


def difference_function(frame: np.ndarray, max_lag: int) -> np.ndarray:
    """
    Step 1-2 of YIN: compute the difference function d(tau).

    d(tau) = sum_{j=0}^{W-1} (x[j] - x[j+tau])^2

    Uses the autocorrelation trick for O(N log N) via FFT instead of O(N^2).
    """
    n = len(frame)
    fft_size = 1
    while fft_size < 2 * n:
        fft_size *= 2

    # Power term: cumulative sum of squared samples
    frame_f = np.float64(frame)
    x_sq = frame_f ** 2
    cum_sum = np.concatenate(([0.0], np.cumsum(x_sq)))

    # Autocorrelation via FFT
    fft_frame = np.fft.rfft(frame_f, n=fft_size)
    acf = np.fft.irfft(fft_frame * np.conj(fft_frame))

    # d(tau) = r(0) + r_shifted(tau) - 2*r_cross(tau)
    # where the first two terms come from the cumulative sum
    diff = np.empty(max_lag + 1)
    diff[0] = 0.0
    for tau in range(1, max_lag + 1):
        # sum of x[0..W-1]^2  +  sum of x[tau..tau+W-1]^2  -  2*acf(tau)
        w = n - tau
        diff[tau] = cum_sum[w] + (cum_sum[n] - cum_sum[tau]) - 2.0 * acf[tau]

    return diff


def cmnd(diff: np.ndarray) -> np.ndarray:
    """
    Step 3: Cumulative Mean Normalized Difference.

    d'(tau) = d(tau) / ((1/tau) * sum_{j=1}^{tau} d(j))

    This normalizes d(tau) so the threshold is independent of signal level.
    d'(0) is defined as 1.
    """
    result = np.empty_like(diff)
    result[0] = 1.0
    running_sum = 0.0

    for tau in range(1, len(diff)):
        running_sum += diff[tau]
        result[tau] = diff[tau] * tau / running_sum if running_sum > 0 else 1.0

    return result


def absolute_threshold(cmnd_arr: np.ndarray, threshold: float) -> int:
    """
    Step 4: Find the first tau where CMND dips below the threshold
    and is a local minimum. Returns 0 if no pitch found.
    """
    tau = 2  # skip trivially small lags
    while tau < len(cmnd_arr) - 1:
        if cmnd_arr[tau] < threshold:
            # Walk past any equal-valued plateau to the local minimum
            while tau + 1 < len(cmnd_arr) and cmnd_arr[tau + 1] < cmnd_arr[tau]:
                tau += 1
            return tau
        tau += 1
    return 0


def parabolic_interpolation(cmnd_arr: np.ndarray, tau: int) -> float:
    """
    Step 5: Refine the period estimate with parabolic interpolation
    around the minimum for sub-sample accuracy.
    """
    if tau <= 0 or tau >= len(cmnd_arr) - 1:
        return float(tau)

    alpha = cmnd_arr[tau - 1]
    beta = cmnd_arr[tau]
    gamma = cmnd_arr[tau + 1]

    denominator = 2.0 * (alpha - 2.0 * beta + gamma)
    if abs(denominator) < 1e-12:
        return float(tau)

    return tau + (alpha - gamma) / denominator


def yin_pitch(
    frame: np.ndarray,
    sample_rate: int = 16000,
    threshold: float = 0.15,
    freq_min: float = 50.0,
    freq_max: float = 2000.0,
) -> tuple[float, float]:
    """
    Detect the fundamental frequency of a monophonic audio frame.

    Parameters
    ----------
    frame        : 1-D float array of audio samples (mono)
    sample_rate  : sample rate in Hz
    threshold    : YIN absolute-threshold (lower = stricter, 0.10-0.20 typical)
    freq_min     : lowest detectable frequency in Hz
    freq_max     : highest detectable frequency in Hz

    Returns
    -------
    (frequency_hz, confidence)
        frequency_hz : detected pitch in Hz, or 0.0 if unvoiced / silence
        confidence   : 1 - CMND value at the chosen lag (0.0 to 1.0)
    """
    n = len(frame)

    # Lag bounds from frequency bounds
    min_lag = max(2, int(sample_rate / freq_max))
    max_lag = min(n // 2, int(sample_rate / freq_min))

    if max_lag <= min_lag:
        return 0.0, 0.0

    # Silence gate: skip near-silent frames
    rms = np.sqrt(np.mean(frame.astype(np.float64) ** 2))
    if rms < 1e-4:
        return 0.0, 0.0

    # YIN steps 1-3
    diff = difference_function(frame, max_lag)
    d_prime = cmnd(diff)

    # Only search within the valid lag range
    search = d_prime.copy()
    search[:min_lag] = 1.0  # mask out lags below freq_max

    # Step 4: threshold search
    tau = absolute_threshold(search, threshold)
    if tau == 0:
        return 0.0, 0.0

    # Step 5: parabolic refinement
    refined_tau = parabolic_interpolation(d_prime, tau)
    if refined_tau <= 0:
        return 0.0, 0.0

    freq = sample_rate / refined_tau
    confidence = 1.0 - d_prime[tau]

    # Sanity check
    if freq < freq_min or freq > freq_max:
        return 0.0, 0.0

    return round(freq, 2), round(max(0.0, min(1.0, confidence)), 4)
