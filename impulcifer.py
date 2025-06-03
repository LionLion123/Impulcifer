# -*- coding: utf-8 -*-

import os
import re
global copy
import copy as _copy 
from scipy.signal import butter, lfilter
import argparse
import sys, re
from scipy.signal import windows 
from tabulate import tabulate
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from autoeq.frequency_response import FrequencyResponse
from impulse_response_estimator import ImpulseResponseEstimator
from hrir import HRIR
from room_correction import room_correction
from utils import sync_axes, save_fig_as_png
from constants import SPEAKER_NAMES, SPEAKER_LIST_PATTERN, HESUVI_TRACK_ORDER

def parse_early_args(arg_list):
    """
    unknown_args(리스트)에서 --early{start}_{end}={gain_db} 패턴을 찾아
    [(start_ms, end_ms, gain_db), ...] 리스트로 반환합니다.
    """
    pattern = re.compile(r'^--early(\d+)_(\d+)=(-?\d+\.?\d*)$')
    wins = []
    for arg in arg_list:
        m = pattern.match(arg)
        if m:
            wins.append((int(m.group(1)),
                         int(m.group(2)),
                         float(m.group(3))))
    return wins

def main(dir_path=None,
         test_signal=None,
         room_target=None,
         room_mic_calibration=None,
         fs=None,
         plot=False,
         channel_balance=None,
         decay=None,
         target_level=None,
         fr_combination_method='average',
         specific_limit=20000,
         generic_limit=1000,
         bass_boost_gain=0.0,
         bass_boost_fc=105,
         bass_boost_q=0.76,
         tilt=0.0,
         do_room_correction=True,
         do_headphone_compensation=True,
         head_ms=1,
         jamesdsp=False,
         hangloose=False,
         do_equalization=True,
         early_windows=None):
    """"""
    if dir_path is None or not os.path.isdir(dir_path):
        raise NotADirectoryError(f'Given dir path "{dir_path}"" is not a directory.')

    # Dir path as absolute
    dir_path = os.path.abspath(dir_path)

    # Impulse response estimator
    print('Creating impulse response estimator...')
    estimator = open_impulse_response_estimator(dir_path, file_path=test_signal)

    # Room correction frequency responses
    room_frs = None
    if do_room_correction:
        print('Running room correction...')
        _, room_frs = room_correction(
            estimator, dir_path,
            target=room_target,
            mic_calibration=room_mic_calibration,
            fr_combination_method=fr_combination_method,
            specific_limit=specific_limit,
            generic_limit=generic_limit,
            plot=plot
        )

    # Headphone compensation frequency responses
    hp_left, hp_right = None, None
    if do_headphone_compensation:
        print('Running headphone compensation...')
        hp_left, hp_right = headphone_compensation(estimator, dir_path)

    # Equalization
    eq_left, eq_right = None, None
    if do_equalization:
        print('Creating headphone equalization...')
        eq_left, eq_right = equalization(estimator, dir_path)

    # Bass boost and tilt
    print('Creating frequency response target...')
    target = create_target(estimator, bass_boost_gain, bass_boost_fc, bass_boost_q, tilt)

    # HRIR measurements
    print('Opening binaural measurements...')
    hrir = open_binaural_measurements(estimator, dir_path)

    readme = write_readme(os.path.join(dir_path, 'README.md'), hrir, fs)

    if plot:
        # Plot graphs pre processing
        os.makedirs(os.path.join(dir_path, 'plots', 'pre'), exist_ok=True)
        print('Plotting BRIR graphs before processing...')
        hrir.plot(dir_path=os.path.join(dir_path, 'plots', 'pre'))

    # Crop noise and harmonics from the beginning
    print('Cropping impulse responses...')
    hrir.crop_heads(head_ms=head_ms)
    hrir.align_ipsilateral_all(
        speaker_pairs=[('FL','FR'), ('SL','SR'), ('BL','BR'),
                        ('TFL','TFR'), ('TSL','TSR'), ('TBL','TBR'),
                        ('FC','FC'), ('WL','WR')],
        segment_ms=30
    )
    hrir.align_onset_groups_peak_leftref()
    hrir.crop_tails()


    if early_windows:
        print('→ Applying early-window gain adjustments...')
        for start_ms, end_ms, gain_db in early_windows:
            for speaker, pair in hrir.irs.items():
                for side, ir in pair.items():
                    data = ir.data       # 원본 배열 참조
                    fs   = ir.fs

                # 1) ITD 샘플 차이 계산
                    itd = abs(pair['left'].peak_index()
                              - pair['right'].peak_index())

                # 2) cross-channel 판정
                    is_cross = ((side=='right' and speaker.endswith('L')) or
                                (side=='left'  and speaker.endswith('R')))

                # 3) aligned 배열 준비
                    if is_cross:
                        # cross-channel: 앞당겨서 복사본 생성
                        aligned = np.roll(data, -itd)
                    else:
                        # direct channel: 원본 배열 그대로 사용
                        aligned = data

                    # 4) 윈도우 구간 계산
                    s = int(start_ms * fs / 1000)
                    e = int(end_ms   * fs / 1000)
                    N = e - s

                    # 5)
                    alpha = 0.5      # 조절값: 0 < alpha < 1. 작을수록 더 플랫
                    w = windows.tukey(N, alpha=alpha, sym=False)
                    g = 10**(gain_db / 20)
                    k = g - 1

                    # 6) 부드러운 가감산 적용
                    segment = aligned[s:e]
                    aligned[s:e] = segment + k * w * segment

                    # 7) 결과를 ir.data에 반영
                    if is_cross:
                        # cross-channel: 다시 원위치로 롤 복원
                        ir.data = np.roll(aligned, itd)
                    else:
                        # direct: aligned가 data alias이므로 이미 in-place로 반영됨
                        ir.data = aligned

 
  # 디버깅용 responses.wav 출력
    hrir.write_wav(os.path.join(dir_path, 'responses.wav'))

    # Write multi-channel WAV file with sine sweeps for debugging
    hrir.write_wav(os.path.join(dir_path, 'responses.wav'))

    # Equalize all
    if do_headphone_compensation or do_room_correction or do_equalization:
        print('Equalizing...')
        for speaker, pair in hrir.irs.items():
            for side, ir in pair.items():
                fr = FrequencyResponse(
                    name=f'{speaker}-{side} eq',
                    frequency=FrequencyResponse.generate_frequencies(f_step=1.01, f_min=10, f_max=estimator.fs / 2),
                    raw=0, error=0
                )

                if room_frs is not None and speaker in room_frs and side in room_frs[speaker]:
                    # Room correction
                    fr.error += room_frs[speaker][side].error

                hp_eq = hp_left if side == 'left' else hp_right
                if hp_eq is not None:
                    # Headphone compensation
                    fr.error += hp_eq.error

                eq = eq_left if side == 'left' else eq_right
                if eq is not None and type(eq) == FrequencyResponse:
                    # Equalization
                    fr.error += eq.error

                # Remove bass and tilt target from the error
                fr.error -= target.raw

                # Smoothen and equalize
                fr.smoothen_heavy_light()
                fr.equalize(max_gain=40, treble_f_lower=10000, treble_f_upper=estimator.fs / 2)

                # Create FIR filter and equalize
                fir = fr.minimum_phase_impulse_response(fs=estimator.fs, normalize=False, f_res=5)
                ir.equalize(fir)

    # Adjust decay time
    if decay:
        print('Adjusting decay time...')
        for speaker, pair in hrir.irs.items():
            for side, ir in pair.items():
                if speaker in decay:
                    ir.adjust_decay(decay[speaker])

    # Correct channel balance
    if channel_balance is not None:
        print('Correcting channel balance...')
        hrir.correct_channel_balance(channel_balance)

    # Normalize gain
    print('Normalizing gain...')
    hrir.normalize(peak_target=None if target_level is not None else -0.1, avg_target=target_level)

    if plot:
        print('Plotting BRIR graphs after processing...')
        # Convolve test signal, re-plot waveform and spectrogram
        for speaker, pair in hrir.irs.items():
            for side, ir in pair.items():
                ir.recording = ir.convolve(estimator.test_signal)
        # Plot post processing
        hrir.plot(os.path.join(dir_path, 'plots', 'post'))

    # Plot results, always
    print('Plotting results...')
    hrir.plot_result(os.path.join(dir_path, 'plots'))

    # Re-sample
    if fs is not None and fs != hrir.fs:
        print(f'Resampling BRIR to {fs} Hz')
        hrir.resample(fs)
        hrir.normalize(peak_target=None if target_level is not None else -0.1, avg_target=target_level)

    # Write multi-channel WAV file with standard track order
    print('Writing BRIRs...')
    hrir.write_wav(os.path.join(dir_path, 'hrir.wav'))

    # Write multi-channel WAV file with HeSuVi track order
    hrir.write_wav(os.path.join(dir_path, 'hesuvi.wav'), track_order=HESUVI_TRACK_ORDER)

    print(readme)


    if jamesdsp:
        print('Generating jamesdsp.wav (FL/FR only, normalized to FL/FR)...')
        import copy, contextlib, io

        # 전체 HRIR 복사 후 FL/FR 외 모든 채널 제거
        dsp_hrir = copy.deepcopy(hrir)
        for sp in list(dsp_hrir.irs.keys()):
            if sp not in ['FL', 'FR']:
                del dsp_hrir.irs[sp]

        with contextlib.redirect_stdout(io.StringIO()):
            dsp_hrir.normalize(
                peak_target=None if target_level is not None else -0.1,
                avg_target=target_level
            )

        # FL‑L, FL‑R, FR‑L, FR‑R 순서로 파일 생성
        jd_order = ['FL-left', 'FL-right', 'FR-left', 'FR-right']
        out_path = os.path.join(dir_path, 'jamesdsp.wav')
        dsp_hrir.write_wav(out_path, track_order=jd_order)

    if hangloose:
        from scipy.io import wavfile

        output_dir = os.path.join(dir_path, 'hangloose')
        os.makedirs(output_dir, exist_ok=True)

        # Hrir.wav 기준 최대 채널 순서
        full_order = [
            'FL','FR','FC','LFE','BL','BR','SL','SR',
            'WL','WR','TFL','TFR','TSL','TSR','TBL','TBR'
        ]
        processed = [sp for sp in full_order if sp in hrir.irs]

        # 1) 스피커별 WAV 생성 (FC도 포함)
        for sp in processed:
            single = _copy.deepcopy(hrir)
            for other in list(single.irs.keys()):
                if other != sp:
                    del single.irs[other]

            track_order = [f'{sp}-left', f'{sp}-right']
            out_path     = os.path.join(output_dir, f'{sp}.wav')
            single.write_wav(out_path, track_order=track_order)
            print(f'[Hangloose] 생성됨: {out_path}')

        # 2) FL.wav 과 FR.wav 읽어서 각각 LFEL.wav, LFR.wav 생성
        for sp, out_name in [('FL', 'LFEL.wav'), ('FR', 'LFER.wav')]:
            src_path = os.path.join(output_dir, f'{sp}.wav')
            if not os.path.isfile(src_path):
                continue

            # 2.1) 읽기
            fs_read, data = wavfile.read(src_path)  # data.shape == (N, 2)

            # 2.2) 120 Hz 로우패스 필터 설계
            b, a = butter(4, 120/(fs_read/2), btype='low', analog=False)
            gain_lin = 10**(10/20)  # +10 dB

            # 2.3) 좌/우 채널 필터링 + 게인 적용
            filtered_l = lfilter(b, a, data[:, 0]) * gain_lin
            filtered_r = lfilter(b, a, data[:, 1]) * gain_lin

            # 2.4) 저장
            out_path = os.path.join(output_dir, out_name)
            lfe_data = np.vstack((filtered_l, filtered_r)).T.astype(data.dtype)
            wavfile.write(out_path, fs_read, lfe_data)
            print(f'[LFE 변환] 생성됨: {out_path}')





