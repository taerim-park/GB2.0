VERSION='2-2_20220519_1755'
print('\n===========')
print(f'Verion {VERSION}')

from datetime import datetime, timedelta
from RepeatedTimer import RepeatedTimer
import os
import re

import process_state
import conf
ae = conf.ae
root = conf.root

next={}
mm_old='00'
myclock=''
myclock_ok=False

def clock():
    global myclock, root
    with open(f"{root}/board_time.json") as f: stime = f.read()
    try:
        now = datetime.strptime(stime,'%Y-%m-%d %H:%M:%S.%f')
        print(f'sync clock {myclock} -> {now}')
        myclock = now
        return True
    except:
        print(f'failed  stime= {stime}')
        return False

import signal
def sigint_handler(signal, frame):
    print()
    print()
    print('got restart command.  exiting...')
    os._exit(0)
signal.signal(signal.SIGINT, sigint_handler)

def do_periodic_state(aename):
    global ae, mm_old, next, myclock, myclock_ok
    myclock += timedelta(seconds=1)
    cmeasure=ae[aename]['config']['cmeasure']
    #print(now)
    if not myclock_ok: myclock_ok=clock()
    if not myclock_ok:
        print('PANIC failed to read board time from file')
        return

    hhmmss = datetime.strftime(myclock,'%H%M%S')
    gogo = False
    if re.match('\d\d\d5\d\d', hhmmss) and re.match('\d\d\d5\d\d', hhmmss)[0]==hhmmss:  # 정5분
        if not aename in next:
            print('first run since boot, 정5분')
            gogo = True
        elif next[aename]< myclock:
            print('시간되었고, 정 5분이다')
            gogo = True

    if gogo:
        process_state.report(aename)
        next[aename]=myclock + timedelta(seconds=cmeasure['stateperiod']*60-5)
        print(f'set next state {next[aename]}')
        myclock_ok=clock()
    else:
        if hhmmss[2:4]!=mm_old:
            if aename in next: print(f"board_time= {datetime.strftime(myclock, '%H:%M:%S')} +{(next[aename]-myclock).total_seconds()}s to next run")
            else: print(f"board_time= {datetime.strftime(myclock, '%H:%M:%S')}")
    mm_old=hhmmss[2:4]

#복수개 AE는 아래부분에서 완결
def run():
    global ae, myclock_ok
    for aename in ae:
        cmeasure=ae[aename]['config']['cmeasure']

        if not 'stateperiod' in cmeasure: cmeasure['stateperiod']=60 #min
        elif not isinstance(cmeasure['stateperiod'],int): cmeasure['stateperiod']=60
        print(f"cmeasure.stateperiod= {cmeasure['stateperiod']} min")

        # check every sec
        RepeatedTimer(1, do_periodic_state, aename)

    myclock_ok=clock()
    print('Ready')
    print()

if __name__ == "__main__":
    run()
