import os
import json
import requests

# 아래 설정값은 최소 1회만 읽어가고 외부명령어로 값 설정이 있을 경우, 그 뒤부터는 'config.dat' 에 저장시켜두고 그것을 사용한다.
# ctrl command 로 reset 을 실행하거나, config.dat 를 삭제하면 다시 아래값을 1회 읽어간다.

csename='cse-gnrb-mon'
#host="m.damoa.io"  #이노온 테스트 사이트
host="218.232.234.232"  #건교부 테스트 사이트
port=1883

uploadhost='m.damoa.io'
uploadport=2883
from default import make_ae, ae, TOPIC_list, supported_sensors

#bridge = 80061056 #placecode 설정을 위해 변수로 재설정
#bridge = 42345141 #placecode 설정을 위해 변수로 재설정
bridge = 32345141 #placecode 설정을 위해 변수로 재설정
#bridge = 80062056 #placecode 설정을 위해 변수로 재설정
#bridge = 11001100 # 개인 테스트용
bridge = 99998888

install= {"date":"2022-04-25","place":"금남2교(하)","placecode":F"{bridge}","location":"6.7m(P2~P3)","section":"최우측 거더","latitude":"37.657248","longitude":"127.359962","aetype":"D"}
#connect={"cseip":host,"cseport":7579,"csename":csename,"cseid":csename,"mqttip":host,"mqttport":port,"uploadip":uploadhost,"uploadport":uploadport}
connect={"cseip":host,"cseport":7579,"csename":csename,"cseid":csename,"mqttip":host,"mqttport":port,"uploadip":uploadhost,"uploadport":uploadport}

# AC X,Y,Z can't coexist in current conf
make_ae(F'ae.{bridge}-AC_S1M_01_X', csename, install, connect)
#make_ae(F'ae.{bridge}-AC_S1M_02_X', csename, install, connect)
#make_ae(F'ae.{bridge}-AC_S1M_03_X', csename, install, connect)
make_ae(F'ae.{bridge}-DI_S1M_01_X', csename, install, connect)
make_ae(F'ae.{bridge}-TP_S1M_01_X', csename, install, connect)
make_ae(F'ae.{bridge}-TI_S1M_01_X', csename, install, connect)

root='/home/pi/GB'
for aename in ae:
    if os.path.exists(F"{root}/{aename}.conf"): 
        print(f'read {aename} from {aename}.conf')
        with open(F"{root}/{aename}.conf") as f:
            try:
                ae1 = json.load(f)
                ae[aename]=ae1
            except ValueError as e:
                print(e)
                print(f'wrong {aename}.conf')
    else:
        print(f'read {aename} from conf.py')

memory={}
boardTime=""

def slack(aename, msg):
    global ae

    if os.path.exists('slackkey.txt'):
        if not 'slack' in ae[aename]["local"]:
            with open("slackkey.txt") as f: ae[aename]['local']['slack']=f.read()
            print(f'activate slack alarm {ae[aename]["local"]["slack"]}')

    if 'slack' in ae[aename]["local"]:
        url2=f'http://damoa.io:8999/?msg={msg}&channel={ae[aename]["local"]["slack"]}'
        try:
            #print(f'for {aename} {msg}')
            r = requests.get(url2)
        except requests.exceptions.RequestException as e:
            print(f'failed to slack {e}')


if __name__ == "__main__":
    print(ae)
