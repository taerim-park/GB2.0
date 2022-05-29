# Send_data.py
VERSION='2-2_20220519_1755'
print('\n===========')
print(f'Verion {VERSION}')

import os
from RepeatedTimer import RepeatedTimer

import process_raw_files
from datetime import datetime, timedelta
import conf
import re

ae = conf.ae
root = conf.root
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

next={}
mm_old='00'
hh_old='00'

# handles periodic measure and fft
def do_periodic_data(aename):
    global ae, mm_old, hh_old, root, next, myclock_ok, myclock
    myclock += timedelta(seconds=1)
    cmeasure=ae[aename]['config']['cmeasure']

    if ae[aename]['local']['measurestart']=='N':  # measure is controlled from remote user
        print('measurestart==N, skip periodic data sending')
        return

    if not myclock_ok: myclock_ok=clock()
    if not myclock_ok:
        print('PANIC failed to read board time from file')
        return

    hhmmss = datetime.strftime(myclock,'%H%M%S')
    # first since start
    gogo = False
    if re.match('\d\d\d00\d', hhmmss) and re.match('\d\d\d00\d', hhmmss)[0]==hhmmss:  # 정10분
        if not aename in next:
            print('first run since boot')
            gogo = True
        elif next[aename]< myclock:
            print('시간되었고, 정 10분이다')
            gogo = True

    if gogo:
        process_raw_files.report(aename, myclock)
        next[aename]=myclock +  timedelta(seconds=cmeasure['measureperiod'] - 5)
        print(f'set next measure {next[aename]}')
        myclock_ok=clock()
    else:
        if hhmmss[0:2]!=hh_old:
            if aename in next: print(f"board_time= {datetime.strftime(myclock, '%H:%M:%S')} +{(next[aename]-myclock).total_seconds():.1f}s to next run")
            else: print(f"board_time= {datetime.strftime(myclock, '%H:%M:%S')}")
    hh_old=hhmmss[0:2]
            
    
#복수개 AE는 아래부분에서 완결
def run():
    global ae, myclock_ok
    for aename in ae:
        cmeasure=ae[aename]['config']['cmeasure']
    
        if not 'measureperiod' in cmeasure: cmeasure['measureperiod']=3600
        elif not isinstance(cmeasure['measureperiod'],int): cmeasure['measureperiod']=3600
        elif cmeasure['measureperiod']<600: cmeasure['measureperiod']=600
        cmeasure['measureperiod'] = int(cmeasure['measureperiod']/600)*600
        print(f"cmeasure.measureperiod= {cmeasure['measureperiod']} sec") 

        cmeasure['rawperiod'] = int(cmeasure['measureperiod']/60)
        print(f"cmeasure.rawperiod= {cmeasure['rawperiod']} min")

        print(f"{aename} cmeasure.usefft= {cmeasure['usefft']}") 
        print(f"{aename} ctrigger.use= {ae[aename]['config']['ctrigger']['use']}") 
        print(f"{aename} measurestart= {ae[aename]['local']['measurestart']}")

        # check every sec
        RepeatedTimer(1, do_periodic_data, aename)

    myclock_ok=clock()
    print('Ready')
    print()

if __name__ == '__main__':
    run()
