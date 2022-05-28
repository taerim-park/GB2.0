import requests
import json
import sys

import conf
host = conf.host
port = conf.port
cse = conf.cse
ae = conf.ae

root=conf.root

print('\n1. CB 조회', f'host= {host}')
h={
    "Accept": "application/json",
    "X-M2M-RI": "12345",
    "X-M2M-Origin": "S",
    "Host": F'{host}'
}
url = F"http://{host}:7579/{cse['name']}"
r = requests.get(url, headers=h)
print(f"{cse['name']}", json.dumps(r.json(),indent=4))

print('\n2. AE/Container 조회')

for k in ae:
    url2 = F"{url}/{k}"
    r = requests.get(url2, headers=h)
    #if "m2m:dbg" in r.json():
        #sys.exit()
    print(f'{k}', json.dumps(r.json(),indent=4))
    for ct in ae[k]:
        url3 = F"{url2}/{ct}"
        r = requests.get(url3, headers=h)
        #if "m2m:dbg" in r.json():
            #sys.exit()
        print(f' {k}/{ct}', json.dumps(r.json(),indent=4))
        if ct in {'ctrigger', 'time', 'cmeasure', 'connect', 'info','install','imeasure'}:
            for subct in ae[k][ct]:
                url4 = F"{url3}/{subct}"
                r = requests.get(url4, headers=h)
                #if "m2m:dbg" in r.json():
                    #sys.exit()
                print(f'  {k}/{ct}/{subct}', json.dumps(r.json(),indent=4))
    print()
