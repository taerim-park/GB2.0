import requests
import json
import sys
import create
import time
import os
from threading import Timer, Thread

from conf import csename, ae
import create
import state

verify_only=False

def sensor_type(aename):
    return aename.split('-')[1][0:2]

def create_sub(aename):
    global csename, ae
    c=ae[aename]['config']['connect']
    h={
        "Accept": "application/json",
        "X-M2M-RI": "12345",
        "X-M2M-Origin": "S",
        "Host": F"{c['cseip']}",
        "Content-Type":"application/vnd.onem2m-res+json;ty=23"
    }
    body={
      "m2m:sub": {
        "rn": "sub",
        "enc": {
          "net": [3]
        },
        "nu": [F"mqtt://{c['cseip']}/{aename}?ct=json"],
        "exc": 10
      }
    }
    
    url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/ctrl?ct=json"
    if not verify_only:
        r = requests.post(url, data=json.dumps(body), headers=h)
        print('created m2m:sub', r.json()["m2m:sub"]["rn"])
        if "m2m:dbg" in r.json(): sys.exit(0)

def makeit(IF_mode):
    global ae, csename
    for aename in ae:
        if IF_mode and sensor_type(aename) != "IF": # IF를 포함한 ae dict의 경우, IF의 AE와 container 외의 리소스는 생성하지 않는다
            continue
        c=ae[aename]['config']['connect']
        print('Using ', f"{c['cseip']}:{c['cseport']}")
        print('Query CB:')
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}"
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}"
        try:
            r = requests.get(url, headers=h, timeout=10)
            print('found', 'm2m:cb', r.json()["m2m:cb"]["rn"])
        except:
            print('***** Got error querying CB. Assume that all resources are ok')
            return
        # once is enough for a board
        break
    
    print('Query AE: ')
    aeToMake = list()
    for aename in ae:
        if IF_mode and sensor_type(aename) != "IF": # IF를 포함한 ae dict의 경우, IF의 AE와 container 외의 리소스는 생성하지 않는다
            continue
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}"
        try:
            r = requests.get(url, headers=h, timeout=10)
            j=r.json()
            if "m2m:ae" in j:
                print('found', r.json()["m2m:ae"]["rn"])
            else:
                aeToMake.append(aename)
        except:
            print('***** Got error querying AE. Assume that all resources are ok')
            return
    if len(aeToMake) == 0:
        return
    
    for aename in aeToMake:
        if IF_mode and sensor_type(aename) != "IF": # IF를 포함한 ae dict의 경우, IF의 AE와 container 외의 리소스는 생성하지 않는다
            continue
        print(F'Found no AE -->{aename}  Create fresh one')
        c=ae[aename]['config']['connect']
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}",
            "Content-Type":"application/vnd.onem2m-res+json;ty=2"
        }
        body={
            "m2m:ae" : {
                "rn": "",
                "api": "0.0.1",
                "rr": True
                }
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}"
        body["m2m:ae"]["rn"]=aename
        body["m2m:ae"]["lbl"]=[aename]
        if not verify_only:
            r = requests.post(url, data=json.dumps(body), headers=h)
            print('created m2m:ae', r.json()["m2m:ae"]["rn"])
            if "m2m:dbg" in r.json(): sys.exit(0)
    
    
    print('\nCreate Container ')
    
    for aename in aeToMake:
        if IF_mode and sensor_type(aename) != "IF": # IF를 포함한 ae dict의 경우, IF의 AE와 container 외의 리소스는 생성하지 않는다
            continue
        c=ae[aename]['config']['connect']
        h={
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}",
            "Content-Type":"application/vnd.onem2m-res+json;ty=3"
        }
        body={
            "m2m:cnt": {
                "rn": "",
                "lbl": []
            }
        }
        url = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}"
        for ct in ae[aename]:
            if ct == 'local':
                continue
            body["m2m:cnt"]["rn"]=ct
            body["m2m:cnt"]["lbl"]=[ct]
            if not verify_only:
                r = requests.post(url, data=json.dumps(body), headers=h)
                print(f'created m2m:cnt {aename}/{r.json()["m2m:cnt"]["rn"]}')
                if "m2m:dbg" in r.json(): 
                    print(f'error in creating ct {ct}')
                    sys.exit(0)
            if ct in {'config','info','data'}:
                url2 = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}"
                for subct in ae[aename][ct]:
                    body["m2m:cnt"]["rn"]=subct
                    body["m2m:cnt"]["lbl"]=[subct]
                    if not verify_only:
                        r = requests.post(url2, data=json.dumps(body), headers=h)
                        print(f'created m2m:cnt {aename}/{ct}/{r.json()["m2m:cnt"]["rn"]}')
                        if "m2m:dbg" in r.json(): sys.exit(0)
                    
            if ct=='ctrl':
                create_sub(aename)

