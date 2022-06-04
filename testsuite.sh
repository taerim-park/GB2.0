ae=('ae.99998888-AC_S1M_01_X'  'ae.99998888-TI_S1M_01_X'  'ae.99998888-DI_S1M_01_X'  'ae.99998888-TP_S1M_01_X')

for aename in ${ae[@]}; do 
    echo ==== Session starts for $aename
    echo; echo 1. setmeasure
    python3 actuate.py  ${aename} '{"cmd":"setmeasure","cmeasure":{"measureperiod":600, "stateperiod":10}}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"setmeasure","cmeasure":{"measureperiod":3600, "stateperiod":60}}'
    sleep 2

    echo; echo 2. measure stop/start
    python3 actuate.py  ${aename} '{"cmd":"measurestop"}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"measurestart"}'
    sleep 2

    echo; echo 3. real stop/start
    python3 actuate.py  ${aename} '{"cmd":"realstop"}'
    sleep 2
    
    python3 actuate.py  ${aename} '{"cmd":"realstart"}'
    sleep 2

    echo; echo 4. reqstate
    python3 actuate.py  ${aename} '{"cmd":"reqstate"}'

    if [[ ${aename} =~ "AC" ]]; then
        echo; echo 5. setrigger
        python3 actuate.py  ${aename}  '{"cmd":"settrigger","ctrigger":{"use":"N"}}'
        sleep 2
    
        python3 actuate.py  ${aename}  '{"cmd":"settrigger","ctrigger":{"use":"Y",}}'
        sleep 2
    fi

    
done