def open_impulse_response_estimator(dir_path, file_path=None):
    """Opens impulse response estimator from a file

    Args:
        dir_path: Path to directory
        file_path: Explicitly given (if any) path to impulse response estimator Pickle or test signal WAV file

    Returns:
        ImpulseResponseEstimator instance
    """
    if file_path is None:
        # Test signal not explicitly given, try Pickle first then WAV
        if os.path.isfile(os.path.join(dir_path, 'test.pkl')):
            file_path = os.path.join(dir_path, 'test.pkl')
        elif os.path.isfile(os.path.join(dir_path, 'test.wav')):
            file_path = os.path.join(dir_path, 'test.wav')
    if re.match(r'^.+\.wav$', file_path, flags=re.IGNORECASE):
        # Test signal is WAV file
        estimator = ImpulseResponseEstimator.from_wav(file_path)
    elif re.match(r'^.+\.pkl$', file_path, flags=re.IGNORECASE):
        # Test signal is Pickle file
        estimator = ImpulseResponseEstimator.from_pickle(file_path)
    else:
        raise TypeError(f'Unknown file extension for test signal "{file_path}"')
    return estimator


def equalization(estimator, dir_path):
    """Reads equalization FIR filter or CSV settings

    Args:
        estimator: ImpulseResponseEstimator
        dir_path: Path to directory

    Returns:
        - Left side FIR as Numpy array or FrequencyResponse or None
        - Right side FIR as Numpy array or FrequencyResponse or None
    """
    if os.path.isfile(os.path.join(dir_path, 'eq.wav')):
        print('eq.wav is no longer supported, use eq.csv!')
    # Default for both sides
    eq_path = os.path.join(dir_path, 'eq.csv')
    eq_fr = None
    if os.path.isfile(eq_path):
        eq_fr = FrequencyResponse.read_from_csv(eq_path)

    # Left
    left_path = os.path.join(dir_path, 'eq-left.csv')
    left_fr = None
    if os.path.isfile(left_path):
        left_fr = FrequencyResponse.read_from_csv(left_path)
    elif eq_fr is not None:
        left_fr = eq_fr
    if left_fr is not None:
        left_fr.interpolate(f_step=1.01, f_min=10, f_max=estimator.fs / 2)

    # Right
    right_path = os.path.join(dir_path, 'eq-right.csv')
    right_fr = None
    if os.path.isfile(right_path):
        right_fr = FrequencyResponse.read_from_csv(right_path)
    elif eq_fr is not None:
        right_fr = eq_fr
    if right_fr is not None and right_fr != left_fr:
        right_fr.interpolate(f_step=1.01, f_min=10, f_max=estimator.fs / 2)

    # Plot
    if left_fr is not None or right_fr is not None:
        if left_fr == right_fr:
            # Both are the same, plot only one graph
            fig, ax = plt.subplots()
            fig.set_size_inches(12, 9)
            left_fr.plot_graph(fig=fig, ax=ax, show=False)
        else:
            # Left and right are different, plot two graphs in the same figure
            fig, ax = plt.subplots(1, 2)
            fig.set_size_inches(22, 9)
            if left_fr is not None:
                left_fr.plot_graph(fig=fig, ax=ax[0], show=False)
            if right_fr is not None:
                right_fr.plot_graph(fig=fig, ax=ax[1], show=False)
        save_fig_as_png(os.path.join(dir_path, 'plots', 'eq.png'), fig)

    return left_fr, right_fr


