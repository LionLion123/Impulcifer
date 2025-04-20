Impulcifer is a software developed by Jaakko Pasanen.
After many years of experimenting with HRIR/BRIR, I came up with quite a few ideas, experienced some inconveniences, and encountered a few issues. However, since the developer is currently busy, I decided to create this version to share the features I want with Korean users.

# Changes #
1.By combining Cavern's software with VB-Cable 16ch, the usability for Atmos and height channel upmixing has been greatly expanded.
Therefore, it now supports processing of WL, WR.wav / TFL, TFR.wav / TSL, TSR.wav / TBL, TBR.wav.
(Since the original order of hrir.wav can be used as-is, I arranged hrir.wav accordingly. As for hesuvi.wav, I customized it for easier personal use.
In any case, since HeSuVi’s code does not support 16 channels, the code must be written manually.)

2.Impulse peak detection is excellent, but sometimes it alters the timing of impulses that are actually fine.
This leads to a degradation in localization and clarity, so I made adjustments to ensure proper alignment is consistently applied.

3.I disabled delay and gain adjustments between surround channels.
In ideal immersive audio setups, it’s often recommended that channels be matched with extremely fine precision—this becomes even more critical at close listening distances (around 1 meter).
In binaural playback, humans can perceive differences as small as 10 microseconds at a 96kHz sample rate,
so there’s no reason to add delay during playback—hence, the feature is disabled.
