# camera.py
# AE type CM에 필요한 사진 촬영을 위한 프로그램입니다.
# measureperiod에 따라 사진을 촬영하는 경우와 명령어 takepicture을 받아 사진을 촬영하는 경우는 각각 다른 함수를 사용합니다. (받는 인자 차이)

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
from conf import ae, root

import zipfile
from os.path import basename

def sensor_type(aename):
    return aename.split('-')[1][0:2]

# take_picture(_time, aename, t1_start, t1_msg)
# 즉시 사진을 촬영 후 저장, 이후 파일을 http raw file server로 전송합니다. 별도로 압축은 진행하지 않습니다.
def take_picture(_time, aename, t1_start, t1_msg):
    global ae
    file_time = _time.strftime('%Y%m%d%H%M')
    file_path = F"{root}/image/{file_time}_{aename}"
    if not os.path.exists(F"{root}/image"): os.makedirs(F"{root}/image") # 저장 디렉토리가 없다면 생성
    #os.system(F"fswebcam -r 1920*1080 --no-banner --title {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {file_path}.jpg") # 사진촬영 명령
    os.system(F"fswebcam -r 1920*1080 --font luxisr:48 --timestamp '%Y-%m-%d %H:%M:%S' {file_path}.jpg") # 사진촬영 명령
    ae[aename]['local']['last_picture']=f"{file_path}.jpg"

    def upload():
        host = ae[aename]['config']['connect']['uploadip']
        port = ae[aename]['config']['connect']['uploadport']
        url = F"http://{host}:{port}/upload"
        print(f'{aename} upload url= {url} {time}_{aename}')
        try:
            r = requests.post(url, data = {"keyValue1":12345}, files = {"attachment":open(f"{file_path}.jpg", "rb")})
            print(f'TIMER: {aename} result= {r.text}')
        except Exception as e:
            print(f'TIMER: fail-to-upload {aename} file={file_path}')
            print(f'error:  {e}')

    print(f'TIMER: upload +3s') # 조금 기다렸다가 사진 업로드
    Timer(3, upload).start()

    return t1_start, t1_msg

# take_picture_command(_time, aename)
# 즉시 사진을 촬영 후 저장, 이후 파일을 http raw file server로 전송합니다. take_picture과의 차이점은 인자로 t1_start, t1_msg를 받지 않는다는 점입니다.
def take_picture_command(_time, aename):
    global ae
    file_time = _time.strftime('%Y%m%d%H%M')
    file_path = F"{root}/image/{file_time}_{aename}"
    if not os.path.exists(F"{root}/image"): os.makedirs(F"{root}/image") # 저장 디렉토리가 없다면 생성
    #os.system(F"fswebcam -r 1920*1080 --no-banner --title {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {file_path}.jpg") # 사진촬영 명령
    os.system(F"fswebcam -r 1920*1080 --font luxisr:48 --timestamp '%Y-%m-%d %H:%M:%S' {file_path}.jpg") # 사진촬영 명령
    ae[aename]['local']['last_picture']=f"{file_path}.jpg"


    def upload():
        host = ae[aename]['config']['connect']['uploadip']
        port = ae[aename]['config']['connect']['uploadport']
        url = F"http://{host}:{port}/upload"
        print(f'{aename} upload url= {url} {time}_{aename}')
        try:
            r = requests.post(url, data = {"keyValue1":12345}, files = {"attachment":open(f"{file_path}.jpg", "rb")})
            print(f'TIMER: {aename} result= {r.text}')
        except Exception as e:
            print(f'TIMER: fail-to-upload {aename} file={file_path}')
            print(f'error:  {e}')

    print(f'TIMER: upload +1s') # 살짝 기다렸다가 사진 업로드
    Timer(1, upload).start()