def headphone_compensation(estimator, dir_path):
    """Equalizes HRIR tracks with headphone compensation measurement.

    Args:
        estimator: ImpulseResponseEstimator instance
        dir_path: Path to output directory

    Returns:
        None
    """
    # Read WAV file
    hp_irs = HRIR(estimator)
    hp_irs.open_recording(os.path.join(dir_path, 'headphones.wav'), speakers=['FL', 'FR'])
    hp_irs.write_wav(os.path.join(dir_path, 'headphone-responses.wav'))

    # Frequency responses
    left = hp_irs.irs['FL']['left'].frequency_response()
    right = hp_irs.irs['FR']['right'].frequency_response()

    # Center by left channel
    gain = left.center([100, 10000])
    right.raw += gain

    # Compensate
    zero = FrequencyResponse(name='zero', frequency=left.frequency, raw=np.zeros(len(left.frequency)))
    left.compensate(zero, min_mean_error=False)
    right.compensate(zero, min_mean_error=False)

    # Headphone plots
    fig = plt.figure()
    gs = fig.add_gridspec(2, 3)
    fig.set_size_inches(22, 10)
    fig.suptitle('Headphones')

    # Left
    axl = fig.add_subplot(gs[0, 0])
    left.plot_graph(fig=fig, ax=axl, show=False)
    axl.set_title('Left')
    # Right
    axr = fig.add_subplot(gs[1, 0])
    right.plot_graph(fig=fig, ax=axr, show=False)
    axr.set_title('Right')
    # Sync axes
    sync_axes([axl, axr])

    # Combined
    _left = left.copy()
    _right = right.copy()
    gain_l = _left.center([100, 10000])
    gain_r = _right.center([100, 10000])
    ax = fig.add_subplot(gs[:, 1:])
    ax.plot(_left.frequency, _left.raw, linewidth=1, color='#1f77b4')
    ax.plot(_right.frequency, _right.raw, linewidth=1, color='#d62728')
    ax.plot(_left.frequency, _left.raw - _right.raw, linewidth=1, color='#680fb9')
    sl = np.logical_and(_left.frequency > 20, _left.frequency < 20000)
    stack = np.vstack([_left.raw[sl], _right.raw[sl], _left.raw[sl] - _right.raw[sl]])
    ax.set_ylim([np.min(stack) * 1.1, np.max(stack) * 1.1])
    axl.set_ylim([np.min(stack) * 1.1, np.max(stack) * 1.1])
    axr.set_ylim([np.min(stack) * 1.1, np.max(stack) * 1.1])
    ax.set_title('Comparison')
    ax.legend([f'Left raw {gain_l:+.1f} dB', f'Right raw {gain_r:+.1f} dB', 'Difference'], fontsize=8)
    ax.set_xlabel('Frequency (Hz)')
    ax.semilogx()
    ax.set_xlim([20, 20000])
    ax.set_ylabel('Amplitude (dBr)')
    ax.grid(True, which='major')
    ax.grid(True, which='minor')
    ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.0f}'))

    # Save headphone plots
    file_path = os.path.join(dir_path, 'plots', 'headphones.png')
    os.makedirs(os.path.split(file_path)[0], exist_ok=True)
    save_fig_as_png(file_path, fig)
    plt.close(fig)

    return left, right


