import requests
import json
import sys


host="218.232.234.232"  #건교부 테스트 사이트
#host="m.damoa.io"  #건교부 테스트 사이트
cse={'name':'cse-gnrb-mon'}

def actuate(aename, cmd):
    #print('Actuator')
    j=json.loads(cmd)
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

if len(sys.argv) <3:
    print('Usage: python3 actuate.py ae.023356-AC_A1_01_X \'{"cmd":"reset"}\'')
    print(sys.argv)
    sys.exit()
else:
    print(sys.argv)

actuate(f'{sys.argv[1]}',f'{sys.argv[2]}')
print(f'{sys.argv[1]}', f'{sys.argv[2]}')
