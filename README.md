
![gif_046](https://github.com/user-attachments/assets/7931c04d-c3ad-4cd5-8f58-84ee40d7bb83)
![gif_047](https://github.com/user-attachments/assets/3ea1cc5b-8bbc-4f92-9b61-71bab0252e3e)

한국 스피커갤러리,BRIR갤러리/Audiosciencereview에서 활동합니다.

https://gall.dcinside.com/mgallery/board/lists?id=speakers

Impulcifer는 Jaakko Pasanen의 소프트웨어입니다.


오랜기간 HRIR/BRIR에 대한 다양한 시도를 하고, 그러한 경험중에 꽤 많은 아이디어 혹은 불편한 부분, 몇가지 문제가 있었지만 개발자는 현재 바쁘기때문에 제가 원하는 요소를 한국 유저들과 공유하기 위해 이렇게 만들어봅니다.


대부분은 GPT의 도움을 받아 직접 실행해보며 문제없는 부분만 반영합니다.

Impulcifer is a software developed by Jaakko Pasanen.
After many years of experimenting with HRIR/BRIR, I came up with quite a few ideas, experienced some inconveniences, and encountered a few issues.

However, since the developer is currently busy, I decided to create this version to share the features I want with Korean users.

For the most part, I execute it myself with GPT’s help and only apply the parts that work without issues.


-----------------------------------------------
# Changes # 변경사항
-----------------------------------------------
### 1 
cavern의 소프트웨어+VBcable 16ch로 Atmos 및 높이채널 업믹스에 대한 활용도가 더욱 넓어졌습니다.


따라서 WL,WR.wav / TFL,TFR.wav / TSL,TSR.wav / TBL,TBR.wav 까지 모두 처리될수있도록 합니다.


(hrir.wav의 순서를 그대로 사용하면 되기때문에 hrir.wav는 순서에 맞게 하였고, hesuvi.wav는 제가 쓰기 편하게끔 해놨습니다. 어차피 hesuvi코드로는 16채널이 되지않기때문에 직접 코드를 작성해야합니다.)

By combining Cavern's software with VB-Cable 16ch, the usability for Atmos and height channel upmixing has been greatly expanded.


Therefore, it now supports processing of WL, WR.wav / TFL, TFR.wav / TSL, TSR.wav / TBL, TBR.wav.


(Since the original order of hrir.wav can be used as-is, I arranged hrir.wav accordingly. As for hesuvi.wav, I customized it for easier personal use.
In any case, since HeSuVi’s code does not support 16 channels, the code must be written manually.)

-----------------------------------------------

### 2 
![002](https://github.com/user-attachments/assets/f90fda17-ce6e-495c-8c04-370dedfa4f0f)

(예시이미지의 위는 원본코드, 아래는 수정코드 적용입니다.)


임펄스 피크감지는 뛰어나지만, 때로는 문제가 없는 임펄스도 타이밍 변조를 합니다.


그러한 부분은 정위감,선명도의 하락으로 이어지며 그에 대한 정렬이 확실하게 적용될수있도록 변경했습니다.

(In the example image, the top shows the original code, and the bottom shows the revised code.)


Impulse peak detection is excellent, but sometimes it alters the timing of impulses that are actually fine.


This leads to a degradation in localization and clarity, so I made adjustments to ensure proper alignment is consistently applied.

-----------------------------------------------

### 3 
![002](https://github.com/user-attachments/assets/fe8996ad-0998-406d-a9a1-4ef679809b64)
![003](https://github.com/user-attachments/assets/19127f81-ef8d-44c0-b601-55df5d3f0760)

(예시이미지의 위는 원본코드, 아래는 수정코드 적용입니다. 의도적으로 같은 채널을 이름만 다르게 하여 서라운드 채널로 할당한 것이며, 이것은 애초에 같은 채널이기때문에 딜레이가 같아야함을 보여주기위한 예시입니다.)


서라운드 채널간에 딜레이 및 게인 조절을 비활성화 합니다.


이상적인 몰입형오디오쪽에서는 매우 미세한 단위로도 정확하게 매칭되는 것을 권장하기도합니다. - 특히나 이것은 근거리(약1m)의 경우에 더욱 명확합니다.


바이노럴 기준으로 96000샘플레이트 기준 10us까지도 사람은 인지할수있으며 이것을 재생단에서 굳이 딜레이를 추가할 이유가 없기때문에 비활성화합니다.


(In the example image, the upper part shows the original code, and the lower part shows the modified code applied. It intentionally assigns the same channel under a different name as a surround channel to illustrate that, since it’s the same channel to begin with, its delay must be identical.)


I disabled delay and gain adjustments between surround channels.


In ideal immersive audio setups, it’s often recommended that channels be matched with extremely fine precision—this becomes even more critical at close listening distances (around 1 meter).


In binaural playback, humans can perceive differences as small as 10 microseconds at a 96kHz sample rate,
so there’s no reason to add delay during playback—hence, the feature is disabled.

-----------------------------------------------

### 4 

--c=10 혹은 --c=50 (ms단위) 를 입력하여 피크이전, 사전절단의 윈도잉을 정할수 있게끔 했습니다. 인수를 사용하지않으면 기본값으로 적용됩니다.


SOTA 기준을 충족시키는 DRC를 잘 적용한다면 대부분의 사전링잉이 억제되지만, 그래도 최소한의 사전딜레이 확보가 되어야합니다.


뿐만 아니라 Bacch와 같은 XTC를 수행할때에도 사전응답은 반드시 확보되어야 올바르게 작동됩니다.


따라서 사용자가 원할수 있게끔 사전딜레이 인수 옵션을 넣었습니다.

I added an option to set the windowing for pre-peak truncation by using --c=10 or --c=50 (in milliseconds). If no argument is provided, a default value will be applied.


While a well-implemented DRC that meets SOTA standards can suppress most pre-ringing, it's still essential to ensure a minimum amount of pre-delay.


Moreover, when performing XTC processing such as Bacch, pre-response must be properly secured for it to function correctly.


Therefore, I included a pre-delay argument option so that users can adjust it as needed.

-----------------------------------------------

### 5 
![002](https://github.com/user-attachments/assets/744a8dc5-61ab-4d0c-bec4-9b2e26711755)
![003](https://github.com/user-attachments/assets/b1e665b0-f0a9-44d1-9963-7179d1418516)

하이패스를 우회합니다.


기본 impulcifer의 문구에선 하이패스가 적용됩니다. (약 10-22hz까지)


바이노럴 가상화에 이용되는 대부분의 헤드폰들은 올바르게 극저음을 재생하지 못합니다.


그렇기때문에 불필요한 부스트를 막기위한 개발자의 의도는 이해됩니다.


하지만 그럼에도 더 깊게 탐구하며 가상의 공간까지 창조하는 고급유저들 대부분은 그들의 응답 자체가 마음대로 변조되는 것을 원하지 않습니다.


또한 이미 룸응답에서도 이상적인 미니멈페이즈(DC제거된)의 형태를 기반으로 DRC가 적용되기때문에 이에 대한 부분은 걱정이 없습니다.


따라서 약 10-22hz에 적용되는 하이패스를 우회합니다.


The high-pass filter is bypassed.


In the default behavior of Impulcifer, a high-pass filter is applied (around 10–22 Hz).


Most headphones used for binaural virtualization cannot accurately reproduce ultra-low frequencies,
so the developer’s intention to prevent unnecessary low-frequency boost is understandable.


However, advanced users who delve deeper and aim to create immersive virtual spaces generally do not want their frequency response to be arbitrarily altered.


Furthermore, since DRC is already applied based on an ideal minimum-phase (DC-removed) room response, there's no concern regarding low-frequency anomalies.


Therefore, the high-pass filter applied around 10–22 Hz has been bypassed.


-----------------------------------------------

### 6
![image](https://github.com/user-attachments/assets/152603cd-8ba4-401d-aa08-b9594ac20881)
![image](https://github.com/user-attachments/assets/e022b813-4e93-41e5-862c-c04499b66ec3)

--jamesdsp 인수를 입력하면 바로 제임스Dsp 앱에 사용할수있는 트루스테레오 IR파일이 만들어집니다. 파일명은 같은 폴더내에 jamesdsp.wav로 저장됩니다.


폴더내에 FL,FR.wav를 제외한 다른 채널들의 파일이 있더라도, --jamesdsp를 입력하면 FL,FR만을 기준으로 정규화되어 스테레오 파일을 따로 만듭니다.


When you specify the --jamesdsp argument, a TrueStereo IR file ready for use in the JamesDSP app is generated immediately. The file is saved in the same folder under the name jamesdsp.wav.


Even if the folder contains files for channels other than FL.wav and FR.wav, using --jamesdsp will normalize based only on FL and FR and produce a separate stereo file.


-----------------------------------------------

### 7
![image](https://github.com/user-attachments/assets/f9f597ee-fc3e-4c37-91d4-fffa9ea93839)
![image](https://github.com/user-attachments/assets/e6b1b68e-040e-44d4-aecc-8ea7e47019f9)
![image](https://github.com/user-attachments/assets/4a53811a-e294-4089-ac03-a6d72f14b9cd)


--hangloose 인수를 입력하면 바로 Hangloose Convolver에  사용할수있는 각 채널 스테레오 IR파일들이 Hangloose라는 새로운 폴더에 만들어집니다.


When you specify the --hangloose argument, stereo IR files for each channel that can be used with the Hangloose Convolver are generated immediately in a new folder named “Hangloose.”


-----------------------------------------------

### 8
![image](https://github.com/user-attachments/assets/33840a8e-b244-4ab4-ab63-a75a406fd39c)


적용된 노멀라이즈 게인이 표시됩니다. 그리고 Readme의 내용들도 바로 표시됩니다.


REW로 직접 확인하는 것이 정확하지만, Readme 파일보며 간단하게 확인하고 싶을때도 있으니까요.


하지만 매번 Readme txt파일을 찾아서 여는 것 또한 번거롭기때문에 같이 표시되도록 했습니다.


The applied normalized gain is displayed, and the contents of the Readme are shown immediately as well.


While checking directly in REW is more accurate, sometimes you just want a quick glance at the Readme. But having to locate and open the Readme txt file each time is tedious, so I’ve made it so they’re displayed together.


-----------------------------------------------
# Items under Consideration # 고려하고 있는 부분들
-----------------------------------------------

### 1
가끔 처리하다보면 ValueError: cannot convert float NaN to integer 라는 에러가 발생할때가 있습니다.


추측으로는 -60db아래 임펄스의 노이즈플로어부분에서 이상한 피크 같은게 있거나 할때 저러는 것 같습니다.


대부분의 응답에선 발생하지 않지만 감쇠가 너무 빠른 응답을 재루프백했을 경우에도 종종 그러구요.


몇년전 개발자에게 문의했었지만 바쁘기때문에 언젠간 직접 고치는게 나을듯합니다.


Sometimes during processing, I encounter an error: ValueError: cannot convert float NaN to integer.


I suspect this happens when there’s some strange peak in the noise floor of the impulse below –60 dB.


It doesn’t occur in most responses, but it also happens occasionally when re-loopbacking a response with very fast attenuation.


I asked the developer about this a few years ago, but since they’re busy, it’s probably better that I fix it myself someday.

-----------------------------------------------


### 2
impulcifer의 채널밸런스 기능과는 별개로 녹음당시에 마이크착용,삽입깊이등의 편차로 인한 경우에는 왼쪽채널, 오른쪽채널이 아니라 왼쪽귀, 오른쪽귀 응답을 보정해야합니다.

FL-L,FR-L / FR-R,FL-R 이렇게 말이죠. 이 기능을 REW의 MTW개념을 섞어서 극도로 짧은 게이팅을 대역별로 다르게 적용하여 착용 편차만을 보정하는 것은 REW에서 충분히 가능합니다.

이 부분을 impulcifer 내부에도 적용시킬까 고민중입니다.


Separately from Impulcifer’s channel balance function, when there are deviations in microphone placement or insertion depth during recording, you need to correct for left‑ear and right‑ear responses rather than left‑channel and right‑channel.


In other words, FL‑L, FR‑L / FR‑R, FL‑R. In REW, it’s entirely possible to compensate solely for fit deviations by combining the MTW concept and applying ultrashort gating differently across frequency bands.


I’m considering applying this approach within Impulcifer as well.


-----------------------------------------------
### 3
BacchORC와 같은 바이노럴 룸보정(DRC) 기능을 적용해볼까 싶은 생각도 하고있습니다.

impulcifer에 룸파일, 타겟등을 적용하여 룸이큐를 처리되게끔 할수도 있지만, 그것과는 별개로 바이노럴의 특징을 고려하여 개인의 좌우 신체편차를 보정하고

더 나아가 각 스피커 각도에서 필연적으로 발생하는 귓바퀴의 착색을 DF(혹은 룸게인 가중치가 부여된 타겟)에 맞게 교정하여, 결과적으로 투명함을 얻을수 있고 스피커가 본질적으로 사라지게 됩니다.

(스피커와 룸, 그리고 귓바퀴의 착색이 스피커가 있다는 것을 인지하게 하는 요소들입니다.)

다만 이건 개인마다 DF의 차이가 분명히 존재하고, 개인마다 녹음 방법이 정확히 같지않기때문에 어떻게 공용화해서 적용시킬지는 고민중입니다.


I’m also considering applying a binaural room correction (DRC) function like BacchORC.


While it’s possible to process room EQ in Impulcifer by applying room files and targets, separately, by taking binaural characteristics into account, you can correct for individual left‑right anatomical variations and, furthermore, correct pinna coloration that inevitably occurs at each speaker angle to match the DF (or a target with room‑gain weighting). The result is transparency, effectively making the speakers disappear.


(The speaker, the room, and pinna coloration are the elements that make us aware of the presence of speakers.)


However, since DF differences clearly exist among individuals and recording methods aren’t exactly the same for everyone, I’m pondering how to generalize and apply this.


-----------------------------------------------
### 4
plot은 초기사용자들에게 나쁘지않은 정보들을 제공해주지만 기존의 plot들중 대부분은 잘 보지않게 되었고, 결국은 REW를 사용하여 확인합니다.


BRIR사용자들에 제일 도움이 될만한 간단한 그래프는 일단 양이응답 임펄스 오버레이형태이지않을까 싶습니다. 더나아가 ILD,IPD,IACC,ETC 등의 지표도 같이 보여주면 좋을 것 같습니다. 


Plots provide useful information for novice users, but most of the existing plots are seldom viewed, and users ultimately use REW to verify.


The simplest graph that would be most helpful for BRIR users would probably be a stereo impulse response overlay. Furthermore, it would be beneficial to also display metrics such as ILD, IPD, IACC, and ETC.
