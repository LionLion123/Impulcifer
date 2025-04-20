Impulcifer는 Jaakko Pasanen의 소프트웨어입니다.
오랜기간 HRIR/BRIR에 대한 다양한 시도를 하고, 그러한 경험중에 꽤 많은 아이디어 혹은 불편한 부분, 몇가지 문제가 있었지만 개발자는 현재 바쁘기때문에 제가 원하는 요소를 한국 유저들과 공유하기 위해 이렇게 만들어봅니다.

Impulcifer is a software developed by Jaakko Pasanen.
After many years of experimenting with HRIR/BRIR, I came up with quite a few ideas, experienced some inconveniences, and encountered a few issues. However, since the developer is currently busy, I decided to create this version to share the features I want with Korean users.

# Changes # 변경사항

#1
cavern의 소프트웨어+VBcable 16ch로 Atmos 및 높이채널 업믹스에 대한 활용도가 더욱 넓어졌습니다. 따라서 WL,WR.wav / TFL,TFR.wav / TSL,TSR.wav / TBL,TBR.wav 까지 모두 처리될수있도록 합니다. (hrir.wav의 순서를 그대로 사용하면 되기때문에 hrir.wav는 순서에 맞게 하였고, hesuvi.wav는 내가 쓰기 편하게끔 해놨습니다. 어차피 hesuvi코드로는 16채널이 되지않기때문에 직접 코드를 작성해야합니다.)

By combining Cavern's software with VB-Cable 16ch, the usability for Atmos and height channel upmixing has been greatly expanded.
Therefore, it now supports processing of WL, WR.wav / TFL, TFR.wav / TSL, TSR.wav / TBL, TBR.wav.
(Since the original order of hrir.wav can be used as-is, I arranged hrir.wav accordingly. As for hesuvi.wav, I customized it for easier personal use.
In any case, since HeSuVi’s code does not support 16 channels, the code must be written manually.)


#2
임펄스 피크감지는 뛰어나지만, 때로는 문제가 없는 임펄스도 타이밍 변조를 합니다.
그러한 부분은 정위감,선명도의 하락으로 이어지며 그에 대한 정렬이 확실하게 적용될수있도록 변경했습니다.

Impulse peak detection is excellent, but sometimes it alters the timing of impulses that are actually fine.
This leads to a degradation in localization and clarity, so I made adjustments to ensure proper alignment is consistently applied.

#3
서라운드 채널간에 딜레이 및 게인 조절을 비활성화 합니다.
이상적인 몰입형오디오쪽에서는 매우 미세한 단위로도 정확하게 매칭되는 것을 권장하기도합니다. - 특히나 이것은 근거리(약1m)의 경우에 더욱 명확합니다.
바이노럴 기준으로 96000샘플레이트 기준 10us까지도 사람은 인지할수있으며 이것을 재생단에서 굳이 딜레이를 추가할 이유가 없기때문에 비활성화합니다.

I disabled delay and gain adjustments between surround channels.
In ideal immersive audio setups, it’s often recommended that channels be matched with extremely fine precision—this becomes even more critical at close listening distances (around 1 meter).
In binaural playback, humans can perceive differences as small as 10 microseconds at a 96kHz sample rate,
so there’s no reason to add delay during playback—hence, the feature is disabled.

#4
