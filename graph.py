import json

def mygraph(d):
    with open("graph.html") as f: format=f.read()
    s=''
    for x in d:
        s+= f",['{x[0]}',{x[1]}]"
    #print(s)
    return format.replace('<%DATA%>', s)