def create_target(estimator, bass_boost_gain, bass_boost_fc, bass_boost_q, tilt):
    """Creates target frequency response with bass boost, tilt and high pass at 20 Hz"""
    target = FrequencyResponse(
        name='bass_and_tilt',
        frequency=FrequencyResponse.generate_frequencies(f_min=10, f_max=estimator.fs / 2, f_step=1.01)
    )
    target.raw = target.create_target(
        bass_boost_gain=bass_boost_gain,
        bass_boost_fc=bass_boost_fc,
        bass_boost_q=bass_boost_q,
        tilt=tilt
    )
    high_pass = FrequencyResponse(
        name='high_pass',
        frequency=[10, 18, 19, 20, 21, 22, 20000],
        raw=[-80, -5, -1.6, -0.6, -0.2, 0, 0]
    )
    high_pass.interpolate(f_min=10, f_max=estimator.fs / 2, f_step=1.01)
    # target.raw += high_pass.raw
    return target


def open_binaural_measurements(estimator, dir_path):
    """Opens binaural measurement WAV files.

    Args:
        estimator: ImpulseResponseEstimator
        dir_path: Path to directory

    Returns:
        HRIR instance
    """
    hrir = HRIR(estimator)
    pattern = r'^{pattern}\.wav$'.format(pattern=SPEAKER_LIST_PATTERN)  # FL,FR.wav
    for file_name in [f for f in os.listdir(dir_path) if re.match(pattern, f)]:
        # Read the speaker names from the file name into a list
        speakers = re.search(SPEAKER_LIST_PATTERN, file_name)[0].split(',')
        # Form absolute path
        file_path = os.path.join(dir_path, file_name)
        # Open the file and add tracks to HRIR
        hrir.open_recording(file_path, speakers=speakers)
    if len(hrir.irs) == 0:
        raise ValueError('No HRIR recordings found in the directory.')
    return hrir


