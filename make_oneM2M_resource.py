import requests
import json
import sys
import create
import time
import os

from conf import csename, ae
verify_only=False

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

def makeit():
    global ae, csename

    for aename in ae:
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


if __name__ == "__main__":
    makeit()
