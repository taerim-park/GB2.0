# 작성자 : ino-on, 주수아
# 정해진 주기마다 가속도 데이터의 통계를 내, 모비우스 규약에 기반한 컨텐트인스턴스를 생성합니다.
# FFT 연산을 사용하는 경우, FFT 연산 후 peak값에 해당하는 hrz를 반환하고, data->FFT 컨텐트인스턴스를 생성합니다.

import json
import os
import sys
import time
from datetime import datetime, timedelta
from time import process_time
import numpy as np
import requests
from threading import Timer, Thread

import create
from conf import ae, root, memory

def sensor_type(aename):
    return aename.split('-')[1][0:2]

# double FFT(cmeasure, data_list)
# 리스트의 가장 오래된 1024개의 데이터를 받아, FFT 연산을 시행합니다.
# cmeasure에 기록된 st1min, st1max를 기반으로 peak을 찾아내어, peak에 해당하는 헤르츠를 찾아냅니다.
def FFT(cmeasure, data_list):
    FFT_fail = -1

    if len(data_list)<1024: # 데이터가 1024개 미만인 경우, 연산을 시행하지 않음
        print("no enough data")
        print("FFT calculation has failed")
        return FFT_fail # 마이너스값 return

    data_FFT_list = list()
    
    FFT_list = data_list[:1024] # select oldest 1024 data
    data_FFT_list_np = np.fft.fft(FFT_list)
    
    for i in range(len(data_FFT_list_np)):
        data_FFT_list.append(round(np.absolute(data_FFT_list_np[i]).item(),2))
    data_FFT_list[0] = 0
    #print(data_FFT_list)

    FFT_const = int(cmeasure["samplerate"])/1024
    data_FFT_X = np.arange(FFT_const, FFT_const*1025, FFT_const)
    data_peak_range = list()
    for i in range(len(data_FFT_X)):
        if data_FFT_X[i] >= cmeasure["st1min"] and data_FFT_X[i] <= cmeasure["st1max"]:
            data_peak_range.append(i)
        if data_FFT_X[i] > cmeasure["st1max"]: # 데이터가 범위를 벗어나기 시작했다면, 더이상 반복문을 수행하지 않음
            break
    # peak를 측정할 범위 내에 속하는 데이터가 전혀 없는 경우, FFT는 실패
    # 예 : st1min이 100, st1max가 1000.. 이런 식일 경우
    if len(data_peak_range) == 0: 
        print("data range error : there is no data in peak range")
        print("FFT calculation has failed")
        return FFT_fail

    peak = 0
    
    for i in range(len(data_peak_range)):
        if peak < data_FFT_list[data_peak_range[i]]:
            peak = data_FFT_list[data_peak_range[i]]

    return data_FFT_X[data_FFT_list.index(peak)]

