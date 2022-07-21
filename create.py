# start.py
# date : 2022-05-06
# 리소스 생성

from encodings import utf_8
import requests
import json
import sys
import os
from datetime import datetime
from conf import csename, ae, slack

def ci(aename, cnt, subcnt):
    global ae, csename
    c=ae[aename]['config']['connect']
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F"{c['cseip']}",
        "Content-Type":"application/vnd.onem2m-res+json;ty=4"
    }
    body={
        "m2m:cin":
        {
            "con": { }
        }
    }
    if cnt in {'config','info','data'}:
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{cnt}/{subcnt}"
        if len(ae[aename][cnt][subcnt]) == 0: # 내용물이 없다면 빈 cin을 생성하게 되므로, 함수를 더이상 실행하지 않도록 한다
            return
        body["m2m:cin"]["con"] = ae[aename][cnt][subcnt]
    else:
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{cnt}"
        if len(ae[aename][cnt]) == 0: # 내용물이 없다면 빈 cin을 생성하게 되므로, 함수를 더이상 실행하지 않도록 한다
            return
        body["m2m:cin"]["con"] = ae[aename][cnt]
    #print(f'{url} {json.dumps(body)[:50]}...')
    #print(f'{url}')
              
    gotok=False
    try:
        r = requests.post(url, data=json.dumps(body), headers=h)
        r.raise_for_status()
        if "m2m:dbg" in r.json():
            print(f'got error {r.json}')
        else:
            if subcnt == "": x=''
            else: x=f'/{subcnt}'
            if x=='/dmeasure':
                print(f'  created ci {aename}/{cnt}{x}/{r.json()["m2m:cin"]["rn"]} {json.dumps(r.json()["m2m:cin"]["con"], ensure_ascii=False)[:100]}...')
            else:
                print(f'  created ci {aename}/{cnt}{x}/{r.json()["m2m:cin"]["rn"]} {json.dumps(r.json()["m2m:cin"]["con"], ensure_ascii=False)}')
            slack(aename, f'created {url}/{r.json()["m2m:cin"]["rn"]}')
            gotok=True
    except requests.exceptions.RequestException as e:
        print(f'failed to ci {e}')


# (ae.323376-TP_A1_01_X, {'info','config'})
def allci(aei, all):
    #print(f'create ci for containers= {all}')
    for cnti in ae[aei]:
        for subcnti in ae[aei][cnti]:
            if cnti in all:
                #print(f'allci {aei}/{cnti}/{subcnti}')
                ci(aei, cnti, subcnti)

if __name__== "__main__":
    doit()
