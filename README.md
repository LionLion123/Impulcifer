
![gif_046](https://github.com/user-attachments/assets/7931c04d-c3ad-4cd5-8f58-84ee40d7bb83)
![gif_047](https://github.com/user-attachments/assets/3ea1cc5b-8bbc-4f92-9b61-71bab0252e3e)

한국 스피커갤러리,BRIR갤러리/Audiosciencereview에서 활동합니다.

https://gall.dcinside.com/mgallery/board/lists?id=speakers

Impulcifer는 Jaakko Pasanen의 소프트웨어입니다.


오랜기간 HRIR/BRIR에 대한 다양한 시도를 하고, 그러한 경험중에 꽤 많은 아이디어 혹은 불편한 부분, 몇가지 문제가 있었지만 개발자는 현재 바쁘기때문에 제가 원하는 요소를 한국 유저들과 공유하기 위해 이렇게 만들어봅니다.


대부분은 GPT의 도움을 받아 직접 실행해보며 문제없는 부분만 반영합니다.


-----------------------------------------------
# Changes # 변경사항
-----------------------------------------------
### 1 
cavern의 소프트웨어+VBcable 16ch로 Atmos 및 높이채널 업믹스에 대한 활용도가 더욱 넓어졌습니다.


따라서 WL,WR.wav / TFL,TFR.wav / TSL,TSR.wav / TBL,TBR.wav 까지 모두 처리될수있도록 합니다.


(hrir.wav의 순서를 그대로 사용하면 되기때문에 hrir.wav는 순서에 맞게 하였고, hesuvi.wav는 제가 쓰기 편하게끔 해놨습니다. 어차피 hesuvi코드로는 16채널이 되지않기때문에 직접 코드를 작성해야합니다.)


-----------------------------------------------

### 2 
![002](https://github.com/user-attachments/assets/f90fda17-ce6e-495c-8c04-370dedfa4f0f)

(예시이미지의 위는 원본코드, 아래는 수정코드 적용입니다.)


임펄스 피크감지는 뛰어나지만, 때로는 문제가 없는 임펄스도 타이밍 변조를 합니다.


그러한 부분은 정위감,선명도의 하락으로 이어지며 그에 대한 정렬이 확실하게 적용될수있도록 변경했습니다.


-----------------------------------------------

### 3 
![002](https://github.com/user-attachments/assets/fe8996ad-0998-406d-a9a1-4ef679809b64)
![003](https://github.com/user-attachments/assets/19127f81-ef8d-44c0-b601-55df5d3f0760)

(예시이미지의 위는 원본코드, 아래는 수정코드 적용입니다. 의도적으로 같은 채널을 이름만 다르게 하여 서라운드 채널로 할당한 것이며, 이것은 애초에 같은 채널이기때문에 딜레이가 같아야함을 보여주기위한 예시입니다.)


서라운드 채널간에 딜레이 및 게인 조절을 비활성화 합니다.


이상적인 몰입형오디오쪽에서는 매우 미세한 단위로도 정확하게 매칭되는 것을 권장하기도합니다. - 특히나 이것은 근거리(약1m)의 경우에 더욱 명확합니다.


바이노럴 기준으로 96000샘플레이트 기준 10us까지도 사람은 인지할수있으며 이것을 재생단에서 굳이 딜레이를 추가할 이유가 없기때문에 비활성화합니다.


-----------------------------------------------

### 4 

--c=10 혹은 --c=50 (ms단위) 를 입력하여 피크이전, 사전절단의 윈도잉을 정할수 있게끔 했습니다. 인수를 사용하지않으면 기본값으로 적용됩니다.


SOTA 기준을 충족시키는 DRC를 잘 적용한다면 대부분의 사전링잉이 억제되지만, 그래도 최소한의 사전딜레이 확보가 되어야합니다.


뿐만 아니라 Bacch와 같은 XTC를 수행할때에도 사전응답은 반드시 확보되어야 올바르게 작동됩니다.


따라서 사용자가 원할수 있게끔 사전딜레이 인수 옵션을 넣었습니다.


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


-----------------------------------------------

### 6
![image](https://github.com/user-attachments/assets/152603cd-8ba4-401d-aa08-b9594ac20881)
![image](https://github.com/user-attachments/assets/e022b813-4e93-41e5-862c-c04499b66ec3)

--jamesdsp 인수를 입력하면 바로 제임스Dsp 앱에 사용할수있는 트루스테레오 IR파일이 만들어집니다. 파일명은 같은 폴더내에 jamesdsp.wav로 저장됩니다.


폴더내에 FL,FR.wav를 제외한 다른 채널들의 파일이 있더라도, --jamesdsp를 입력하면 FL,FR만을 기준으로 정규화되어 스테레오 파일을 따로 만듭니다.


-----------------------------------------------

### 7
![image](https://github.com/user-attachments/assets/f9f597ee-fc3e-4c37-91d4-fffa9ea93839)
![image](https://github.com/user-attachments/assets/e6b1b68e-040e-44d4-aecc-8ea7e47019f9)
![image](https://github.com/user-attachments/assets/4a53811a-e294-4089-ac03-a6d72f14b9cd)


--hangloose 인수를 입력하면 바로 Hangloose Convolver에  사용할수있는 각 채널 스테레오 IR파일들이 Hangloose라는 새로운 폴더에 만들어집니다.


-----------------------------------------------


### 8
![image](https://github.com/user-attachments/assets/33840a8e-b244-4ab4-ab63-a75a406fd39c)


적용된 노멀라이즈 게인이 표시됩니다. 그리고 Readme의 내용들도 바로 표시됩니다.


REW로 직접 확인하는 것이 정확하지만, Readme 파일보며 간단하게 확인하고 싶을때도 있으니까요.


하지만 매번 Readme txt파일을 찾아서 여는 것 또한 번거롭기때문에 같이 표시되도록 했습니다.


-----------------------------------------------


### 9
![image](https://github.com/user-attachments/assets/907c5ef0-c8fb-411c-b848-b374308ae907)


직접음 대비 20-50ms의 초기반사 레벨과 50-150ms 반사 레벨을 표시합니다.


davidgriesinger의 연구에 따르면 공간지각 스트림은 약 50ms를 분기점으로 삼으며 50ms이전엔 전경, 이후부턴 배경스트림으로 자극되어 인지됩니다.


다만 50ms~150ms의 에너지는 음표가 끝나기전(음표의 길이 약 200ms)에 과도하게 남아있다면 명료도를 크게 해치게 됩니다.


따라서 50~150ms의 에너지는 최소화하며 전체 RT의 길이를 낮은 레벨로 길게 가져가는 것이 올바른 공간 확장의 예시중 하나입니다.


-----------------------------------------------


### 10
![image](https://github.com/user-attachments/assets/51e6319c-6bd5-4cce-920a-d180bdcdda6d)
![image](https://github.com/user-attachments/assets/199d1ad6-ee10-44da-bcfc-97eaf253a02e)


응답을 보다보면 센터채널도 종종 이상할때가 있습니다.

기존 좌우페어매칭에 센터는 미포함이였기에 포함시켰습니다.


![image](https://github.com/user-attachments/assets/c68d0037-6e3d-423d-80a3-826aedcf391b)


또한 채널별 시작타이밍도 일단은 적용했습니다.


피크 정렬이랑 교차상관 둘다 경우에 따라 다른 결과를 보여줬는데, 대부분 피크 정렬이 좀더 나은 결과를 보여줬기에 피크정렬을 사용합니다.



-----------------------------------------------


### 11
![image](https://github.com/user-attachments/assets/67652815-f8d7-482c-83e9-3663a4724f1c)
이렇게 ITD가 틀어진 응답이 있다하면


![image](https://github.com/user-attachments/assets/deecfc0e-be84-4411-9306-1a28b736042c)
![image](https://github.com/user-attachments/assets/5cbbdb8f-a931-4c18-ab72-5ff69bc273f1)
--itd=e 옵션일때엔


early 이른쪽에 느린쪽을 땡겨오고


![image](https://github.com/user-attachments/assets/b8c36615-02d4-426b-81ef-1ec2983befe5)
![image](https://github.com/user-attachments/assets/7944a450-a972-4bc9-bd61-d8aa894cd9cb)


--itd=l 옵션일땐

late 느린쪽에 이른쪽을 땡겨오고


![image](https://github.com/user-attachments/assets/3c0ff3e6-e96b-4788-9e9b-079b58a052c8)
![image](https://github.com/user-attachments/assets/5fabca92-17d1-46c7-9541-eb1d0f1fd75f)


--itd=a 를 사용했을땐

avg 평균에 각각 밀고 땡겨오게 됩니다.


기본값은 비활성이고, --itd=a 와 같이 원하는 옵션을 적용할수있습니다.(a, e, l)


근데 이게 잘 생각해봐야 하는게


공통지연이 틀어져서 한쪽으로 쏠리면 당연히 쏠려서 들리는건 맞아서 그게 거슬리긴 하는데 (현실에선 실시간 뇌보정으로 커버가 되지만)


얘가 틀어졌든 아니든 얼굴,몸이 돌아가있는 기준으론 정확한? 응답이라서


건드는 순간부터 지각되는 스펙트럼이 개선 혹은 복구가 될수도 있지만 오히려 더 캔슬이 나듯 물먹은듯한 소리도 날수있다는점


고음은 저음에 비해 ITD에 "덜" 의존하긴하지만 테스트톤에 따라서 그 차이가 제법 나기도 해서


심한경우엔 거리감, 깊이감이 압축되기도 하기때문에


1~2샘플정도면 건드려도 괜찮고 (20~40us 차이정도)


그 이상의 차이면(예를들어 한쪽귀는250us, 반대채널은 333us) 녹음을 다시하는걸 권장합니다요.


그리고 또 한가지 저게 정확하지 않을수 있는게 반대귀 채널은 초고음 스펙트럼이 보통 무딘 상태라서


단순히 피크만 보고 정렬하기엔 혼란이 있을수도 있기때문에


먼저 듣고나서, 바꿔보고 또 들어보고 판단해보시는게 좋을듯 합니다.


제일 좋은건 처리에 의존하지않고, 녹음때 잘 녹음하는 것이 좋습니다.


-----------------------------------------------


### 11

가상 베이스 기능이 추가되었습니다.


![image](https://github.com/user-attachments/assets/bb77da45-97ce-4576-8a8a-396b3ffa16ea)


응답암거나 가져왔을때 이런 모습 (명령어 x)


![image](https://github.com/user-attachments/assets/80b0b6b5-ff47-4edb-a492-8f378448a268)


여기에 -vbass=200을 적용했을때


![image](https://github.com/user-attachments/assets/c70ec485-ef3a-413c-860d-72eb6b06a2a1)
![image](https://github.com/user-attachments/assets/5a764c41-2ef7-4264-8a3b-2c99787ef7e9)


이렇게 200Hz를 기준으로 크로스오버를 잡고 저음이 합성됩니다.


![image](https://github.com/user-attachments/assets/8366bf7d-9a1a-4180-90d9-b04e1e26816d)


물론 프론트말고 모든 채널들 다 적용됩니다. 각 반대귀 채널들은 각각의 ITD에 맞게 합성되며, 이는 각 스피커의 각도별로 ITD가 달라짐을 의미합니다.


오랜기간동안 모노bass라는 개념이 존재해왔지만, 제일 좋은건 각도별 스피커들 모두가 각각의 ITD를 가지고 풀레인지로 재생될때가 베스트입니다.


가상베이스(15hz 버터워스 4차 필터)에 ILD도 추가되어있고


크오는 링크위츠 8차를 사용하는데 최대 200~250hz정도까지, 그 이상은 권장하지않습니다.


그냥 서브우퍼 영역만 교체하는거면 -vbass=100으로 해도 되지만요.


smyth realizer의 구현이 썩 좋아보이진 않았지만 암튼 딸깍으로 저음합성이 되는 기능이 Impulcifer의 수동 크로스오버와의 차이였는데


이젠 저음도 합성이 가능합니다. virtual_bass.py를 다른 py들이 있는 폴더내에 다운받아놓고 --vbass= 만 원할때 입력하면 됩니다.


