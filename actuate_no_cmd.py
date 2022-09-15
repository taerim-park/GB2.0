#actuate_no_cmd.py
#cmd에 커맨드를 입력하는 방식이 아닌, 프로그램의 AE명을 수정해 mqtt 명령어를 보내는 프로그램입니다.

import requests
import json
import sys


host="218.232.234.232"  #건교부 테스트 사이트
#host="m.damoa.io"  #교수님 개인 서버
cse={'name':'cse-gnrb-mon'}

#void actuate(string aename, dictionary cmd)
#입력받은 aename에 해당하는 AE에 mqtt를 통해 명령을 전달합니다.
#전달되는 명령 josn은 변수 cmd에 담습니다. 딕셔너리 형식입니다.
def actuate(aename, cmd):
    print('Actuator')
    j=cmd
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F'{host}',
        "Content-Type":"application/vnd.onem2m-res+json; ty=4"
    }
    body={
        "m2m:cin":{
            "con": cmd
            }
    }
    url = F"http://{host}:7579/{cse['name']}/{aename}/ctrl"
    r = requests.post(url, data=json.dumps(body), headers=h)
    print(url, json.dumps(r.json()))

config_json = {
  "cmd":"autossh"
}

actuate("ae.T0083b-AC_S1M_01_X", config_json)

#actuate("ae.11001100-AC_S1M_01_X", config_json)

# 이하로는 실제 현장에 설치된 테스트 센서의 AE 리스트 #
####################################################

## 테스트 센서 1 : 태리IC(상)/(하) ##

#1 : 상행선 가속도
#actuate("ae.025175-AC_S1Q2_01_Z", config_json)

#2 : 상행선 가속도 변형률 온도
#actuate("ae.025175-AC_S1Q2_02_Z", config_json)
#actuate("ae.025175-DS_S1Q0_01_X", config_json)
#actuate("ae.025175-TP_S1Q2_01", config_json)

#3 : 상행선 경사 카메라 변위
#actuate("ae.025175-DI_S1Q0_01_X", config_json)
#actuate("ae.025175-CM_A1_01_X", config_json)
#actuate("ae.025175-TI_A1_01_XY", config_json)

#4 : 하행선 가속도
#actuate("ae.025176-AC_S1Q2_02_Z", config_json)

#5 : 하행선 가속도 변형률 온도
#actuate("ae.025176-TP_S1Q2_01", config_json)
#actuate("ae.025176-AC_S1Q2_01_Z", config_json)
#actuate("ae.025176-DS_S1Q2_01_X", config_json)

####################################################

## 테스트 센서 2 : 하평교(상/하행 구분 x) ##

#1
#actuate('ae.001685-TP_S2Q2_01', config_json)
#actuate('ae.001685-AC_S2Q2_01_Z', config_json)

#2
#actuate('ae.001685-DS_S1Q2_01_X', config_json)
#actuate('ae.001685-AC_S1Q2_01_Z', config_json)

#3
#actuate('ae.001685-TI_A1_01_XY', config_json)
#actuate('ae.001685-CM_A1_01', config_json)
#actuate('ae.001685-DI_S1Q0_01_X', config_json)

####################################################