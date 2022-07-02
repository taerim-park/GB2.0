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

import zipfile
from os.path import basename

import create
from conf import ae, root, memory

import zipfile
from os.path import basename

def sensor_type(aename):
    return aename.split('-')[1][0:2]

def remove_old_data(aename, boardTime):
    global memory
    # reserve some data for trigger follow-up
    
    mymemory=memory[aename]
    r1=""
    r2=""
    c1=0
    c2=0
    for i in range(60, 1000): # 전 1분간의 데이타를 save해둔다. 
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        if key in mymemory["file"]: 
            del mymemory["file"][key]
            if r1=="": 
                r1=key
                c1=i
        else:
            r2= (boardTime - timedelta(seconds=i-1)).strftime("%Y-%m-%d-%H%M%S")
            c2=i-1
            break
    print(f"at 10m interval remove-old-data from= {r2} to= {r1} count={c2-c1+1}")

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
    once=False
    start_time=''
    for i in range(600, 0,-1): #600에서 시작해서 1까지
        key = (boardTime - timedelta(seconds=i)).strftime("%Y-%m-%d-%H%M%S")
        # 가장 최근 데이터를 뽑아낸다, i=0이 정시 boardData 를 처리하기전으로 수정

        if not key in mymemory["file"]:
            once=True
            continue

        if once: # partial data 의 경우 첫부분  key가 없을 수 있으며 이때만 시작점을 프린트
            once=False
            print(f' partial data. beginning valid key= {key}')
            
        if start_time=='': start_time = boardTime - timedelta(seconds=i) # 가장 첫번째 valid data의 시간

        json_data = mymemory["file"][key]
        if isinstance(json_data['data'], list): data_list.extend(json_data["data"])
        else: data_list.append(json_data["data"])

    if start_time=='':
        print(f" failed. no data. sart_time==null")
        return 'ok', t1_start, t1_msg

    if 'json_data' not in locals():
        print(f"no json_data in locals() ")
        return 'ok', t1_start, t1_msg

    recent_data = json_data  # 마지막 데이타가 가장 최신

    t1_msg += f' - doneCollectData - {process_time()-t1_start:.1f}s'

    print(f"{aename} len(data)= {len(data_list)} elapsed= {process_time()-point1:.1f}")
    
    # 정적, 동적 센서 관계없이 모두 동적처럼 데이터 연산 및 저장
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
        
        # 파일 압축 실행
        zip_file_name = F"{file_name[:len(file_name)-4]}.zip"
        zip_file = zipfile.ZipFile(zip_file_name, "w")
        zip_file.write(file_name, basename(file_name), compress_type=zipfile.ZIP_DEFLATED)
        zip_file.close()
        print(f"file compression has completed > {zip_file_name}")

        try:
            r = requests.post(url, data = {"keyValue1":12345}, files = {"attachment":open(zip_file_name, "rb")})
            print(f'TIMER: {aename} result= {r.text}')
        except Exception as e:
            print(f'TIMER: fail-to-upload {aename} file={zip_file_name}')
            print(f'error:  {e}')
    
    #upload(aename, f'{save_path}/{file_name}.bin')
    print(f'TIMER: upload +3s')
    Timer(3, upload).start()
    #print(f'{aename} uploaded a file elapsed= {process_time()-point1:.1f}s')

    remove_old_data(aename, boardTime)

    t1_msg += f' - doneUploadFile - {process_time()-t1_start:.1f}s'

    print("RETURN from savedJson()")
    return 'ok', t1_start, t1_msg
