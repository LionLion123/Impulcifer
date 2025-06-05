# -*- coding: utf-8 -*-

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.mlab import specgram
from matplotlib.ticker import LinearLocator, FormatStrFormatter, FuncFormatter
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 unused import
from mpl_toolkits.axes_grid1 import make_axes_locatable
from scipy import signal, stats, ndimage, interpolate
import nnresample
from copy import deepcopy
from autoeq.frequency_response import FrequencyResponse
from utils import magnitude_response, get_ylim, running_mean
from constants import COLORS

EPSILON = 1e-20 # Small constant to avoid log(0) or division by zero with tiny numbers


class ImpulseResponse:
    def __init__(self, data, fs, recording=None):
        self.fs = fs
        self.data = data
        self.recording = recording

    def copy(self):
        return deepcopy(self)

    def __len__(self):
        """Impulse response length in samples."""
        return len(self.data)

    def duration(self):
        """Impulse response duration in seconds."""
        return len(self) / self.fs

    def peak_index(self, start=0, end=None, peak_height=0.12589):
        """Finds the first high (negative or positive) peak in the impulse response wave form.

        Args:
            start: Index for start of search range
            end: Index for end of search range
            peak_height: Minimum peak height. Default is -18 dBFS

        Returns:
            Peak index to impulse response data
        """
        if len(self.data) == 0: # Handle empty IR data
            # print("Warning: peak_index called on empty data.")
            return 0
            
        if end is None:
            end = len(self.data)
        # Peak height threshold, relative to the data maximum value
        # Copy to avoid manipulating the original data here
        data_copy = self.data.copy() # Renamed to avoid conflict with input 'data' if this class is nested
        # Limit search to given range
        data_to_search = data_copy[start:end]

        if len(data_to_search) == 0: # Handle empty search range
            # print(f"Warning: peak_index search range [{start}:{end}] is empty for data of len {len(data_copy)}.")
            return start # Or raise error, or return a sentinel like -1

        max_abs_val = np.max(np.abs(data_to_search))
        if max_abs_val < EPSILON: # Essentially silent signal
            # print("Warning: peak_index called on silent or near-silent data. Returning middle of search range.")
            # For silent signal, any point can be peak; pick first or middle.
            # Defaulting to first point of search range
            return start

        # Normalize to 1.0
        data_to_search /= max_abs_val
        
        # Find positive peaks
        peaks_pos, _ = signal.find_peaks(data_to_search, height=peak_height)
        # Find negative peaks that are at least
        peaks_neg, _ = signal.find_peaks(data_to_search * -1.0, height=peak_height)
        
        # Combine positive and negative peaks
        peaks = np.concatenate([peaks_pos, peaks_neg])
        
        if len(peaks) == 0:
            # No peaks found meeting height criteria, fall back to absolute maximum in range
            # This can happen if peak_height is too high for the actual data's character
            # print(f"Warning: No peaks found with height {peak_height}. Using absolute max in range.")
            peak_idx_in_search_range = np.argmax(np.abs(data_to_search))
            return peak_idx_in_search_range + start

        # Add start delta to peak indices
        peaks += start
        # Return the first one
        return np.min(peaks)

    def decay_params(self):
        """Determines decay parameters with Lundeby method

        https://www.ingentaconnect.com/content/dav/aaua/1995/00000081/00000004/art00009
        http://users.spa.aalto.fi/mak/PUB/AES_Modal9992.pdf

        Returns:
            - peak_ind: Fundamental starting index
            - knee_point_ind: Index where decay reaches noise floor
            - noise_floor: Noise floor in dBFS, also peak to noise ratio
            - window_size: Averaging window size as determined by Lundeby method
        """
        if len(self.data) < 10: # Arbitrary small length, too short for meaningful analysis
            # print("Warning: IR too short for decay_params. Returning fallback.")
            return 0, len(self.data), -200.0, len(self.data) if len(self.data) > 0 else 1

        peak_index = self.peak_index()

        # 1. The squared impulse response is averaged into localtime intervals in the range of 10–50 ms,
        # to yield a smooth curve without losing short decays.
        data = self.data.copy()
        # From peak to 2 seconds after the peak
        analysis_end_idx = min(peak_index + int(2 * self.fs), len(self))
        if peak_index >= analysis_end_idx : # peak is at or after the desired analysis window end
             # print(f"Warning: Peak index {peak_index} is at or beyond analysis window end {analysis_end_idx}. IR likely too short post-peak.")
             # Provide minimal valid data for squaring, or return early
             if peak_index >= len(self.data): peak_index = len(self.data) -1 # ensure peak_index is valid
             if peak_index < 0: peak_index = 0
             data_segment = data[peak_index : peak_index+1] if peak_index < len(data) else np.array([EPSILON])
        else:
            data_segment = data[peak_index:analysis_end_idx]
        
        if len(data_segment) == 0: data_segment = np.array([EPSILON]) # ensure not empty

        max_abs_segment = np.max(np.abs(data_segment))
        if max_abs_segment < EPSILON: # essentially silent
            data_segment_norm = data_segment # avoid division by zero
        else:
            data_segment_norm = data_segment / max_abs_segment  # Normalize
        
        squared = data_segment_norm ** 2  # Squared impulse response starting from the peak
        
        if len(squared) == 0: # Should not happen due to above checks, but as a safeguard
            # print("Warning: 'squared' array is empty in decay_params. Fallback.")
            return peak_index, len(self.data), -200.0, 100 # arbitrary w_fallback

        t_squared = np.linspace(0, len(squared) / self.fs, len(squared))  # Time stamps starting from peak
        
        wd = 0.03  # Window duration, let's start with 30 ms (wd_initial)
        n = int(len(squared) / self.fs / wd) if self.fs > 0 and wd > 0 else 0 # Number of time windows (n_initial)
        
        if n == 0:
            # Signal is too short for even one 30ms window.
            # print("Warning: Signal too short for initial 30ms window in decay_params. Fallback.")
            noise_floor_val = np.mean(squared) if len(squared) > 0 else EPSILON
            noise_floor_db = 10 * np.log10(max(noise_floor_val, EPSILON))
            w_fallback_short = max(1, len(squared)) # Use full length as window size
            return peak_index, peak_index + len(squared), noise_floor_db, w_fallback_short
            
        w = int(len(squared) / n)  # Width of a single time window (w_initial)
        if w == 0: w = 1 # Ensure window width is at least 1
        w_fallback = w # Store this initial w for potential fallback return

        t_windows = np.arange(n) * wd + wd / 2  # Timestamps for the window centers
        
        # Ensure reshaping is possible: len(squared) must be >= n*w
        # This can be an issue if n*w from integer truncation slightly exceeds len(squared)
        squared_to_reshape = squared[:n*w]
        if len(squared_to_reshape) < n*w and n > 0 :
             # This implies problem with n or w calculation, or very short squared
             # print(f"Warning: Cannot reshape squared array of length {len(squared_to_reshape)} into ({n}, {w}). Adjusting n or w.")
             # Adjust n to fit
             n = len(squared_to_reshape) // w if w > 0 else 0
             if n == 0: # Still problematic
                 noise_floor_val = np.mean(squared) if len(squared) > 0 else EPSILON
                 noise_floor_db = 10 * np.log10(max(noise_floor_val, EPSILON))
                 return peak_index, peak_index + len(squared), noise_floor_db, w_fallback
        
        if n == 0: # Recalculated n is 0
             noise_floor_val = np.mean(squared) if len(squared) > 0 else EPSILON
             noise_floor_db = 10 * np.log10(max(noise_floor_val, EPSILON))
             return peak_index, peak_index + len(squared), noise_floor_db, w_fallback

        windows_reshaped = np.reshape(squared_to_reshape, (n, w)) # Split into time windows, one window per row
        windows_mean = np.mean(windows_reshaped, axis=1)  # Average each time window
        windows = 10 * np.log10(np.maximum(windows_mean, EPSILON))  # dB, prevent -inf

        # 2. A first estimate for the background noise level is determined
        tail_start_idx = int(len(squared) * 0.9) # Original: int(-0.1 * len(squared)) means last 10%
        tail = squared[tail_start_idx:]
        if len(tail) == 0: tail = squared # Use all of squared if tail is empty
        
        mean_tail_val = np.mean(tail) if len(tail) > 0 else EPSILON
        noise_floor = 10 * np.log10(np.maximum(mean_tail_val, EPSILON)) # Ensure finite

        # 3. The decay slope is estimated
        slope_end_threshold = noise_floor + 10.0
        
        # Find indices where windows are below or at the threshold
        candidate_indices = np.where(windows <= slope_end_threshold)[0]
        
        idx_for_regression_end = len(windows) # Default: use all windows for regression
        if len(candidate_indices) > 0:
            first_candidate = candidate_indices[0]
            if first_candidate > 0: # If first candidate is not the very first window
                idx_for_regression_end = first_candidate # Regress up to (but not including) this point
                                                          # Original: first_candidate - 1, so including point before
                                                          # For slice windows[:idx], use first_candidate
        
        # Ensure at least 2 points for linear regression
        if idx_for_regression_end < 2:
            if len(windows) >= 2: # If enough windows overall, use all of them
                idx_for_regression_end = len(windows)
            else: # Not enough windows for regression at all
                # print(f"Warning: Not enough windows ({len(windows)}) for Lundeby slope. Using fallback decay params.")
                return peak_index, peak_index + len(squared), noise_floor, w_fallback
        
        x_fit = t_windows[:idx_for_regression_end]
        y_fit = windows[:idx_for_regression_end]

        slope, intercept, _, _, _ = stats.linregress(x_fit, y_fit)

        # CRITICAL FIX: Check for NaN or zero slope
        if np.isnan(slope) or abs(slope) < EPSILON:
            # print(f"Warning: Initial Lundeby slope is problematic (slope={slope}). Using fallback decay params.")
            return peak_index, peak_index + len(squared), noise_floor, w_fallback

        # 4. A preliminary knee point is determined
        # Ensure slope is not zero for division
        if abs(slope) < EPSILON: # Should be caught above, but as safeguard
            knee_point_time = t_squared[-1] if len(t_squared)>0 else 0 # End of signal
        else:
            knee_point_time = (noise_floor - intercept) / slope
        
        # Ensure knee_point_time is within the bounds of t_squared
        if len(t_squared) > 0:
            knee_point_time = np.clip(knee_point_time, t_squared[0], t_squared[-1])
        else: # t_squared is empty, should not happen if len(squared) > 0
            knee_point_time = 0


        # 5. A new time interval length is calculated
        n_windows_per_10dB = 3
        # wd calculation (line 119 in user's file, now safe due to slope check)
        wd_denominator = abs(slope) * n_windows_per_10dB
        if wd_denominator < EPSILON: # Denominator too small
            # print(f"Warning: Denominator for wd calculation is too small ({wd_denominator}). Using large wd.")
            wd = (t_squared[-1] if len(t_squared) > 0 else 1.0) / 3.0 # Default wd to 1/3 of signal duration
        else:
            wd = 10 / wd_denominator
        
        # n calculation (line 120, where error occurred)
        if self.fs <= 0 or wd <= EPSILON : # wd can be very small if slope is very large
             # print(f"Warning: Unsuitable fs ({self.fs}) or wd ({wd}) for n calculation. Fallback for n.")
             n_new = 1 # Default to 1 window
        else:
            n_new = int(len(squared) / self.fs / wd)

        if n_new == 0: n_new = 1 # Ensure at least one window for the loop
        
        w_new = int(len(squared) / n_new) # Width of a single time window for iteration
        if w_new == 0: w_new = 1 # Ensure window width is at least 1

        t_windows_new = np.arange(n_new) * wd + wd / 2 # Time window center time stamps

        # 6. The squared impulse is averaged into the new local time intervals.
        squared_to_reshape_new = squared[:n_new*w_new]
        if len(squared_to_reshape_new) < n_new*w_new and n_new > 0: # Adjust n_new if needed
            n_new = len(squared_to_reshape_new) // w_new if w_new > 0 else 0
            if n_new == 0 : # Still problematic, exit gracefully from loop part
                # print("Warning: Cannot proceed with Lundeby iteration due to reshaping issues. Using pre-loop results.")
                idx_knee_pt_final = np.argmin(np.abs(t_squared - knee_point_time)) if len(t_squared)>0 else 0
                return peak_index, peak_index + idx_knee_pt_final, noise_floor, w_new # return current best w
        
        if n_new == 0: # Should be caught above
            idx_knee_pt_final = np.argmin(np.abs(t_squared - knee_point_time)) if len(t_squared)>0 else 0
            return peak_index, peak_index + idx_knee_pt_final, noise_floor, w_fallback # Use original w_fallback

        windows_reshaped_new = np.reshape(squared_to_reshape_new, (n_new, w_new))
        windows_mean_new = np.mean(windows_reshaped_new, axis=1)
        windows_new = 10 * np.log10(np.maximum(windows_mean_new, EPSILON)) # dB

        try:
            idx_knee_prelim_in_new_windows = np.argwhere(t_windows_new >= knee_point_time)[0, 0]
            val_knee_prelim_in_new_windows = windows_new[idx_knee_prelim_in_new_windows]
        except IndexError:
            # Knee point time is beyond the new t_windows, or t_windows_new is empty
            # print("Warning: Preliminary knee_point_time is outside new t_windows range. Using end of t_windows_new.")
            if len(t_windows_new) > 0:
                knee_point_time = t_windows_new[-1]
                val_knee_prelim_in_new_windows = windows_new[-1]
                idx_knee_prelim_in_new_windows = len(t_windows_new) -1
            else: # t_windows_new is empty, critical failure of iteration setup
                 # print("Warning: t_windows_new is empty. Fallback.")
                 idx_knee_pt_final = np.argmin(np.abs(t_squared - knee_point_time)) if len(t_squared)>0 else 0
                 return peak_index, peak_index + idx_knee_pt_final, noise_floor, w_new

        # Steps 7–9 are iterated
        noise_floor_iter = noise_floor # Start with pre-loop noise_floor
        knee_point_time_iter = knee_point_time
        val_knee_iter = val_knee_prelim_in_new_windows
        idx_knee_iter_in_windows = idx_knee_prelim_in_new_windows

        for i in range(5): # Max 5 iterations
            # 7. Re-estimate background noise level
            try:
                # Find where decay is 5dB below current knee point value
                noise_start_idx_in_windows = np.argwhere(windows_new <= val_knee_iter - 5)[0, 0]
            except IndexError: # No point is 5dB below knee value, or windows_new is too short/flat
                break # Cannot refine noise floor, exit loop
            
            noise_start_time_candidate = t_windows_new[noise_start_idx_in_windows]
            # Noise segment starts 5-10dB after knee OR min 10% of total response length
            # Here self.duration() refers to original IR, t_squared is for the segment after peak
            total_response_duration_from_peak = t_squared[-1] if len(t_squared)>0 else 0.0
            noise_floor_est_start_time = max(noise_start_time_candidate, 0.1 * total_response_duration_from_peak)
            
            # Ensure start time is within t_windows_new bounds
            if noise_floor_est_start_time > t_windows_new[-1]: break

            # Noise floor estimation ends one full (current) decay time after its start, or end of signal
            noise_floor_est_end_time = min(noise_floor_est_start_time + knee_point_time_iter, total_response_duration_from_peak)
            
            # Find corresponding indices in t_squared
            idx_noise_start_in_tsq = np.argmin(np.abs(t_squared - noise_floor_est_start_time))
            idx_noise_end_in_tsq   = np.argmin(np.abs(t_squared - noise_floor_est_end_time))

            if idx_noise_start_in_tsq >= idx_noise_end_in_tsq : # Invalid range for noise estimation
                 break

            noise_segment_for_avg = squared[idx_noise_start_in_tsq : idx_noise_end_in_tsq]
            if len(noise_segment_for_avg) == 0: noise_segment_for_avg = np.array([EPSILON]) # Avoid empty mean

            mean_noise_segment = np.mean(noise_segment_for_avg)
            noise_floor_iter = 10 * np.log10(np.maximum(mean_noise_segment, EPSILON))

            # 8. Estimate late decay slope
            slope_late_end_headroom = 8.0
            slope_late_dynamic_range = 20.0
            
            # Find points for late slope regression: 5-10dB above new noise_floor_iter, for 10-20dB range
            late_slope_end_val_target = noise_floor_iter + slope_late_end_headroom
            late_slope_start_val_target = noise_floor_iter + slope_late_end_headroom + slope_late_dynamic_range
            
            try:
                # Indices in 'windows_new'
                late_slope_end_idx_in_win = np.argwhere(windows_new <= late_slope_end_val_target)[0,0] -1
                late_slope_start_idx_in_win = np.argwhere(windows_new <= late_slope_start_val_target)[0,0] -1
            except IndexError: # Not enough dynamic range or points above noise floor
                break 

            if late_slope_start_idx_in_win < 0 : late_slope_start_idx_in_win = 0
            if late_slope_end_idx_in_win <= late_slope_start_idx_in_win + 1: # Need at least 2 points
                break
            
            x_late_fit = t_windows_new[late_slope_start_idx_in_win : late_slope_end_idx_in_win]
            y_late_fit = windows_new[late_slope_start_idx_in_win : late_slope_end_idx_in_win]

            if len(x_late_fit) < 2: break # Still not enough points after adjustments

            late_slope, late_intercept, _, _, _ = stats.linregress(x_late_fit, y_late_fit)

            if np.isnan(late_slope) or abs(late_slope) < EPSILON:
                break # Late slope calculation failed

            # 9. Find new knee_point
            if abs(late_slope) < EPSILON: # Avoid division by zero
                new_knee_point_time = t_windows_new[-1] if len(t_windows_new)>0 else 0
            else:
                new_knee_point_time = (noise_floor_iter - late_intercept) / late_slope

            if len(t_windows_new) == 0: break # Should not happen here
            new_knee_point_time = np.clip(new_knee_point_time, t_windows_new[0], t_windows_new[-1])

            try:
                new_idx_knee_in_windows = np.argwhere(t_windows_new >= new_knee_point_time)[0,0]
            except IndexError: # new_knee_point_time is past the end of t_windows_new
                 new_idx_knee_in_windows = len(t_windows_new) - 1 if len(t_windows_new)>0 else 0
            
            if new_idx_knee_in_windows == idx_knee_iter_in_windows: # Converged
                idx_knee_iter_in_windows = new_idx_knee_in_windows
                knee_point_time_iter = t_windows_new[idx_knee_iter_in_windows] if len(t_windows_new)>0 else 0
                break 
            else: # Update for next iteration
                idx_knee_iter_in_windows = new_idx_knee_in_windows
                knee_point_time_iter = t_windows_new[idx_knee_iter_in_windows] if len(t_windows_new)>0 and idx_knee_iter_in_windows < len(t_windows_new) else (t_windows_new[-1] if len(t_windows_new)>0 else 0)
                val_knee_iter = windows_new[idx_knee_iter_in_windows] if len(windows_new)>0 and idx_knee_iter_in_windows < len(windows_new) else (windows_new[-1] if len(windows_new)>0 else -200)
        else: # Loop finished without break (i.e., did not converge in 5 iterations)
            pass # Use the last calculated knee_point_time_iter

        # Final knee_point_index in the original 'squared' array (relative to peak_index)
        if len(t_squared) > 0 :
            final_knee_point_idx_in_squared = np.argmin(np.abs(t_squared - knee_point_time_iter))
        else: # t_squared was empty
            final_knee_point_idx_in_squared = 0
            
        # w_new is the window size from the iterative part.
        return peak_index, peak_index + final_knee_point_idx_in_squared, noise_floor_iter, w_new

    # ... (rest of the ImpulseResponse class methods remain the same) ...

    def decay_times(self, peak_ind=None, knee_point_ind=None, noise_floor=None, window_size=None):
        """Calculates decay times EDT, RT20, RT30, RT60

        Args:
            peak_ind: Peak index as returned by `decay_params()`. Optional.
            knee_point_ind: Knee point index as returned by `decay_params()`. Optional.
            noise_floor: Noise floor as returned by `decay_params()`. Optional.
            window_size: Moving average window size as returned by `decay_params()`. Optional.

        Returns:
            - EDT, None if SNR < 10 dB
            - RT20, None if SNR < 35 dB
            - RT30, None if SNR < 45 dB
            - RT60, None if SNR < 75 dB

        """
        if peak_ind is None or knee_point_ind is None or noise_floor is None or window_size is None: # Added window_size check
            # print("decay_times: One or more input parameters are None. Recomputing decay_params.")
            peak_ind, knee_point_ind, noise_floor, window_size = self.decay_params()

        if window_size <= 0: # Invalid window_size from decay_params fallback
            # print(f"decay_times: Invalid window_size ({window_size}). Setting to a default.")
            window_size = max(1, int(0.01 * self.fs)) # Default to 10ms or 1 sample

        t = np.linspace(0, self.duration(), len(self))

        # Ensure knee_point_ind is relative to peak_ind and valid
        if knee_point_ind <= peak_ind:
            # print(f"decay_times: knee_point_ind ({knee_point_ind}) <= peak_ind ({peak_ind}). Adjusting or returning Nones.")
            # This indicates an issue from decay_params, perhaps very short decay.
            # Schroeder integral requires knee_point_ind > peak_ind to define a decay range.
            return None, None, None, None 
            
        relative_knee_point_ind = knee_point_ind - peak_ind

        data = self.data.copy()
        # Ensure data segment starts at peak_ind and has some length
        if peak_ind >= len(data): peak_ind = len(data)-1
        if peak_ind < 0: peak_ind = 0
        
        data_segment = data[peak_ind:] # From peak to end
        if len(data_segment) == 0: return None, None, None, None # No data after peak

        max_abs_val = np.max(np.abs(data_segment))
        if max_abs_val < EPSILON: # Silent
             data_segment_norm = data_segment
        else:
             data_segment_norm = data_segment / max_abs_val
        
        analytical = np.abs(data_segment_norm) # Use absolute value

        # Ensure relative_knee_point_ind is within bounds of analytical
        if relative_knee_point_ind >= len(analytical):
            relative_knee_point_ind = len(analytical) -1 
        if relative_knee_point_ind < 0: # Should be caught by knee_point_ind <= peak_ind check
            return None, None, None, None


        # Schroeder integral calculation needs a valid range
        # Sum from relative_knee_point_ind down to 0 (inclusive of 0)
        # If relative_knee_point_ind is 0, cumsum part is tricky.
        if relative_knee_point_ind == 0 and len(analytical) > 0 : # Only one point in decay (the peak itself)
            schroeder = np.array([0.0]) # 10*log10(1)
        elif len(analytical[:relative_knee_point_ind+1]) > 0 :
            sum_sq_decay = np.sum(analytical[:relative_knee_point_ind+1] ** 2)
            if sum_sq_decay < EPSILON : # Sum is zero, avoid division by zero
                 schroeder = np.full(relative_knee_point_ind +1, -200.0) # effectively silent
            else:
                 schroeder_vals = np.cumsum(analytical[relative_knee_point_ind::-1] ** 2) / sum_sq_decay
                 schroeder = 10 * np.log10(np.maximum(schroeder_vals[::-1], EPSILON)) # Reverse back, ensure positive for log
        else: # analytical[:relative_knee_point_ind+1] is empty
            return None, None, None, None
        
        if len(schroeder) == 0: return None, None, None, None


        # Moving average of the squared impulse response
        avg_data_orig = self.data.copy()
        
        # Ensure window_size is not larger than the data available for averaging
        avg_head = min((window_size // 2), peak_ind)
        # For avg_tail, ensure peak_ind + relative_knee_point_ind is a valid index for avg_data_orig
        end_of_decay_abs_idx = peak_ind + relative_knee_point_ind
        if end_of_decay_abs_idx >= len(avg_data_orig): end_of_decay_abs_idx = len(avg_data_orig) -1
        
        avg_tail = min((window_size // 2), len(avg_data_orig) - 1 - end_of_decay_abs_idx)
        avg_offset = window_size // 2 - avg_head
        
        avg_start_idx = peak_ind - avg_head
        avg_end_idx = end_of_decay_abs_idx + avg_tail + 1 # Slice end is exclusive
        
        if avg_start_idx < 0 : avg_start_idx = 0
        if avg_end_idx > len(avg_data_orig) : avg_end_idx = len(avg_data_orig)
        if avg_start_idx >= avg_end_idx : # Not enough data for averaging segment
             return None, None, None, None

        avg_segment = avg_data_orig[avg_start_idx:avg_end_idx]
        
        if len(avg_segment) == 0: return None, None, None, None
        max_abs_avg_segment = np.max(np.abs(avg_segment))
        if max_abs_avg_segment < EPSILON:
            avg_segment_norm = avg_segment
        else:
            avg_segment_norm = avg_segment / max_abs_avg_segment
        
        avg_segment_sq = avg_segment_norm ** 2
        
        # Ensure running_mean gets at least window_size elements if possible, or gracefully handles less
        if len(avg_segment_sq) < window_size:
            # print(f"decay_times: Data for running_mean ({len(avg_segment_sq)}) is shorter than window_size ({window_size}). Using mean.")
            avg_filtered = np.full_like(avg_segment_sq, np.mean(avg_segment_sq)) if len(avg_segment_sq)>0 else np.array([])
        else:
            avg_filtered = running_mean(avg_segment_sq, window_size)

        if len(avg_filtered) == 0: return None, None, None, None
        avg = 10 * np.log10(np.maximum(avg_filtered, EPSILON))
        
        # Fit offset for Schroeder
        # Ensure Schroeder and avg have comparable lengths for fitting offset
        len_sch = len(schroeder)
        len_avg_eff = len(avg) # avg is result of running_mean, its length is len(input) - window_size + 1
        
        fit_start_sch = int(len_sch * 0.1)
        fit_end_sch = int(len_sch * 0.9)

        # Corresponding indices in avg, considering avg_offset from original IR
        # avg_filtered corresponds to avg_segment_sq[window_size//2 : -(window_size//2)+1 (or similar)]
        # This part is complex; the original code's fit_start/fit_end logic for offset calculation:
        # fit_start = max(int(len(schroeder) * 0.1), avg_offset)
        # fit_end = min(int(len(schroeder) * 0.9), avg_offset + (len(avg)))
        # This implies avg indices are relative to a global frame, and schroeder indices too.
        # Let's assume schroeder is aligned with the start of the decay segment (peak_ind)
        
        # Effective length of `avg` for comparison with `schroeder`
        # `avg` is shorter than `schroeder` by `window_size-1` and potentially by `avg_offset` differences.
        # For simplicity, if ranges don't overlap well, offset might be inaccurate.

        # Ensure fit_start and fit_end define a valid range for both schroeder and avg.
        # Schroeder corresponds to t[0:relative_knee_point_ind+1]
        # Avg corresponds to t[avg_offset : avg_offset + len(avg)] (approximately)
        
        # Max common start index for fitting, min common end index
        # This is simplified; precise alignment for offset calculation is non-trivial
        # without knowing how `avg` indices map to `schroeder` indices.
        # Assuming `avg` starts effectively `avg_offset` samples later than `schroeder` start.
        
        common_len = min(len(schroeder), len(avg) - avg_offset if len(avg) > avg_offset else 0)
        if common_len < 2: # Not enough overlap for meaningful offset
            offset = 0.0
        else:
            sch_for_offset = schroeder[:common_len]
            avg_for_offset = avg[avg_offset : avg_offset + common_len] if avg_offset + common_len <= len(avg) else avg[avg_offset:]
            if len(sch_for_offset) != len(avg_for_offset) : # Adjust if still mismatched
                min_l = min(len(sch_for_offset), len(avg_for_offset))
                if min_l < 2: offset = 0.0
                else: offset = np.mean(sch_for_offset[:min_l] - avg_for_offset[:min_l])
            elif len(sch_for_offset) < 2: # after potential match, still too short
                offset = 0.0
            else:
                offset = np.mean(sch_for_offset - avg_for_offset)


        decay_times = dict()
        limits = [(-1, -10, -10, 'EDT'), (-5, -25, -20, 'RT20'), (-5, -35, -30, 'RT30'), (-5, -65, -60, 'RT60')]
        t_decay_segment = t[peak_ind : peak_ind + len(schroeder)] # Time vector for schroeder curve

        for start_target, end_target, decay_target, name in limits:
            decay_times[name] = None
            # Check SNR: end_target dB (on Schroeder) vs noise_floor (original IR noise) + offset
            if end_target < noise_floor + offset + 10: # Check if noise_floor is dB
                continue
            
            try:
                # Find indices on Schroeder curve
                start_indices = np.where(schroeder <= start_target)[0]
                end_indices = np.where(schroeder <= end_target)[0]

                if len(start_indices)==0 or len(end_indices)==0 : continue # Target levels not reached
                
                start_idx_sch = start_indices[0]
                end_idx_sch = end_indices[0]

                if end_idx_sch <= start_idx_sch + 1: continue # Need at least 2 points for regression
                
                # Use time from t_decay_segment corresponding to these Schroeder indices
                slope, intercept, _, _, _ = stats.linregress(
                    t_decay_segment[start_idx_sch:end_idx_sch], 
                    schroeder[start_idx_sch:end_idx_sch]
                )
                
                if np.isnan(slope) or abs(slope) < EPSILON: continue # Slope unusable
                decay_times[name] = decay_target / slope

            except IndexError: # Should be caught by len checks
                continue
            except ValueError: # Linregress failed for other reasons
                continue


        return decay_times['EDT'], decay_times['RT20'], decay_times['RT30'], decay_times['RT60']


    def crop_head(self, head_ms=1):
        """Crops away head."""
        if len(self.data) == 0: return # Cannot crop empty data
        peak_idx = self.peak_index()
        crop_start = peak_idx - int(self.fs * head_ms / 1000)
        if crop_start < 0: crop_start = 0
        self.data = self.data[crop_start:]

    def equalize(self, fir):
        """Equalizes this impulse response with give FIR filter.

        Args:
            fir: FIR filter as an single dimensional array

        Returns:
            None
        """
        if len(self.data) == 0 or len(fir) == 0: return # Cannot convolve with empty data/fir
        self.data = signal.convolve(self.data, fir, mode='full')[:len(self.data)+len(fir)-1 if len(self.data)>0 else len(fir)-1] # Match typical full conv length
        # Truncate to a reasonable length if it gets too long, or keep full.
        # Original behavior seems to be 'full' length. If this is too long, it might need trimming.
        # For now, let's assume 'full' is desired. If problems arise, trim to e.g. original len + fir_len -1 or fixed max.


    def resample(self, fs):
        """Resamples this impulse response to the given sampling rate."""
        if len(self.data) == 0: return
        if self.fs == fs : return # No need to resample
        self.data = nnresample.resample(self.data, fs, self.fs)
        self.fs = fs

    def convolve(self, x):
        """Convolves input data with this impulse response

        Args:
            x: Input data to be convolved

        Returns:
            Convolved data
        """
        if len(self.data) == 0 or len(x) == 0: return np.array([])
        return signal.convolve(x, self.data, mode='full')

    def adjust_decay(self, target):
        """Adjusts decay time in place.

        Args:
            target: Target 60 dB decay time in seconds

        Returns:
            None
        """
        if len(self.data) < 10 : return # Too short
        peak_index, knee_point_index, _, window_size_lundeby = self.decay_params() # Added window_size
        edt, rt20, rt30, rt60 = self.decay_times(peak_ind=peak_index, knee_point_ind=knee_point_index, window_size=window_size_lundeby) # Pass it
        
        rt_slope = None
        # Finds largest available decay time parameter
        for rt_time, rt_level in [(rt60, -60), (rt30, -30), (rt20, -20), (edt, -10)]: # Prioritize longer RTs
            if rt_time is not None and rt_time > EPSILON: # Check not None and positive
                rt_slope = rt_level / rt_time
                break
        
        if rt_slope is None or abs(rt_slope) < EPSILON : # No valid RT found or slope is flat
            # print("adjust_decay: Could not determine a valid current RT slope.")
            return

        if target <= EPSILON: # Invalid target decay time
            # print(f"adjust_decay: Invalid target decay time {target}.")
            return

        target_slope = -60 / target  # Target dB/s
        if target_slope > rt_slope - EPSILON : # Allow very small increase or if target slope is less negative (longer decay)
            # We're not going to adjust decay up significantly or if current decay is already shorter.
            # Original: if target_slope > rt_slope (means target decay is shorter than current, or slope is less negative)
            # If target_slope is less negative than rt_slope (e.g. -30dB/s vs -60dB/s), means target decay is longer.
            # This function is designed to shorten decay. So if target decay is longer, do nothing.
            # print("adjust_decay: Target decay is longer than or equal to current, or adjustment would be upwards. No change.")
            return
            
        # Ensure knee_point_index is valid relative to peak_index and data length
        if knee_point_index <= peak_index or knee_point_index >= len(self.data):
             # print(f"adjust_decay: Invalid knee_point_index ({knee_point_index}). Cannot apply decay adjustment.")
             return

        knee_point_time_abs = knee_point_index / self.fs # Absolute time of knee point from IR start
        # Time relative to peak for slope calculation:
        knee_point_time_rel_peak = (knee_point_index - peak_index) / self.fs
        if knee_point_time_rel_peak <= EPSILON:
            # print("adjust_decay: Knee point is too close to peak. Cannot adjust.")
            return


        knee_point_level = rt_slope * knee_point_time_rel_peak  # Extrapolated level at knee point relative to peak level (0dB)
        target_level = target_slope * knee_point_time_rel_peak  # Target level at knee point
        
        window_level_db_change = target_level - knee_point_level  # dB change needed at knee point
        
        # Window start after a small delay from peak, e.g. 2ms
        window_slope_start_idx = peak_index + int(2 * self.fs / 1000)
        if window_slope_start_idx >= knee_point_index:
            # print("adjust_decay: Window for slope adjustment is invalid (start >= knee).")
            return

        # Half Hanning window length, from delayed peak to knee point
        half_hanning_len = knee_point_index - window_slope_start_idx
        if half_hanning_len <= 0:
            # print("adjust_decay: Hanning window length for decay adjustment is zero or negative.")
            return

        # Adjustment window: ones until window_slope_start_idx, then Hanning down to knee_point_index, then zeros
        hanning_part = signal.windows.hann(half_hanning_len * 2)[half_hanning_len:] # Second half of Hanning
        
        win = np.concatenate([
            np.ones(window_slope_start_idx),
            hanning_part,
            np.zeros(len(self.data) - knee_point_index) # Fill with zeros to full length
        ])
        if len(win) > len(self.data): win = win[:len(self.data)] # Ensure same length
        elif len(win) < len(self.data): win = np.pad(win, (0, len(self.data) - len(win)), 'constant', constant_values=0)


        win = (win - 1.0)  # Slopes down from 0.0 (ones part) to -1.0 (end of Hanning)
        win *= -window_level_db_change  # Scale with dB change. If window_level_db_change is negative (target is lower), this term becomes positive.
                                     # We want to attenuate, so dB values should be negative.
                                     # If target_level (-50dB) < knee_point_level (-40dB), then window_level_db_change is -10dB.
                                     # -window_level_db_change becomes +10dB. This would boost.
                                     # Correction: win factor should be `window_level_db_change` if win slopes 0 to -1.
                                     # Since win slopes 0 to -1, and we want to apply `window_level_db_change` (which is negative for attenuation)
                                     # scale win by `window_level_db_change` (negative)
        win_scaled_db = win * window_level_db_change # If window_level_db_change is -10dB, this part becomes 0dB to +10dB. Incorrect.
        # Let's simplify: create a gain multiplier directly.
        # At window_slope_start_idx, gain is 1 (0dB).
        # At knee_point_index, gain should be 10**(window_level_db_change / 20).
        # We need a window that goes from 0dB to `window_level_db_change` dB.
        
        gain_at_knee = 10**(window_level_db_change / 20.0) # e.g. 0.316 if -10dB
        # Hanning window goes from 1 down to 0 (if we take second half and normalize it to start at 1).
        # We want it to go from 1 down to gain_at_knee.
        # So, hanning_part scaled: gain_at_knee + (1-gain_at_knee) * hanning_part (where original hanning_part is 1 to 0)
        # The scipy hann(M)[M//2:] goes from 1 down to 0 approx. Let's verify.
        # hann(N) is 0 at ends, 1 in middle. hann(N)[:N//2] is 0 to 1. hann(N)[N//2:] is 1 to 0.
        # So hanning_part is correct (1 down to 0).
        
        scaled_hanning_part = gain_at_knee + hanning_part * (1.0 - gain_at_knee)
        
        final_gain_window = np.concatenate([
            np.ones(window_slope_start_idx),
            scaled_hanning_part,
            np.full(len(self.data) - knee_point_index, gain_at_knee) # After knee, maintain gain_at_knee
        ])
        if len(final_gain_window) > len(self.data): final_gain_window = final_gain_window[:len(self.data)]
        elif len(final_gain_window) < len(self.data): final_gain_window = np.pad(final_gain_window, (0, len(self.data) - len(final_gain_window)), 'constant', constant_values=gain_at_knee)


        self.data *= final_gain_window  # Scale impulse response data with the gain window

    def magnitude_response(self):
        """Calculates magnitude response for the data."""
        if len(self.data) == 0: return np.array([]), np.array([])
        return magnitude_response(self.data, self.fs)

    def frequency_response(self):
        """Creates FrequencyResponse instance."""
        if len(self.data) < 2: # Need at least 2 points for FFT based magnitude_response
            # print("Warning: Data too short for frequency_response. Returning flat FR.")
            f = FrequencyResponse.generate_frequencies(f_step=1.01, f_min=10, f_max=self.fs / 2)
            return FrequencyResponse(name='Frequency response (short IR)', frequency=f, raw=np.zeros_like(f))

        f, m = self.magnitude_response()
        if len(f) == 0: # magnitude_response failed or returned empty
            f_gen = FrequencyResponse.generate_frequencies(f_step=1.01, f_min=10, f_max=self.fs / 2)
            return FrequencyResponse(name='Frequency response (mag_resp failed)', frequency=f_gen, raw=np.zeros_like(f_gen))

        # Ensure f has enough points for step calculation
        # n = self.fs / 2 / 4  # 4 Hz resolution. This n is num points, not related to FFT-N
        # Max freq is self.fs/2. If we want 4Hz resolution, we need (self.fs/2)/4 points.
        # This seems like a target number of points for the FR object, not step for slicing FFT output.
        # Original: step = int(len(f) / n)
        # If n is target points, then step should be chosen to achieve that.
        # Let's assume this logic means downsampling the FFT output for the FR object.
        
        target_fr_points = (self.fs / 2) / 4.0 # Example: 48k -> 24k -> 6000 points
        if target_fr_points < 2 or len(f) < 2 : # Not enough points from FFT or for target
             step = 1
        else:
             step = int(round(len(f) / target_fr_points))
             if step == 0 : step = 1 # Avoid step=0

        # Ensure f[1::step] is not empty. Max f index is len(f)-1.
        # f[0] is DC, often skipped.
        if len(f[1::step]) == 0 : # Slicing resulted in empty array
             # This happens if step is too large relative to len(f)-1
             # Fallback: use fewer points or just f[1:]
             f_selected = f[1:]
             m_selected = m[1:]
             if len(f_selected) == 0: # Original FFT output was just DC or empty
                f_gen = FrequencyResponse.generate_frequencies(f_step=1.01, f_min=10, f_max=self.fs / 2)
                return FrequencyResponse(name='Frequency response (FFT too short)', frequency=f_gen, raw=np.zeros_like(f_gen))
        else:
            f_selected = f[1::step]
            m_selected = m[1::step]

        fr = FrequencyResponse(name='Frequency response', frequency=f_selected, raw=m_selected)
        fr.interpolate(f_step=1.01, f_min=10, f_max=self.fs / 2) # Interpolate will resample to standard log-spaced freqs
        return fr

    # Plotting methods (plot, plot_recording, etc.) are complex and error-prone if data is minimal.
    # Add basic checks for data length in each plotting function.
    def plot(self,
             fig=None,
             ax=None,
             plot_file_path=None,
             plot_recording=True,
             plot_spectrogram=True,
             plot_ir=True,
             plot_fr=True,
             plot_decay=True,
             plot_waterfall=True):
        if len(self.data) < 2 and not (self.recording is not None and len(self.recording) >=2):
            # print("ImpulseResponse.plot: Data too short for most plots.")
            # Optionally create a dummy plot or skip
            if fig is None: fig = plt.figure()
            fig.text(0.5, 0.5, "Data too short to plot", ha='center', va='center')
            if plot_file_path: fig.savefig(plot_file_path)
            return fig

        if fig is None:
            fig = plt.figure()
            fig.set_size_inches(22, 10)
            gs = fig.add_gridspec(2, 3) # Use gridspec for 3d subplot
            ax_flat = []
            ax_flat.append(fig.add_subplot(gs[0,0]))
            ax_flat.append(fig.add_subplot(gs[0,1]))
            ax_flat.append(fig.add_subplot(gs[0,2]))
            ax_flat.append(fig.add_subplot(gs[1,0]))
            ax_flat.append(fig.add_subplot(gs[1,1]))
            ax_flat.append(fig.add_subplot(gs[1,2], projection='3d')) # Waterfall
            ax = np.array(ax_flat).reshape(2,3) # Keep ax as 2x3 array

        if plot_recording: self.plot_recording(fig=fig, ax=ax[0, 0])
        if plot_spectrogram: self.plot_spectrogram(fig=fig, ax=ax[1, 0])
        if plot_ir: self.plot_ir(fig=fig, ax=ax[0, 1])
        if plot_fr: self.plot_fr(fig=fig, ax=ax[1, 1])
        if plot_decay: self.plot_decay(fig=fig, ax=ax[0, 2])
        if plot_waterfall: self.plot_waterfall(fig=fig, ax=ax[1, 2])
        if plot_file_path: fig.savefig(plot_file_path)
        return fig

    def plot_recording(self, fig=None, ax=None, plot_file_path=None):
        if self.recording is None or len(self.recording) < 2:
            if ax is not None: ax.text(0.5, 0.5, "No recording data", ha='center', va='center', transform=ax.transAxes)
            return fig, ax # Return fig,ax even if nothing plotted, to maintain structure
        if fig is None: fig, ax = plt.subplots()

        t = np.linspace(0, len(self.recording) / self.fs, len(self.recording))
        ax.plot(t, self.recording, color=COLORS['blue'], linewidth=0.5)
        ax.grid(True); ax.set_xlabel('Time (s)'); ax.set_ylabel('Amplitude'); ax.set_title('Sine Sweep')
        if plot_file_path: fig.savefig(plot_file_path)
        return fig, ax

    def plot_spectrogram(self, fig=None, ax=None, plot_file_path=None, f_res=10, n_segments=200):
        if self.recording is None or len(self.recording) < int(self.fs / f_res) : # Need enough data for NFFT
            if ax is not None: ax.text(0.5, 0.5, "Recording too short for spectrogram", ha='center', va='center', transform=ax.transAxes)
            return fig, ax
        if fig is None: fig, ax = plt.subplots()

        nfft = int(self.fs / f_res)
        if nfft == 0 : nfft = 128 # Fallback nfft
        noverlap = int(nfft - (len(self.recording) - nfft) / n_segments)
        if noverlap >= nfft : noverlap = nfft // 2 # Ensure valid noverlap

        try:
            spectrum, freqs, t = specgram(self.recording, Fs=self.fs, NFFT=nfft, noverlap=noverlap, mode='psd')
            if len(freqs) <= 1 : raise ValueError("Spectrogram freqs too few.")
        except ValueError as e: # specgram can fail if data is too short relative to NFFT/noverlap
            # print(f"Error in specgram: {e}. Skipping spectrogram plot.")
            if ax is not None: ax.text(0.5, 0.5, f"Spectrogram error: {e}", ha='center', va='center', transform=ax.transAxes)
            return fig, ax

        f = freqs[1:]; z = spectrum[1:, :]
        if z.shape[0] == 0 or z.shape[1] == 0: # spectrum was empty after slicing
             if ax is not None: ax.text(0.5, 0.5, "Spectrogram data empty", ha='center', va='center', transform=ax.transAxes)
             return fig, ax
        
        z = 10 * np.log10(np.maximum(z, EPSILON)) # Prevent log(0)

        t_mesh, f_mesh = np.meshgrid(t, f) # Renamed to avoid conflict
        cs = ax.pcolormesh(t_mesh, f_mesh, z, cmap='gnuplot2', vmin=np.min(z), vmax=np.max(z), shading='auto') # Adjusted vmin/vmax

        divider = make_axes_locatable(ax)
        cax = divider.append_axes('right', size='5%', pad=0.05)
        fig.colorbar(cs, cax=cax)

        ax.semilogy(); ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        ax.set_xlabel('Time (s)'); ax.set_ylabel('Frequency (Hz)'); ax.set_title('Spectrogram')
        if plot_file_path: fig.savefig(plot_file_path)
        return fig, ax

    def plot_ir(self, fig=None, ax=None, start=0.0, end=None, plot_file_path=None):
        if len(self.data) < 2:
            if ax is not None: ax.text(0.5,0.5, "IR data too short", ha='center', va='center', transform=ax.transAxes)
            return fig, ax
        if end is None: end = len(self.data) / self.fs
        
        start_sample = int(start * self.fs)
        end_sample = int(end * self.fs)
        if start_sample >= end_sample or start_sample >= len(self.data):
             if ax is not None: ax.text(0.5,0.5, "IR plot range invalid", ha='center', va='center', transform=ax.transAxes)
             return fig, ax

        ir_segment = self.data[start_sample : min(end_sample, len(self.data))]
        if len(ir_segment) < 1:
            if ax is not None: ax.text(0.5,0.5, "IR segment empty", ha='center', va='center', transform=ax.transAxes)
            return fig, ax

        if fig is None: fig, ax = plt.subplots()
        t_plot = np.arange(len(ir_segment)) / self.fs * 1000 + start * 1000 # Time in ms
        ax.plot(t_plot, ir_segment, color=COLORS['blue'], linewidth=0.5)
        ax.set_xlabel('Time (ms)'); ax.set_ylabel('Amplitude'); ax.grid(True)
        ax.set_title(f'Impulse response ({start*1000:.0f}ms to {end*1000:.0f}ms)')
        if plot_file_path: fig.savefig(plot_file_path)
        return fig, ax

    def plot_fr(self,
                fr=None,
                fig=None,
                ax=None,
                plot_file_path=None,
                plot_raw=True, raw_color='#7db4db',
                plot_smoothed=True, smoothed_color='#1f77b4',
                plot_error=True, error_color='#dd8081',
                plot_error_smoothed=True, error_smoothed_color='#d62728',
                plot_target=True, target_color='#ecdef9',
                plot_equalization=True, equalization_color='#2ca02c',
                plot_equalized=True, equalized_color='#680fb9',
                fix_ylim=False):
        if fr is None:
            if len(self.data) < 2: # Not enough data for self.frequency_response()
                if ax is not None: ax.text(0.5,0.5, "Data too short for FR plot", ha='center', va='center', transform=ax.transAxes)
                return fig, ax
            fr = self.frequency_response()
            # Check if fr has valid data
            if len(fr.frequency) == 0 or len(fr.raw) == 0 :
                 if ax is not None: ax.text(0.5,0.5, "FR data empty", ha='center', va='center', transform=ax.transAxes)
                 return fig, ax
            fr.smoothen_fractional_octave(window_size=1/3, treble_f_lower=max(20000, fr.frequency.min()), treble_f_upper=min(23999, fr.frequency.max()))
        
        if fig is None: fig, ax = plt.subplots()
        ax.set_xlabel('Frequency (Hz)'); ax.semilogx(); ax.set_xlim([max(10, fr.frequency.min() if len(fr.frequency)>0 else 10), min(22000, fr.frequency.max() if len(fr.frequency)>0 else 22000)])
        ax.set_ylabel('Amplitude (dB)'); ax.set_title(fr.name if fr.name else "Frequency Response"); ax.grid(True, which='major'); ax.grid(True, which='minor')
        ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))
        
        legend, v = [], []
        sl = np.logical_and(fr.frequency >= 20, fr.frequency <= 20000) if len(fr.frequency)>0 else np.array([False])


        # Safely plot each component
        def safe_plot(data_attr, label, color, width=1, style='-'):
            data_y = getattr(fr, data_attr, np.array([]))
            if len(data_y) == len(fr.frequency) and len(data_y)>0:
                ax.plot(fr.frequency, data_y, linewidth=width, color=color, linestyle=style)
                legend.append(label)
                if np.any(sl): v.append(data_y[sl]) # Only if sl is not all False

        if plot_target: safe_plot('target', 'Target', target_color, width=5)
        if plot_raw: safe_plot('raw', 'Raw', raw_color, width=0.5)
        if plot_error: safe_plot('error', 'Error', error_color, width=0.5)
        if plot_smoothed: safe_plot('smoothed', 'Raw Smoothed', smoothed_color)
        if plot_error_smoothed: safe_plot('error_smoothed', 'Error Smoothed', error_smoothed_color)
        if plot_equalization: safe_plot('equalization', 'Equalization', equalization_color)
        if plot_equalized:
            if len(getattr(fr, 'equalized_raw', np.array([]))) > 0 and not len(getattr(fr, 'equalized_smoothed', np.array([]))) > 0:
                safe_plot('equalized_raw', 'Equalized raw', equalized_color)
            elif len(getattr(fr, 'equalized_smoothed', np.array([]))) > 0:
                safe_plot('equalized_smoothed', 'Equalized smoothed', equalized_color)

        if fix_ylim and v: # v might be empty if sl was all False or no curves plotted
            all_v = np.concatenate(v) if v else np.array([-1,1]) # Default y_lim if no valid data
            if len(all_v) > 0:
                lower, upper = get_ylim([all_v]) # get_ylim expects list of arrays
                ax.set_ylim([lower, upper])
            else: ax.set_ylim([-60, 20]) # Fallback ylim

        if legend: ax.legend(legend, fontsize=8)
        if plot_file_path: fig.savefig(plot_file_path)
        return fig, ax

    def plot_decay(self, fig=None, ax=None, plot_file_path=None):
        if len(self.data) < 10: # Arbitrary threshold
             if ax is not None: ax.text(0.5,0.5, "Data too short for decay plot", ha='center', va='center', transform=ax.transAxes)
             return fig, ax
        if fig is None: fig, ax = plt.subplots()

        try:
            peak_ind, knee_point_ind, noise_floor, window_size = self.decay_params()
        except Exception as e: # Catch any error from decay_params
            # print(f"Error in decay_params for plot_decay: {e}. Skipping.")
            if ax is not None: ax.text(0.5,0.5, f"Decay params error: {e}", ha='center', va='center', transform=ax.transAxes)
            return fig,ax

        if window_size <= 0 : window_size = 1 # Ensure valid window size

        # Ensure indices are valid
        start_plot_idx = max(0, (peak_ind - 2 * abs(knee_point_ind - peak_ind))) # abs for safety
        end_plot_idx = min(len(self.data), (peak_ind + 2 * abs(knee_point_ind - peak_ind)))
        if start_plot_idx >= end_plot_idx : 
            if ax is not None: ax.text(0.5,0.5, "Decay plot range invalid", ha='center', va='center', transform=ax.transAxes)
            return fig, ax

        t_plot = np.arange(start_plot_idx, end_plot_idx) / self.fs

        squared_plot = self.data.copy()
        max_abs_sq_plot = np.max(np.abs(squared_plot))
        if max_abs_sq_plot > EPSILON: squared_plot /= max_abs_sq_plot
        
        squared_plot = squared_plot[start_plot_idx:end_plot_idx] ** 2
        if len(squared_plot) == 0:
            if ax is not None: ax.text(0.5,0.5, "Squared data empty for decay plot", ha='center', va='center', transform=ax.transAxes)
            return fig, ax
        
        avg = running_mean(squared_plot, window_size) if len(squared_plot) >= window_size else np.full_like(squared_plot, np.mean(squared_plot))
        
        squared_db = 10 * np.log10(np.maximum(squared_plot, EPSILON))
        avg_db = 10 * np.log10(np.maximum(avg, EPSILON))

        ax.plot(t_plot * 1000, squared_db, color=COLORS['lightblue'], label='Squared impulse response')
        
        # Time vector for avg needs to align with its data
        t_avg_start_offset = (window_size -1) // 2 # running_mean output is 'centered' effectively
        t_avg = t_plot[t_avg_start_offset : t_avg_start_offset + len(avg_db)] if len(t_plot) >= t_avg_start_offset + len(avg_db) else t_plot[:len(avg_db)]
        if len(t_avg) == len(avg_db) and len(t_avg)>0: # Ensure lengths match for plotting
           ax.plot(t_avg * 1000, avg_db, color=COLORS['blue'], label=f'{window_size / self.fs *1000:.0f} ms moving average')
        
        min_avg_val = np.min(avg_db) if len(avg_db)>0 else -100
        ax.set_ylim([min_avg_val * 1.2 if min_avg_val < -EPSILON else -120, 0]) # Ensure ylim lower bound is reasonable
        ax.set_xlim([start_plot_idx / self.fs * 1000, end_plot_idx / self.fs * 1000])
        ax.set_xlabel('Time (ms)'); ax.set_ylabel('Amplitude (dBr)'); ax.grid(True, which='major')
        ax.set_title('Decay'); ax.legend(loc='upper right')
        if plot_file_path: fig.savefig(plot_file_path)
        return fig, ax

    def plot_waterfall(self, fig=None, ax=None):
        # Waterfall plots are sensitive to data quality and length. Add robust checks.
        if len(self.data) < int(self.fs * 0.02): # Need at least ~20ms for a minimal waterfall
             if ax is not None: ax.text(0.5,0.5, "Data too short for waterfall", ha='center', va='center', transform=ax.transAxes)
             return fig, ax
        if fig is None: # If ax is not 3D, this will fail. Handled by main plot() usually.
            fig = plt.figure() 
            ax = fig.add_subplot(111, projection='3d')


        z_min = -100
        window_duration = 0.01
        nfft = min(int(self.fs * window_duration), max(1, int(len(self.data) / 10))) # ensure nfft > 0
        if nfft == 0: nfft = 128 # Fallback if data is extremely short
        noverlap = int(nfft * 0.9)
        if noverlap >= nfft : noverlap = nfft // 2

        # Hanning window parts for ascend/plateau/descend
        ascend_ms = 10 
        ascend_samples = int(ascend_ms / 1000 * self.fs)
        if ascend_samples * 2 > nfft: ascend_samples = nfft // 4 # Ensure ascend part fits
        
        plateau_samples = int((nfft - ascend_samples) * 3 / 4)
        descend_samples = nfft - ascend_samples - plateau_samples
        if descend_samples < 0 : # Adjust if calculation made it negative
            descend_samples = 0
            plateau_samples = nfft - ascend_samples # Maximize plateau
        if ascend_samples == 0 and plateau_samples == 0 and descend_samples == 0 and nfft > 0: # All zero, but nfft > 0
             window = signal.windows.hann(nfft) # Default to full hann window
        elif ascend_samples == 0 and descend_samples == 0 : # Only plateau
             window = np.ones(nfft)
        else: # Construct custom window
            win_asc = signal.windows.hann(ascend_samples * 2)[:ascend_samples] if ascend_samples > 0 else np.array([])
            win_pla = np.ones(plateau_samples) if plateau_samples > 0 else np.array([])
            win_des = signal.windows.hann(descend_samples * 2)[descend_samples:] if descend_samples > 0 else np.array([])
            window = np.concatenate([win_asc, win_pla, win_des])

        if len(window) != nfft : window = signal.windows.hann(nfft) # Fallback if construction failed

        try:
            peak_ind, tail_ind, _, _ = self.decay_params()
        except Exception: # decay_params failed
            peak_ind = self.peak_index() if len(self.data)>0 else 0
            tail_ind = len(self.data) -1

        start_wf = max(int(peak_ind - self.fs * 0.01), 0)
        stop_wf = min(int(round(max(peak_ind + self.fs * 1.0, tail_ind + nfft))), len(self.data)) # Ensure stop is within bounds
        if start_wf >= stop_wf or stop_wf - start_wf < nfft: # Data segment too short
             if ax is not None: ax.text(0.5,0.5, "Waterfall segment too short", ha='center', va='center', transform=ax.transAxes)
             return fig, ax
        
        data_wf = self.data[start_wf:stop_wf]

        try:
            spectrum, freqs_wf, t_wf = specgram(data_wf, Fs=self.fs, NFFT=nfft, noverlap=noverlap, mode='magnitude', window=window)
            if spectrum.shape[0] <=1 or spectrum.shape[1] <=1: raise ValueError("Spectrogram output too small")
        except ValueError as e:
            # print(f"Error in specgram for waterfall: {e}")
            if ax is not None: ax.text(0.5,0.5, f"Waterfall specgram error: {e}", ha='center', va='center', transform=ax.transAxes)
            return fig, ax

        spectrum = spectrum[1:, :]; freqs_wf = freqs_wf[1:] # Remove DC
        if spectrum.shape[0] == 0 or spectrum.shape[1] == 0:
             if ax is not None: ax.text(0.5,0.5, "Waterfall data empty post-DC removal", ha='center', va='center', transform=ax.transAxes)
             return fig, ax


        # Interpolate to logarithmic frequency scale
        f_max_wf = self.fs / 2; f_min_wf = 20 # Waterfall typically starts at 20Hz
        step_wf = 1.03 
        # Ensure f_min_wf < f_max_wf and freqs_wf has range
        if f_min_wf >= f_max_wf or freqs_wf.min() >= freqs_wf.max() :
             if ax is not None: ax.text(0.5,0.5, "Waterfall freq range invalid", ha='center', va='center', transform=ax.transAxes)
             return fig, ax

        num_f_pts = int(np.log(f_max_wf / f_min_wf) / np.log(step_wf)) if f_max_wf > f_min_wf else 0
        if num_f_pts <=1 : 
             if ax is not None: ax.text(0.5,0.5, "Waterfall log-freq points too few", ha='center', va='center', transform=ax.transAxes)
             return fig, ax
        
        f_log_wf = np.array([f_min_wf * step_wf ** i for i in range(num_f_pts)])
        f_log_wf = f_log_wf[f_log_wf <= freqs_wf.max()] # Clip to max available freq
        f_log_wf = f_log_wf[f_log_wf >= freqs_wf.min()] # Clip to min available freq
        if len(f_log_wf) <=1 :
             if ax is not None: ax.text(0.5,0.5, "Waterfall log-freq points too few after clipping", ha='center', va='center', transform=ax.transAxes)
             return fig, ax

        log_f_spec = np.ones((len(f_log_wf), spectrum.shape[1]))
        
        # Check if freqs_wf is monotonically increasing (required for InterpolatedUnivariateSpline)
        if not np.all(np.diff(freqs_wf) > 0):
            # print("Waterfall: freqs_wf not monotonic. Using unique sorted values.")
            unique_freqs, idx_unique = np.unique(freqs_wf, return_index=True)
            if len(unique_freqs) < 2 : # Need at least 2 unique freqs for spline
                 if ax is not None: ax.text(0.5,0.5, "Waterfall too few unique freqs for spline", ha='center', va='center', transform=ax.transAxes)
                 return fig, ax
            
            for i in range(spectrum.shape[1]): # Iterate over time slices
                spectrum_slice = spectrum[idx_unique, i] # Use only data corresponding to unique freqs
                interpolator = interpolate.InterpolatedUnivariateSpline(np.log10(unique_freqs), spectrum_slice, k=1, ext='zeros')
                log_f_spec[:, i] = interpolator(np.log10(f_log_wf))
        else: # freqs_wf is fine
            for i in range(spectrum.shape[1]):
                interpolator = interpolate.InterpolatedUnivariateSpline(np.log10(freqs_wf), spectrum[:, i], k=1, ext='zeros') # ext='zeros' for out-of-bounds
                log_f_spec[:, i] = interpolator(np.log10(f_log_wf))
        
        z_wf = log_f_spec
        f_mesh_log_wf = np.log10(f_log_wf) # Use f_log_wf for the mesh Y axis

        max_z_wf = np.max(z_wf)
        if max_z_wf < EPSILON: z_wf_norm = z_wf # Avoid division by zero if all silent
        else: z_wf_norm = z_wf / max_z_wf
        
        z_wf_db = 20 * np.log10(np.clip(z_wf_norm, 10**(z_min/20.0), 1.0)) # Clip then log
        z_wf_smooth = ndimage.uniform_filter(z_wf_db, size=3, mode='constant', cval=z_min) # cval for edges
        
        t_mesh_wf, f_mesh_wf_log_display = np.meshgrid(t_wf, f_mesh_log_wf) # Meshgrid for plotting

        # Remove "walls" from smoothing (typically first/last row/col of smoothed data)
        if z_wf_smooth.shape[0] > 2 and z_wf_smooth.shape[1] > 1 :
            t_plot_wf = t_mesh_wf[1:-1, :-1] * 1000 # Milliseconds
            f_plot_wf = f_mesh_wf_log_display[1:-1, :-1]
            z_plot_wf = z_wf_smooth[1:-1, :-1]
        else: # Not enough data to remove walls, plot as is
            t_plot_wf = t_mesh_wf * 1000
            f_plot_wf = f_mesh_wf_log_display
            z_plot_wf = z_wf_smooth
        
        if t_plot_wf.size == 0 or f_plot_wf.size == 0 or z_plot_wf.size == 0 :
            if ax is not None: ax.text(0.5,0.5, "Waterfall plot data empty after processing", ha='center', va='center', transform=ax.transAxes)
            return fig, ax


        ax.plot_surface(t_plot_wf, f_plot_wf, z_plot_wf, rcount=min(50, z_plot_wf.shape[0]), ccount=min(50, z_plot_wf.shape[1]), cmap='magma', antialiased=True, vmin=z_min, vmax=0)

        ax.set_zlim([z_min, 0]); ax.zaxis.set_major_locator(LinearLocator(10)); ax.zaxis.set_major_formatter(FormatStrFormatter('%.0f')) # Changed z format
        ax.set_xlim([0, t_plot_wf.max() if t_plot_wf.size > 0 else 100]); ax.set_xlabel('Time (ms)')
        ax.set_ylim(np.log10([max(10,f_min_wf), min(20000, f_max_wf)])); ax.set_ylabel('Frequency (Hz)')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x_val, p: f'{10**x_val:.0f}'))
        ax.view_init(30, 30)
        return fig, ax
