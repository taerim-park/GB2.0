# Client_Data_Saving.py
# 소켓 서버로 'CAPTURE' 명령어를 1초에 1번 보내, 센서 데이터값을 받습니다.
# 받은 데이터를 센서 별로 분리해 각각 다른 디렉토리에 저장합니다.
# 현재 mqtt 전송도 이 프로그램에서 담당하고 있습니다.
VERSION='2-2_20220522_2330'
print('\n===========')
print(f'Verion {VERSION}')

from encodings import utf_8
import threading
from threading import Timer
import random
import requests
import json
from socket import *
import select
import os
import sys
import time
import re
import signal
from datetime import datetime, timedelta
from time import process_time
from paho.mqtt import client as mqtt
from events import Events
from RepeatedTimer import RepeatedTimer

import versionup
import create  #for Mobius resource
import conf

import Send_data
import Send_state

import make_oneM2M_resource

broker = conf.host
port = conf.port
csename = conf.csename
ae = conf.ae
supported_sensors = conf.supported_sensors

root=conf.root
do_trigger=""
do_trigger_param={}
do_status=""
do_status_param=""

TOPIC_callback=f'/oneM2M/req/{csename}/#'
TOPIC_response=f'/oneM2M/resp/{csename}'
TOPIC_list = conf.TOPIC_list
mqttc=""
command=""

# key==aename
trigger_activated={}

# single value for all ae
btime=''
btime_old=''

# 다중 데이터의 경우, 어떤 data를 저장할지 결정해야한다
acc_axis = "x" # x, y, z중 택1
deg_axis = "x" # x, y, z중 택1
str_axis = "z" # x, y, z중 택1
dis_channel = "ch4" # ch4, ch5중 택1

def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)

def sensor_type(aename):
    return aename.split('-')[1][0:2]

#센서별 데이타 저장소, 디렉토리가 없으면 자동생성
if not os.path.exists(F"{root}/raw_data"): os.makedirs(F"{root}/raw_data")

for stype in supported_sensors: # {'AC', 'DI', 'TP', 'TI', 'DS'}
    raw_path = F"{root}/raw_data/{stype}"
    if not os.path.exists(raw_path): 
        print(f'created directory {raw_path}')
        os.makedirs(raw_path)

client_socket=""

def connect():
    global client_socket
    if client_socket=="":
        client_socket= socket(AF_INET, SOCK_STREAM)
        client_socket.settimeout(5)
        try:
            client_socket.connect(('127.0.0.1', 50000))
        except:
            print('got no connection')
            return 'no'
        print("socket pi연결에 성공했습니다.")
    return "yes"

if connect()=='no':
    os._exit(0)

make_oneM2M_resource.makeit()
print('done any necessary Mobius resource creation')

# dict jsonCreate(dataTyep, timeData, realData)
# 받은 인자를 통해 딕셔너리를 생성합니다.
def jsonCreate(dataType, timeData, realData):
    data = {
        "type":dataType,
        "time":timeData,
        "data":realData
        }
    return data


# void jsonSave(path, jsonFile)
# 받은 dict를 json으로 변환한 후, 지정된 path에 저장합니다.
# 파일명은 기본적으로 날짜