def write_readme(file_path, hrir, fs):
    """Writes info and stats to readme file.

    Args:
        file_path: Path to readme file
        hrir: HRIR instance
        fs: Output sampling rate

    Returns:
        Readme string
    """
    if fs is None:
        fs = hrir.fs

    rt_name = 'Reverb'
    rt = None
    table = []
    speaker_names = sorted(hrir.irs.keys(), key=lambda x: SPEAKER_NAMES.index(x))
    for speaker in speaker_names:
        pair = hrir.irs[speaker]
        itd = np.abs(pair['right'].peak_index() - pair['left'].peak_index()) / hrir.fs * 1e6
        for side, ir in pair.items():
            # Zero for the first ear
            _itd = itd if side == 'left' and speaker[1] == 'R' or side == 'right' and speaker[1] == 'L' else 0.0
            # Use the largest decay time parameter available
            peak_ind, knee_point_ind, noise_floor, window_size = ir.decay_params()
            edt, rt20, rt30, rt60 = ir.decay_times(peak_ind, knee_point_ind, noise_floor, window_size)
            if rt60 is not None:
                rt_name = 'RT60'
                rt = rt60
            elif rt30 is not None:
                rt_name = 'RT30'
                rt = rt30
            elif rt20 is not None:
                rt_name = 'RT20'
                rt = rt20
            elif edt is not None:
                rt_name = 'EDT'
                rt = edt
            table.append([
                speaker,
                side,
                f'{noise_floor:.1f} dB',
                f'{_itd:.1f} us',
                f'{(knee_point_ind - peak_ind) / ir.fs * 1000:.1f} ms',
                f'{rt * 1000:.1f} ms' if rt is not None else '-'
            ])
    table_str = tabulate(
        table,
        headers=['Speaker', 'Side', 'PNR', 'ITD', 'Length', rt_name],
        tablefmt='github'
    )

        # --- 메인 귀 채널별 반사음 에너지(20–50 ms, 50–150 ms) 계산 ---
    frame    = lambda ms: int(ms * 1e-3 * fs)
    to_db    = lambda E, E0: 10 * np.log10(E / (E0 + 1e-20))
    energy_lines = ["\n**직접음 대비 반사음 에너지 (채널별, dB):**"]
    for speaker, channels in hrir.irs.items():
        # 스피커 이름 끝이 L이면 left, 아니면 right 채널만
        main_side = 'left' if speaker.endswith('L') else 'right'
        data      = channels[main_side].data
        peak      = np.argmax(np.abs(data))
        E0        = np.sum(data[peak : peak + frame(5)]**2)
        E_early   = np.sum(data[peak + frame(20) : peak + frame(50)]**2)
        E_mid     = np.sum(data[peak + frame(50) : peak + frame(150)]**2)
        energy_lines.append(
            f"- {speaker} ({main_side}): "
            f"Early (20–50 ms) {to_db(E_early, E0):.2f} dB, "
            f"Mid (50–150 ms) {to_db(E_mid,   E0):.2f} dB"
        )
    energy_str = "\n" + "\n".join(energy_lines)

    s = f'''# HRIR

    **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
    **Input sampling rate:** {hrir.fs} Hz  
    **Output sampling rate:** {fs} Hz  

    {table_str}
    {energy_str}
    '''
    s = re.sub('\n[ \t]+', '\n', s).strip()

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(s)

    return s