# raw_json 은 file로 저장준비가된 모든 센서들 통합 데이타
def savedJson(aename,raw_json, t1_start, t1_msg):
    global root, ae, memory
    print(f'create ci for {aename}')
    cmeasure = ae[aename]['config']['cmeasure']
    save_path = F"{root}/merged_data/{sensor_type(aename)}"
    j = raw_json[sensor_type(aename)]
    boardTime = datetime.strptime(j['time'],'%Y-%m-%d %H:%M:%S')
    if not os.path.exists(save_path): os.makedirs(save_path)

    mymemory=memory[aename]
    point1 = process_time()
    print('measure time begin: 0')
    
    data_list = list()
    recent_data = ""
    print(f'{aename} processing {len(mymemory["file"])} records(sec)')

    # boardTime 기준으로, 아직 지금 이순간 1초 데이타는 hold되고있지, Json 으로 저정되어있지 않다. 그래서 1부터.
    print(f'boardTime= {boardTime} ')
    for i in range(1, 601): # 10분간 기간
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        # 가장 최근 데이터를 뽑아낸다, i=0이 정시 boardData 를 처리하기전으로 수정
        if recent_data == "":
            try:
                recent_data = mymemory["file"][key]
                print(f' got recent_data with {key}')
            except:
                print(f' failed recent_data len(mymemory["file"][{key}]= len(mymemory["file"][{key}])')
        # 데이타가 600개가 되지 않을 경우도 있다. 그래서 계속 값지정. 마지막에 지정된 값이 시작시간이 된다.
        start_time = boardTime - timedelta(seconds=i)

        if not key in mymemory["file"]:
            print(f'{aename} no key= {key} i= {i}')
            break
        json_data = mymemory["file"][key]
        if isinstance(json_data['data'], list): data_list.extend(json_data["data"])
        else: data_list.append(json_data["data"])

    t1_msg += f' - doneCollectData - {process_time()-t1_start:.1f}s'

    if sensor_type(aename) == "AC" or sensor_type(aename) == "DS": # 동적 데이터의 경우
        print(f"{aename} len(data)= {len(data_list)} elapsed= {process_time()-point1:.1f}")
        
        #print(f'len(data_list)= {len(data_list)}')
        #print(data_list)
        data_list_np = np.array(data_list)
        dmeasure = {}
        dmeasure['type'] = "D"
        dmeasure['time'] = start_time.strftime("%Y-%m-%d %H:%M:%S")   # spec에 의하면 10분 측정구간의 시작시간을 지정
        dmeasure['min'] = np.min(data_list_np)
        dmeasure['max']= np.max(data_list_np)
        dmeasure['avg'] = np.average(data_list_np)
        dmeasure['std'] = np.std(data_list_np)
        dmeasure['rms'] = np.sqrt(np.mean(data_list_np**2))
        ae[aename]['data']['dmeasure'] = dmeasure
        #create.ci(aename, 'data', 'dmeasure')
        print(f'TIMER: create.ci +1s')
        Timer(1, create.ci,[aename, 'data', 'dmeasure']).start()
        
        if cmeasure["usefft"] in {"Y", "y"}:
            hrz = FFT(cmeasure, data_list_np)
            if hrz != -1 : #FFT 연산에 성공한 경우에만 hrz 기록
                fft = {}
                fft["start"]=start_time.strftime("%Y-%m-%d %H:%M:%S")
                fft["end"]=recent_data['time']
                fft["st1hz"]=hrz
                ae[aename]['data']['fft']=fft
                #create.ci(aename, 'data', 'fft')
                t0=Thread(target=create.ci, args=(aename, 'data', 'fft'))
                t0.start()

    else: # 정적 데이터의 경우, 하나의 데이터만을 전송. FFT 설정에는 아예 반응하지 않는다
        dmeasure = {}
        dmeasure['val'] = j["data"]
        dmeasure['time'] = j["time"]
        dmeasure['type'] = "S"
        ae[aename]['data']['dmeasure'] = dmeasure
        #create.ci(aename, 'data', 'dmeasure')
        t1=Thread(target=create.ci, args=(aename, 'data', 'dmeasure')).start()

    t1_msg += f' - doneSendCi - {process_time()-t1_start:.1f}s'

    merged_file = { # 최종적으로 rawperiod간의 데이터가 저장될 json의 dict
        "starttime":start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "endtime":recent_data['time'],
        "count":len(data_list),
        "data":data_list
    }

    file_name = f'{save_path}/{start_time.strftime("%Y%m%d%H%M")}_{aename}.bin'

    # saved file의 이름은 끝나는 시간임 --> 시작시간으로 변경
    def savefile(merged_file):
        with open (file_name, "w") as f: json.dump(merged_file, f, indent=4)
        print(f'TIMER: saved')
    #savefile(aename, boardTime, f'{save_path}/{file_name}.bin')
    print(f'TIMER: savefile +2s')
    Timer(2, savefile, [merged_file]).start()


    t1_msg += f' - doneSaveFile - {process_time()-t1_start:.1f}s'

    def upload():
        host = ae[aename]['config']['connect']['uploadip']
        port = ae[aename]['config']['connect']['uploadport']
        url = F"http://{host}:{port}/upload"
        print(f'{aename} upload url= {url} {file_name}')
        try:
            r = requests.post(url, data = {"keyValue1":12345}, files = {"attachment":open(file_name, "rb")})
            print(f'TIMER: {aename} result= {r.text}')
        except:
            print(f'TIMER: fail-to-upload {aename} file={file_name}')

    #upload(aename, f'{save_path}/{file_name}.bin')
    print(f'TIMER: upload +3s')
    Timer(3, upload).start()
    #print(f'{aename} uploaded a file elapsed= {process_time()-point1:.1f}s')

    # reserve some data for trigger follow-up
    for i in range(60, 1000): # 전 1분간의 데이타를 save해둔다. 
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        if key in mymemory["file"]: del mymemory["file"][key]
        else:
            print(f'done removing break at {i} {key}')
            break

    t1_msg += f' - doneUploadFile - {process_time()-t1_start:.1f}s'

    print("RETURN from savedJson()")
    return 'ok', t1_start, t1_msg