old_time=""
def jsonSave(path, jsonFile):
    global old_time
    now = datetime.strptime(jsonFile['time'],'%Y-%m-%d %H:%M:%S.%f')
    now_file = f"{path}/{now.strftime('%Y-%m-%d-%H%M%S')}"
    with open(now_file, 'w') as f:
        json.dump(jsonFile, f, indent=4)
    now_time = datetime.strptime(datetime.strftime(now, '%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
    if old_time != "":
        if (now_time - old_time).total_seconds()>1.9:
            print(f'fyi, missing second slot {old_time} {now_time}')
    old_time=now_time
    

def save_conf():
    with open(F"{root}/config.dat","w") as f:
        f.write(json.dumps(ae, ensure_ascii=False,indent=4))
    print(f"wrote config.dat")

def do_user_command(aename, jcmd):
    global ae, do_trigger, do_trigger_param, do_status, do_status_param
    cmd=jcmd['cmd']
    if 'reset' in cmd:
        file=f"{root}/config.dat"
        if os.path.exists(file): 
            os.remove(file)
            print(f'removed {file}')
        else:
            print(f'no {file} to delete')
        os.system("sudo reboot")
    elif 'reboot' in cmd:
        os.system("sudo reboot")
    elif cmd in {'synctime'}:
        print('nothing to sync time')
    elif cmd in {'fwupdate'}:
        url= f'{jcmd["protocol"]}://{jcmd["ip"]}:{jcmd["port"]}{jcmd["path"]}'
        versionup.versionup(url)
    elif cmd in {'realstart'}:
        print('start mqtt real tx')
        ae[aename]['local']['realstart']='Y'
    elif cmd in {'realstop'}:
        print('stop mqtt real tx')
        ae[aename]['local']['realstart']='N'
    elif cmd in {'reqstate'}:
        do_status="goandshoot"
        do_status_param=aename
    elif cmd in {'settrigger'}:
        print(f'set ctrigger= {jcmd["ctrigger"]}')
        for x in jcmd["ctrigger"]:
            ae[aename]["config"]["ctrigger"][x]= jcmd["ctrigger"][x]

        #do_config(aename)
        do_trigger = do_config
        do_trigger_param={"aename":aename, "save":'save', "cmd":cmd}
    elif cmd in {'setmeasure'}:
        print(f'set cmeasure= {jcmd["cmeasure"]}')
        for x in jcmd["cmeasure"]:
            ae[aename]["config"]["cmeasure"][x]= jcmd["cmeasure"][x]
        save_conf()
        if "measureperiod" in jcmd["cmeasure"]: os.system('pm2 restart Send_data')
        if "stateperiod" in jcmd["cmeasure"]: os.system('pm2 restart Send_state')
        if "rawperiod" in jcmd["cmeasure"]: os.system('pm2 restart Send_file')
    elif cmd in {'settime'}:
        print(f'set time= {jcmd["time"]}')
        ae[aename]["config"]["time"]= jcmd["time"]
        save_conf()
    elif cmd in {'setconnect'}:
        print(f'set {aename}/connect= {jcmd["connect"]}')
        for x in jcmd["connect"]:
            ae[aename]["connect"][x]=jcmd["connect"][x]
        create.ci(aename, 'config', 'connect')
        save_conf()
    elif cmd in {'measurestart'}:
        ae[aename]['local']['measurestart']='Y'
        print(f"set measurestart= {ae[aename]['local']['measurestart']}")
        save_conf()
        os.system('pm2 restart Send_data')
    elif cmd in {'measurestop'}:
        ae[aename]['local']['measurestart']='N'
        print(f"set measurestart= {ae[aename]['local']['measurestart']}")
        save_conf()
        os.system('pm2 restart Send_data')
    elif cmd == 'inoon':
        cmd2=jcmd['cmd2']
        if cmd2=='data': Send_data.do_periodic_data(aename)
        elif cmd2=='file': Send_file.do_periodic_file(aename)
        elif cmd2=='state': Send_state.do_periodic_state(aename)
        else:
            print(f'invalid cmd  {jcmd}')
    else:
        print(f'invalid cmd {jcmd}')
        

def got_callback(topic, msg):
    global mqttc
    aename=topic[4] 
    if aename in ae:
        #print(topic, aename,  msg)
        try:
            j=json.loads(msg)
        except:
            print(f"json error {msg}")
            return
        jcmd=j["pc"]["m2m:sgn"]["nev"]["rep"]["m2m:cin"]["con"]
        print(f" ==> {aename} {jcmd}")
        do_user_command(aename, jcmd)

        resp_topic=f'{TOPIC_response}/{aename}/json'
        r = {}
        r['m2m:rsp'] = {}
        r['m2m:rsp']["rsc"] = 2001
        r['m2m:rsp']["to"] = ''
        r['m2m:rsp']["fr"] = aename
        r['m2m:rsp']["rqi"] = j["rqi"]
        r['m2m:rsp']["pc"] = ''
        mqttc.publish(resp_topic, json.dumps(r, ensure_ascii=False))
        print(f'response {resp_topic} {j["rqi"]}')

    else:
        #print(' ==> not for me', topic, msg[:20],'...')
        pass





def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to {broker} via MQTT")
            client.subscribe(TOPIC_callback)
            print(f"subscribed to {TOPIC_callback}")
        else:
            print("Failed to connect, return code %d\n", rc)

    def on_disconnect(client, userdata, rc):
        print("Disconnected from MQTT server!")

    def on_message(client, _topic, _msg):
        topic=_msg.topic.split('/')
        msg=_msg.payload.decode('utf8')
        got_callback(topic, msg)


    client_id = f'python-mqtt-{random.randint(0, 1000)}'
    mqttc = mqtt.Client(client_id)
    mqttc.on_connect = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_message = on_message
    mqttc.connect(broker, port)
    return mqttc

mqttc = connect_mqtt()
mqttc.loop_start()
print("mqtt 연결에 성공했습니다.")

        
# void mqtt_sending(aename, data)
# mqtt 전송을 수행합니다. 단, mqtt 전송을 사용하지 않기로 한 센서라면, 수행하지 않습니다.
# 센서에 따라 다른 TOPIC에 mqtt 메시지를 publish합니다.
def mqtt_sending(aename, data):   
    if mqttc=="":
        connect_mqtt()

    now = datetime.now()
    test_list = list()
    if type(data) == type(test_list):
        count = len(data)
    else:
        count = 1
    BODY = {
        "start":now.strftime("%Y-%m-%d %H:%M:%S.%f"),
        "samplerate":ae[aename]["config"]["cmeasure"]['samplerate'],
        "count":count,
        "data":data
        }
    mqttc.publish(F'/{csename}/{aename}/realtime', json.dumps(BODY, ensure_ascii=False))
    


time_old=datetime.now()

def do_config(param):
    global client_socket
    global ae

    aename=param["aename"]
    cmd=param["cmd"]
    save=param["save"]

    setting={ 'AC':{'select':0x0100,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'DI':{'select':0x0800,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TI':{'select':0x0200,'use':'N','st1high':0,'st1low':0, 'offset':0},
                'TP':{'select':0x1000,'use':'N','st1high':0,'st1low':0, 'offset':0}}
    for aename in ae:
        cmeasure = ae[aename]['config']['cmeasure']
        if 'offset' in cmeasure:
            setting[sensor_type(aename)]['offset'] = cmeasure['offset']
        ctrigger = ae[aename]['config']['ctrigger']
        if 'use' in ctrigger:
            setting[sensor_type(aename)]['use'] = ctrigger['use']
            if 'st1high' in ctrigger: setting[sensor_type(aename)]['st1high']= int(ctrigger['st1high'])
            if 'st1low' in ctrigger: setting[sensor_type(aename)]['st1low']= int(ctrigger['st1low'])

    print(f"do_config seting= {setting}")

    if connect() == 'no': 
        return
    try:
        client_socket.sendall(("CONFIG"+json.dumps(setting, ensure_ascii=False)).encode())
        rData = client_socket.recv(10000)
    except OSError as msg:
        print(f"socket error {msg} exiting..")
        os._exit(0)


    rData = rData.decode('utf_8')
    jsonData = json.loads(rData) # jsonData : 서버로부터 받은 json file을 dict 형식으로 변환한 것

    if jsonData["Status"] == "False":
        ae[aename]["state"]["abflag"]="Y"
        ae[aename]["state"]["abtime"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ae[aename]["state"]["abdesc"]="board config failed"
        create.ci(aename, 'state','')
        return


    if save=='save':
        print(f'do_config: got result {jsonData}')
        if cmd in {'ctrigger', 'cmeasure'}:
            create.ci(aename, 'config', cmd)
        elif cmd == 'settime':
            create.ci(aename, 'config', 'time')
        save_conf()

def do_trigger_followup(aename):
    global ae,root,path

    #print(f'trigger_followup {aename}')
    dtrigger=ae[aename]['data']['dtrigger']
    ctrigger = ae[aename]['config']['ctrigger']
    stype = sensor_type(aename)
    trigger= datetime.strptime(dtrigger['time'],'%Y-%m-%d %H:%M:%S.%f')
    raw_path = F"{root}/raw_data/{stype}"

    data_path_list = list()
    j=0
    for i in range(0,ctrigger['bfsec']+10):
        fname = datetime.strftime(trigger - timedelta(seconds=i), "%Y-%m-%d-%H%M%S")
        if os.path.exists(f'{raw_path}/{fname}'):
            #print(f'file ok -{i} {raw_path}/{fname}')
            data_path_list.append(f'{raw_path}/{fname}')
            j +=1
            start = datetime.strftime(trigger - timedelta(seconds=i), "%Y-%m-%d %H:%M:%S.%f")
            if j>= ctrigger['bfsec']:
                #print(f"done i= {i} bfsec= {ctrigger['bfsec']}")
                start = datetime.strftime(trigger - timedelta(seconds=i), "%Y-%m-%d %H:%M:%S.%f")
                break;
        else:
            print(f'skip missing file -{i} {raw_path}/{fname}')
    j=0
    for i in range(1, ctrigger['afsec']+10):
        fname = datetime.strftime(trigger + timedelta(seconds=i), "%Y-%m-%d-%H%M%S")
        if os.path.exists(f'{raw_path}/{fname}'):
            #print(f'file ok +{i} {fname}')
            data_path_list.append(f'{raw_path}/{fname}')
            j+=1
        else:
            print(f'skip missing file +{i} {raw_path}/{fname}')
        if j>= ctrigger['afsec']:
            #print(f"done afsec= {ctrigger['afsec']}")
            break;
    #print(f'found {len(data_path_list)} files')
    data_path_list.sort()

    # path에 존재하는 모든 data를 열어보고, 보낼 데이터 list를 작성한다.
    # 정렬된 data_path_list가 들어오기 때문에, 가장 처음 들어오는 데이터가 가장 오래된 데이터. 즉, start data이다.
    data = list()
    for file in range(len(data_path_list)):
        with open(data_path_list[file], "rb") as f:
            one_file = json.load(f)
            if isinstance(one_file['data'], list): data.extend(one_file["data"])
            else: data.append(one_file["data"])

    dtrigger['count']=len(data)
    dtrigger['data']=data
    dtrigger["start"] = start
    create.ci(aename, 'data', 'dtrigger')
    print(f"comiled trigger data: {len(data)} bytes for bfsec+afsec= {ctrigger['bfsec']+ctrigger['afsec']}")

session_active = False
def watchdog():
    global session_active
    if not session_active:
        print('found server capture session freeze, exiting..')
        os._exit(0)
    session_active = False
RepeatedTimer(60, watchdog)


def do_capture(target):
    global client_socket, mqtt_measure, time_old
    global trigger_activated, session_active
    global ae #samplerate 조정을 위한 값. 동적 데이터에만 적용되는 것으로 한다
    global btime, btime_old

    t1_start=process_time()
    #print('do capture')
    if connect() == 'no':
        return
    try:
        client_socket.sendall(target.encode()) # deice server로 'CAPTURE' 명령어를 송신합니다.
        rData = client_socket.recv(10000)
    except OSError as msg:
        print(f"socket error {msg} exiting..")
        os._exit(0)

    t2_start=process_time()
    rData = rData.decode('utf_8')
    try:
        j = json.loads(rData) # j : 서버로부터 받은 json file을 dict 형식으로 변환한 것
    except ValueError:
        print("invalid data from socket skip.")
        return

    now=datetime.now()
    # 모든 Server 메시지에는 'Status'가 있다
    if 'Status' not in j:
        print(f'found no Status {j} at {now.strftime("%H:%M:%S")}')
        return

    session_active=True
    if j['Status']=='False':
        #print(f"{j} at {now.strftime('%H:%M:%S')} +{(now-time_old).total_seconds():.1f}s fetching speed won sensor board speed")
        time_old=now
        return

    if 'Timestamp' not in j:
        print(f'found no Timestamp {j} at {now.strftime("%H:%M:%S")}')
        return

    if target == 'STATUS':
        with open('state.json', 'w') as f:
            json.dump(j, f)
        print(f'saved status= {j}')
        return


    #else target == 'CAPTURE'    
    #print('got=',j)
    btime = datetime.strptime(j['Timestamp'],'%Y-%m-%d %H:%M:%S.%f')
    with open('board_time.json','w') as f: f.write(j['Timestamp']) 
    if btime_old != "":
        print(f'Got new data {btime.strftime("%H:%M:%S.%f")} +{(btime - btime_old).total_seconds()}', end='')
    btime_old = btime
    #print(f"trigger= {j['trigger']}")

    for aename in ae:
        ctrigger=ae[aename]['config']['ctrigger']
        cmeasure=ae[aename]['config']['cmeasure']
        dtrigger=ae[aename]['data']['dtrigger']
        #print(f"aename= {aename} stype= {sensor_type(aename)} use= {ctrigger['use']}")

        # aename에 트리거 이미 진행중
        if aename in trigger_activated: # waiting for afsec
            print(f'  trigger[{aename}]= {trigger_activated[aename]}')
            if trigger_activated[aename]==0:
                #print(f'follow_up trigger')
                do_trigger_followup(aename)
                del trigger_activated[aename]
                continue
            else:
                trigger_activated[aename] -= 1
        else:
            print()

        if j['trigger'][sensor_type(aename)]=='0':
            continue
        elif ctrigger['use'] not in {'Y','y'}:
            #print(f"{aename} use trigger= {ctrigger['use']}")
            continue

        # new trigger
        if sensor_type(aename) == "AC": # 동적 데이터의 경우, 트리거 전초와 후초를 고려해 전송 시행
            trigger_list = j["AC"]
            trigger_data = "unknown"
            for ac in trigger_list: # 트리거 조건을 충족시키는 가장 첫번째 값을 val에 저장하기 위해 일치하는 값을 찾으면 break
                if ctrigger['mode'] == 1 and ac[acc_axis] > ctrigger['st1high']:
                    trigger_data = ac[acc_axis]
                    break
                elif ctrigger['mode'] == 2 and ac[acc_axis] < ctrigger['st1low']:
                    trigger_data = ac[acc_axis]
                    break
                elif ctrigger['mode'] == 3:
                    if ac[acc_axis] > ctrigger['st1high'] and ac[acc_axis] < ctrigger['st1low']:
                        trigger_data = ac[acc_axis]
                        break
                elif ctrigger['mode'] == 4:
                    if ac[acc_axis] < ctrigger['st1high'] and ac[acc_axis] > ctrigger['st1low']:
                        trigger_data = ac[acc_axis]
                        break

            if trigger_data == "unknown":
                print(f" -> trigger not for me")
                continue
                
            dtrigger['val'] = trigger_data
            print(f"  got AC trigger {aename} bfsec= {ctrigger['bfsec']}  afsec= {ctrigger['afsec']}")
            if isinstance(ctrigger['afsec'],int) and ctrigger['afsec']>0:
                trigger_activated[aename]=ctrigger['afsec']
            else:
                print(f"invalid afsec= {ctrigger['afsec']}")
        else:
            # 정적 데이터의 경우, 트리거 발생 당시의 데이터를 전송한다
            print(f"got non-AC trigger {aename}  bfsec= {ctrigger['bfsec']}  afsec= {ctrigger['afsec']}")
            dtrigger['start']=j["Timestamp"]
            dtrigger['count'] = 1
            
            if sensor_type(aename) == "DI": data = j["DI"][dis_channel]+cmeasure['offset']
            elif sensor_type(aename) == "TP": data = j["TP"]+cmeasure['offset']
            elif sensor_type(aename) == "TI": data = j["TI"][deg_axis]+cmeasure['offset'] # offset이 있는 경우, 합쳐주어야한다
            else: data = "nope"

            #정말로 val값이 trigger를 만족시키는지 check해야함. 추후 추가.
            dtrigger['val'] = data

        dtrigger['time']=j["Timestamp"] # 트리거 신호가 발생한 당시의 시각
        dtrigger['mode']=ctrigger['mode']
        dtrigger['sthigh']=ctrigger['st1high']
        dtrigger['stlow']=ctrigger['st1low']
        dtrigger['step']=1
        dtrigger['samplerate']=cmeasure['samplerate']

        # AC need afsec
        if sensor_type(aename) != "AC":
            create.ci(aename, "data", "dtrigger") # 정적 트리거 전송은 따로 do_trigger_followup을 실행하지 않는다.
            print("sent trigger for {aename}")

        

    # end of trigger            

    offset_dict = {
        "AC":0,
        "DI":0,
        "TP":0,
        "TI":0
    }

    for aename in ae:
        cmeasure=ae[aename]['config']['cmeasure']
        type = sensor_type(aename)

        if type == 'TP' and 'offset' in cmeasure:
            offset_dict["TP"] = cmeasure['offset']
        elif type == 'DI' and 'offset' in cmeasure:
            offset_dict["DI"] = cmeasure['offset']
        elif type == "AC" and 'offset' in cmeasure:
            offset_dict["AC"] = cmeasure['offset']
        elif type == "TI" and 'offset' in cmeasure:
            offset_dict["TI"] = cmeasure['offset']

    Time_data = j["Timestamp"]
    Temperature_data = j["TP"] + offset_dict["TP"]
    Displacement_data = j["DI"][dis_channel] + offset_dict["DI"]
    
    acc_list = list()
    str_list = list()
    
    for i in range(len(j["AC"])):
        acc_list.append(j["AC"][i][acc_axis] + offset_dict["AC"])
    for i in range(len(j["DS"])):
        str_list.append(j["DS"][i][str_axis]) #offset 기능 구현되어있지 않음
        
    #print(F"acc : {acc_list}")
    #samplerate에 따라 파일에 저장되는 data 조정
    #현재 가속도 센서에만 적용중
    for aename in ae:
        # acceleration의 경우, samplerate가 100이 아닌 경우에 대처한다
        if sensor_type(aename)=="AC":
            ae_samplerate = float(ae[aename]["config"]["cmeasure"]["samplerate"])
            if ae_samplerate != 100:
                if 100%ae_samplerate != 0:
                    #100의 약수가 아닌 samplerate가 설정되어있는 경우, 오류가 발생한다
                    print("wrong samplerate config")
                    print("apply standard samplerate = 100")
                    ae_samplerate = 100
                new_acc_list = list()
                merged_value = 0
                merge_count = 0
                sample_number = 100//ae_samplerate
                for i in range(len(acc_list)):
                    merged_value += acc_list[i]
                    merge_count += 1
                    if merge_count == sample_number:
                        new_acc_list.append(round(merged_value/sample_number, 2))
                        merge_count = 0
                        merged_value = 0
                acc_list = new_acc_list
            #print("samplerate calculation end")
            #print(acc_list)
    Acceleration_data = acc_list
    Strain_data = str_list
    Degree_data = j["TI"][deg_axis]+ offset_dict["TI"]
    
    # 센서의 특성을 고려해 각 센서 별로 센서 data를 담은 dict 생성
    raw_json={}
    raw_json['TI'] = jsonCreate('TI', Time_data, Degree_data)
    raw_json['TP'] = jsonCreate('TP', Time_data, Temperature_data)
    raw_json['DI'] = jsonCreate('DI', Time_data, Displacement_data)
    raw_json['AC'] = jsonCreate('AC', Time_data, Acceleration_data)
    raw_json['DS'] = jsonCreate('DS', Time_data, Strain_data)
    
    
    # mqtt 전송을 시행하기로 했다면 mqtt 전송 시행
    # 내 device의 ae에 지정된 sensor type 정보만을 전송
    for aename in ae:
        # stype 은 'AC' 와 같은 부분
        stype = sensor_type(aename)
        #print(f"mqtt {aename} {stype} {ae[aename]['local']['realstart']}")
        if ae[aename]['local']['realstart']=='Y':  # mqtt_realtime is controlled from remote user
            payload = raw_json[stype]["data"]
            mqtt_sending(aename, payload)
            #print(F'real mqtt /{csename}/{aename}/realtime')
        else:
            #print('reslstart==N, skip real time mqtt sending')
            pass

    # 센서별 json file 생성
    # 내 ae에 지정된 sensor type정보만을 저장
    for aename in ae:
        stype = sensor_type(aename)
        jsonSave(F"{root}/raw_data/{stype}", raw_json[stype])
        #if stype == 'AC': print(f"saved {stype} {len(raw_json[stype]['data'])} data")

    #print(f'CAPTURE {now.strftime("%H:%M:%S:%f")} capture,process={(t2_start-t1_start)*1000:.1f}+{(process_time()-t2_start)*1000:.1f}ms got {len(rData)}B {rData[:50]} ...')

def do_tick():
    global do_trigger, do_trigger_param, do_status, do_status_param
    do_capture('CAPTURE')
    if not do_trigger=="":
        print('do_trigger')
        do_trigger(do_trigger_param)
        do_trigger=""
    if not do_status=="":
        do_capture('STATUS')
        if do_status=='go': 
            do_status=""
            return

        print(f"reqstate create state ci for {do_status_param}")
        if do_status_param == "":
            print('PANIC... do_status_param==null')
        else:
            periodic_state.update(do_status_param)
        do_status = ''
        do_status_param=''

def do_periodic_status():
    global do_status, do_status_param
    do_status = 'go' 
    do_status_param=""


def startup():
    global ae
    print('create ci at boot')
    for aename in ae:
        ae[aename]['info']['manufacture']['fwver']=VERSION
        create.allci(aename, {'config','info'})
        do_config({'aename':aename, 'cmd':'','save':'nosave'})
        RepeatedTimer(ae[aename]['config']['cmeasure']['stateperiod']*60, do_periodic_status)


print('Ready')
Timer(10, startup).start()
RepeatedTimer(0.9, do_tick)