def create_cli():
    import argparse

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--c', type=float, default=1,
                            help='Retain headroom in milliseconds before the impulse peak. Default is 1 ms.')
    arg_parser.add_argument('--jamesdsp', action='store_true',
                            help='Generate an additional jamesdsp.wav containing only FL/FR IRs.')
    arg_parser.add_argument('--hangloose', action='store_true',
                   help='채널별 Hangloose 파일(스피커별 좌/우 WAV) 생성')    
    arg_parser.add_argument('--dir_path', type=str, required=True, help='Path to directory for recordings and outputs.')
    arg_parser.add_argument('--test_signal', type=str, default=argparse.SUPPRESS,
                            help='Path to sine sweep test signal or pickled impulse response estimator.')
    arg_parser.add_argument('--room_target', type=str, default=argparse.SUPPRESS,
                            help='Path to room target response AutoEQ style CSV file.')
    arg_parser.add_argument('--room_mic_calibration', type=str, default=argparse.SUPPRESS,
                            help='Path to room measurement microphone calibration file.')
    arg_parser.add_argument('--no_room_correction', action='store_false', dest='do_room_correction',
                            help='Skip room correction.')
    arg_parser.add_argument('--no_headphone_compensation', action='store_false', dest='do_headphone_compensation',
                            help='Skip headphone compensation.')
    arg_parser.add_argument('--no_equalization', action='store_false', dest='do_equalization',
                            help='Skip equalization.')
    arg_parser.add_argument('--fs', type=int, default=argparse.SUPPRESS, help='Output sampling rate in Hertz.')
    arg_parser.add_argument('--plot', action='store_true', help='Plot graphs for debugging.')
    arg_parser.add_argument('--channel_balance', type=str, default=argparse.SUPPRESS,
                            help='Channel balance correction by equalizing left and right ear results to the same '
                                 'level or frequency response. "trend" equalizes right side by the difference trend '
                                 'of right and left side. "left" equalizes right side to left side fr, "right" '
                                 'equalizes left side to right side fr, "avg" equalizes both to the average fr, "min" '
                                 'equalizes both to the minimum of left and right side frs. Number values will boost '
                                 'or attenuate right side relative to left side by the number of dBs. "mids" is the '
                                 'same as the numerical values but guesses the value automatically from mid frequency '
                                 'levels.')
    arg_parser.add_argument('--decay', type=str, default=argparse.SUPPRESS,
                            help='Target decay time in milliseconds to reach -60 dB. When the natural decay time is '
                                 'longer than the target decay time, a downward slope will be applied to decay tail. '
                                 'Decay cannot be increased with this. By default no decay time adjustment is done. '
                                 'A comma separated list of channel name and  reverberation time pairs, separated by '
                                 'a colon. If only a single numeric value is given, it is used for all channels. When '
                                 'some channel names are give but not all, the missing channels are not affected. For '
                                 'example "--decay=300" or "--decay=FL:500,FC:100,FR:500,SR:700,BR:700,BL:700,SL:700" '
                                 'or "--decay=FC:100".')
    arg_parser.add_argument('--target_level', type=float, default=argparse.SUPPRESS,
                            help='Target average gain level for left and right channels. This will sum together all '
                                 'left side impulse responses and right side impulse responses respectively and take '
                                 'the average gain from mid frequencies. The averaged level is then normalized to the '
                                 'given target level. This makes it possible to compare HRIRs with somewhat similar '
                                 'loudness levels. This should be negative in most cases to avoid clipping.')
    arg_parser.add_argument('--fr_combination_method', type=str, default='average',
                            help='Method for combining frequency responses of generic room measurements if there are '
                                 'more than one tracks in the file. "average" will simply average the frequency'
                                 'responses. "conservative" will take the minimum absolute value for each frequency '
                                 'but only if the values in all the measurements are positive or negative at the same '
                                 'time.')
    arg_parser.add_argument('--specific_limit', type=float, default=400,
                            help='Upper limit for room equalization with speaker-ear specific room measurements. '
                                 'Equalization will drop down to 0 dB at this frequency in the leading octave. 0 '
                                 'disables limit.')
    arg_parser.add_argument('--generic_limit', type=float, default=300,
                            help='Upper limit for room equalization with generic room measurements. '
                                 'Equalization will drop down to 0 dB at this frequency in the leading octave. 0 '
                                 'disables limit.')
    arg_parser.add_argument('--bass_boost', type=str, default=argparse.SUPPRESS,
                            help='Bass boost shelf. Sub-bass frequencies will be boosted by this amount. Can be '
                                 'either a single value for a gain in dB or a comma separated list of three values for '
                                 'parameters of a low shelf filter, where the first is gain in dB, second is center '
                                 'frequency (Fc) in Hz and the last is quality (Q). When only a single value (gain) is '
                                 'given, default values for Fc and Q are used which are 105 Hz and 0.76, respectively. '
                                 'For example "--bass_boost=6" or "--bass_boost=6,150,0.69".')
    arg_parser.add_argument('--tilt', type=float, default=argparse.SUPPRESS,
                            help='Target tilt in dB/octave. Positive value (upwards slope) will result in brighter '
                                 'frequency response and negative value (downwards slope) will result in darker '
                                 'frequency response. 1 dB/octave will produce nearly 10 dB difference in '
                                 'desired value between 20 Hz and 20 kHz. Tilt is applied with bass boost and both '
                                 'will affect the bass gain.')
    
    known_args, unknown_args = arg_parser.parse_known_args()
    args = vars(known_args)

    if 'bass_boost' in args:
        bass_boost = args['bass_boost'].split(',')
        if len(bass_boost) == 1:
            args['bass_boost_gain'] = float(bass_boost[0])
            args['bass_boost_fc'] = 105
            args['bass_boost_q'] = 0.76
        elif len(bass_boost) == 3:
            args['bass_boost_gain'] = float(bass_boost[0])
            args['bass_boost_fc'] = float(bass_boost[1])
            args['bass_boost_q'] = float(bass_boost[2])
        else:
            raise ValueError('"--bass_boost" must have one value or three values separated by commas!')
        del args['bass_boost']
    if 'decay' in args:
        decay = dict()
        try:
            # Single float value
            decay = {ch: float(args['decay']) / 1000 for ch in SPEAKER_NAMES}
        except ValueError:
            # Channels separated
            for ch_t in args['decay'].split(','):
                decay[ch_t.split(':')[0].upper()] = float(ch_t.split(':')[1]) / 1000
        args['decay'] = decay
    if  'c' in args:
        args['head_ms'] = args['c']
        del args['c']

        args['early_windows'] = parse_early_args(unknown_args)
    return args


if __name__ == '__main__':
    main(**create_cli())
