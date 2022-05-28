import requests
import json
import sys

if len(sys.argv)<1:
    print('Usage pkython3 read_resource.py http://.......')
    sys.exit()

h={
    "Accept": "application/json",
    "X-M2M-RI": "12345",
    "X-M2M-Origin": "S"
}
url = sys.argv[1]
print('Resource url=', url)
r = requests.get(url, headers=h)
print(json.dumps(r.json(), indent=4))
