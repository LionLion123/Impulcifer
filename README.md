Impulcifer는 Jaakko Pasanen의 소프트웨어입니다.
오랜기간 HRIR/BRIR에 대한 다양한 시도를 하고, 그러한 경험중에 꽤 많은 아이디어 혹은 불편한 부분, 몇가지 문제가 있었지만 개발자는 현재 바쁘기때문에 제가 원하는 요소를 한국 유저들과 공유하기 위해 이렇게 만들어봅니다.

Impulcifer is a software developed by Jaakko Pasanen.
After many years of experimenting with HRIR/BRIR, I came up with quite a few ideas, experienced some inconveniences, and encountered a few issues. However, since the developer is currently busy, I decided to create this version to share the features I want with Korean users.

# Changes # 변경사항


### 1 ###
cavern의 소프트웨어+VBcable 16ch로 Atmos 및 높이채널 업믹스에 대한 활용도가 더욱 넓어졌습니다. 따라서 WL,WR.wav / TFL,TFR.wav / TSL,TSR.wav / TBL,TBR.wav 까지 모두 처리될수있도록 합니다. (hrir.wav의 순서를 그대로 사용하면 되기때문에 hrir.wav는 순서에 맞게 하였고, hesuvi.wav는 제가 쓰기 편하게끔 해놨습니다. 어차피 hesuvi코드로는 16채널이 되지않기때문에 직접 코드를 작성해야합니다.)

By combining Cavern's software with VB-Cable 16ch, the usability for Atmos and height channel upmixing has been greatly expanded.
Therefore, it now supports processing of WL, WR.wav / TFL, TFR.wav / TSL, TSR.wav / TBL, TBR.wav.
(Since the original order of hrir.wav can be used as-is, I arranged hrir.wav accordingly. As for hesuvi.wav, I customized it for easier personal use.
In any case, since HeSuVi’s code does not support 16 channels, the code must be written manually.)


### 2 ###
임펄스 피크감지는 뛰어나지만, 때로는 문제가 없는 임펄스도 타이밍 변조를 합니다.
그러한 부분은 정위감,선명도의 하락으로 이어지며 그에 대한 정렬이 확실하게 적용될수있도록 변경했습니다.

Impulse peak detection is excellent, but sometimes it alters the timing of impulses that are actually fine.
This leads to a degradation in localization and clarity, so I made adjustments to ensure proper alignment is consistently applied.


### 3 ###
서라운드 채널간에 딜레이 및 게인 조절을 비활성화 합니다.
이상적인 몰입형오디오쪽에서는 매우 미세한 단위로도 정확하게 매칭되는 것을 권장하기도합니다. - 특히나 이것은 근거리(약1m)의 경우에 더욱 명확합니다.
바이노럴 기준으로 96000샘플레이트 기준 10us까지도 사람은 인지할수있으며 이것을 재생단에서 굳이 딜레이를 추가할 이유가 없기때문에 비활성화합니다.

I disabled delay and gain adjustments between surround channels.
In ideal immersive audio setups, it’s often recommended that channels be matched with extremely fine precision—this becomes even more critical at close listening distances (around 1 meter).
In binaural playback, humans can perceive differences as small as 10 microseconds at a 96kHz sample rate,
so there’s no reason to add delay during playback—hence, the feature is disabled.


### 4 ###
--c=10 혹은 --c=50 (ms단위) 를 입력하여 피크이전, 사전절단의 윈도잉을 정할수 있게끔 했습니다. 인수를 사용하지않으면 기본값으로 적용됩니다.
SOTA 기준을 충족시키는 DRC를 잘 적용한다면 대부분의 사전링잉이 억제되지만, 그래도 최소한의 사전딜레이 확보가 되어야합니다.
뿐만 아니라 Bacch와 같은 XTC를 수행할때에도 사전응답은 반드시 확보되어야 올바르게 작동됩니다.
따라서 사용자가 원할수 있게끔 사전딜레이 인수 옵션을 넣었습니다.

I added an option to set the windowing for pre-peak truncation by using --c=10 or --c=50 (in milliseconds). If no argument is provided, a default value will be applied.
While a well-implemented DRC that meets SOTA standards can suppress most pre-ringing, it's still essential to ensure a minimum amount of pre-delay.
Moreover, when performing XTC processing such as Bacch, pre-response must be properly secured for it to function correctly.
Therefore, I included a pre-delay argument option so that users can adjust it as needed.


### 5 ###
하이패스를 우회합니다.
기본 impulcifer의 문구에선 하이패스가 적용됩니다. (약 10~22hz까지)
바이노럴 가상화에 이용되는 대부분의 헤드폰들은 올바르게 극저음을 재생하지 못합니다. 그렇기때문에 불필요한 부스트를 막기위한 개발자의 의도는 이해됩니다.
하지만 그럼에도 더 깊게 탐구하며 가상의 공간까지 창조하는 고급유저들 대부분은 그들의 응답 자체가 마음대로 변조되는 것을 원하지 않습니다.
또한 이미 룸응답에서도 이상적인 미니멈페이즈(DC제거된)의 형태를 기반으로 DRC가 적용되기때문에 이에 대한 부분은 걱정이 없습니다.
따라서 약 10~22hz에 적용되는 하이패스를 우회합니다.

The high-pass filter is bypassed.

In the default behavior of Impulcifer, a high-pass filter is applied (around 10–22 Hz).
Most headphones used for binaural virtualization cannot accurately reproduce ultra-low frequencies,
so the developer’s intention to prevent unnecessary low-frequency boost is understandable.
However, advanced users who delve deeper and aim to create immersive virtual spaces generally do not want their frequency response to be arbitrarily altered.
Furthermore, since DRC is already applied based on an ideal minimum-phase (DC-removed) room response, there's no concern regarding low-frequency anomalies.
Therefore, the high-pass filter applied around 10–22 Hz has been bypassed.