# void container_search()
# 현재 dict ae에 지정된 AE가 정말로 모든 컨테이너를 갖추고 있는지 검사합니다. 
def container_search(IF_mode):
    global csename, ae
    print("start container searching...")
    for aename in ae:
        if IF_mode and sensor_type(aename) != "IF": # IF를 포함한 ae dict의 경우, IF의 AE와 container 외의 리소스는 존재여부를 검사하지 않는다
            continue
        c=ae[aename]['config']['connect']
        h_search={ # con 존재유무 검사할 때 사용하는 헤더
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}"
        }
        h_make={ # con 생성할 때 사용하는 헤더
            "Accept": "application/json",
            "X-M2M-RI": "12345",
            "X-M2M-Origin": "S",
            "Host": F"{c['cseip']}",
            "Content-Type":"application/vnd.onem2m-res+json;ty=3"
        }
        body={ # container를 생성하게 된다면 사용할 body
            "m2m:cnt": {
                "rn": "",
                "lbl": []
            }
        }
        url_make = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}"
        for ct in ae[aename]:
            if ct == 'local': #cnt local은 말 그대로 local data를 저장하기 위한 dict이기 때문에, 생성하거나 검사하지 않는다
                continue
            body["m2m:cnt"]["rn"]=ct
            body["m2m:cnt"]["lbl"]=[ct]
            url_search = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}"

            try:
                r = requests.get(url_search, headers=h_search, timeout=20) # 해당 컨테이너가 존재하는지 검사
            except Exception as e:
                print(F"ERROR : {e}")
                return

            if "m2m:dbg" in r.json(): # cnt이 존재하지 않는 경우, 생성한다
                print(F"found no cnt : {ct} -> creating...")
                try:
                    r = requests.post(url_make, data=json.dumps(body), headers=h_make)
                except Exception as e:
                    print(F"ERROR : {e}")
                    return

                if "m2m:dbg" in r.json(): 
                    print(f'error in creating ct {ct}')
                    return
                print(f'created m2m:cnt {aename}/{r.json()["m2m:cnt"]["rn"]}')
                if ct in {'config','info','data'}: # 새로 만든 컨테이너가 config, info, data라면 하위 컨테이너를 만들어야 한다
                    url_make2 = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}"

                    for subct in ae[aename][ct]: 

                        body["m2m:cnt"]["rn"]=subct
                        body["m2m:cnt"]["lbl"]=[subct]

                        r = requests.post(url_make2, data=json.dumps(body), headers=h_make)

                        if "m2m:dbg" in r.json():
                            print(f'error in creating ct {subct}')
                            return
                        else:
                            print(f'created m2m:cnt {aename}/{ct}/{r.json()["m2m:cnt"]["rn"]}')
                            if ct in{'config', 'info'}: #초깃값이 업로드되지 않았을 것이기 때문에, 업로드해둔다.
                                t0=Thread(target=create.ci, args=(aename, ct, subct))
                                t0.start()
                elif ct == 'state':
                    #print("uploading initial state...")
                    Timer(1, state.report, [aename]).start()
                elif ct == 'ctrl':
                    #print("create new sub")
                    Timer(1, create_sub, [aename]).start()

            elif ct in {'config','info','data'}: # cnt config, info, data의 존재를 확인한 경우, 그 하위 컨테이너를 검사한다
                url_make2 = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}"
                for subct in ae[aename][ct]: # 서브 컨테이너가 있는 컨테이너가 생성되어있지 않은 경우, 모든 서브 컨테이너에 대해 생성을 시도.
                    url_search2 = F"http://{c['cseip']}:{c['cseport']}/{csename}/{aename}/{ct}/{subct}"
                    body["m2m:cnt"]["rn"]=subct
                    body["m2m:cnt"]["lbl"]=[subct]
                    try:
                        r = requests.get(url_search2, headers=h_search, timeout=20) # 해당 컨테이너가 존재하는지 검사
                    except Exception as e:
                        print(F"ERROR : {e}")
                        return
                    if "m2m:dbg" in r.json(): # cnt이 존재하지 않는 경우, 생성한다
                        print(F"found no subcnt : {subct} -> creating...")
                        r = requests.post(url_make2, data=json.dumps(body), headers=h_make)
                        if "m2m:dbg" in r.json(): pass
                        else:
                            print(f'created m2m:cnt {aename}/{ct}/{r.json()["m2m:cnt"]["rn"]}')
                            if ct in {'config', 'info'}: #초깃값이 업로드되지 않았을 것이기 때문에, 업로드해둔다.
                                t3=Thread(target=create.ci, args=(aename, ct, subct))
                                t3.start()
                        
            else:
                continue

    print("container searching is over")


if __name__ == "__main__":
    makeit()
