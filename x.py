import json

a='{"Timestamp": "2022-06-03 02:20:01", "trigger": {"TP": "0", "DI": "0", "DS": "0", "TI": "0", "AC": "0"}, "TI": {"x": -0.61, "y": -0.02, "z": 0.61}, "TP": 0.0, "DI": {"ch4": 632.4224705714886, "ch5": 632.4224705714886}, "AC": [{"x": 11.33, "y": -0.78, "z": 995.81}, {"x": 11.39, "y": -1.05, "z": 995.16}, {"x": 11.48, "y": -1.05, "z": 995.63}, {"x": 11.31, "y": -0.81, "z": 995.41}, {"x": 10.93, "y": -0.78, "z": 995.57}, {"x": 11.13, "y": -1.45, "z": 995.62}, {"x": 11.14, "y": -0.9, "z": 995.12}, {"x": 11.35, "y": -0.95, "z": 995.69}, {"x": 11.43, "y": -1.12, "z": 994.96}, {"x": 11.25, "y": -1.15, "z": 995.56}, {"x": 11.28, "y": -0.95, "z": 995.35}, {"x": 11.12, "y": -0.28, "z": 995.4}, {"x": 10.77, "y": -0.82, "z": 995.49}, {"x": 10.87, "y": -1.01, "z": 995.3}, {"x": 11.15, "y": -0.7, "z": 995.56}, {"x": 11.06, "y": -0.96, "z": 995.16}, {"x": 10.71, "y": -1.07, "z": 995.6}, {"x": 11.37, "y": -0.86, "z": 995.16}, {"x": 10.9, "y": -0.79, "z": 995.66}, {"x": 11.17, "y": -0.69, "z": 995.07}, {"x": 10.98, "y": -1.02, "z": 995.03}, {"x": 10.75, "y": -0.85, "z": 995.52}, {"x": 11.17, "y": -0.99, "z": 995.84}, {"x": 11.33, "y": -1.03, "z": 994.71}, {"x": 11.11, "y": -0.78, "z": 995.3}, {"x": 11.28, "y": -0.92, "z": 994.41}, {"x": 11.03, "y": -0.71, "z": 995.28}, {"x": 10.78, "y": -0.64, "z": 995.02}, {"x": 11.03, "y": -0.88, "z": 995.38}, {"x": 11.31, "y": -0.77, "z": 995.49}, {"x": 11.31, "y": -0.96, "z": 995.19}, {"x": 11.07, "y": -0.73, "z": 995.58}, {"x": 10.98, "y": -0.67, "z": 995.49}, {"x": 11.01, "y": -0.68, "z": 995.52}, {"x": 11.05, "y": -0.92, "z": 995.4}, {"x": 11.35, "y": -0.94, "z": 995.3}, {"x": 11.29, "y": -0.91, "z": 995.56}, {"x": 10.85, "y": -0.97, "z": 995.53}, {"x": 11.42, "y": -0.51, "z": 995.41}, {"x": 11.3, "y": -0.7, "z": 995.33}, {"x": 10.85, "y": -0.5, "z": 995.37}, {"x": 11.42, "y": -0.81, "z": 995.47}, {"x": 11.19, "y": -0.8, "z": 995.21}, {"x": 11.32, "y": -0.97, "z": 995.43}, {"x": 11.31, "y": -1.06, "z": 995.47}, {"x": 11.28, "y": -1.33, "z": 995.55}, {"x": 11.48, "y": -1.21, "z": 995.19}, {"x": 10.92, "y": -0.79, "z": 995.24}, {"x": 11.23, "y": -1.0, "z": 995.49}, {"x": 11.03, "y": -0.52, "z": 995.1}, {"x": 11.05, "y": -1.12, "z": 995.63}, {"x": 10.78, "y": -0.65, "z": 995.92}, {"x": 10.95, "y": -1.11, "z": 996.27}, {"x": 11.03, "y": -0.41, "z": 995.75}, {"x": 11.45, "y": -0.67, "z": 995.08}, {"x": 10.64, "y": -0.9, "z": 994.45}, {"x": 10.83, "y": -0.88, "z": 995.26}, {"x": 11.04, "y": -1.02, "z": 995.03}, {"x": 11.58, "y": -1.0, "z": 995.05}, {"x": 11.27, "y": -1.24, "z": 995.38}, {"x": 10.93, "y": -0.94, "z": 995.23}, {"x": 11.14, "y": -1.29, "z": 994.94}, {"x": 10.96, "y": -1.15, "z": 995.51}, {"x": 11.11, "y": -0.99, "z": 995.55}, {"x": 11.48, "y": -0.53, "z": 995.29}, {"x": 10.93, "y": -0.68, "z": 995.2}, {"x": 11.0, "y": -0.4, "z": 995.69}, {"x": 11.26, "y": -1.06, "z": 995.04}, {"x": 11.52, "y": -1.12, "z": 995.28}, {"x": 11.28, "y": -1.19, "z": 995.21}, {"x": 10.75, "y": -0.73, "z": 994.75}, {"x": 11.15, "y": -0.77, "z": 995.25}, {"x": 11.24, "y": -0.89, "z": 995.15}, {"x": 11.01, "y": -0.89, "z": 995.18}, {"x": 11.4, "y": -0.84, "z": 995.49}, {"x": 11.33, "y": -1.05, "z": 995.12}, {"x": 11.12, "y": -1.15, "z": 995.51}, {"x": 11.15, "y": -0.97, "z": 995.43}, {"x": 10.91, "y": -1.07, "z": 995.55}, {"x": 11.47, "y": -1.03, "z": 994.79}, {"x": 10.9, "y": -0.59, "z": 995.23}, {"x": 11.33, "y": -1.16, "z": 995.47}, {"x": 11.4, "y": -1.25, "z": 995.29}, {"x": 11.31, "y": -1.2, "z": 995.2}, {"x": 11.08, "y": -0.95, "z": 994.64}, {"x": 11.35, "y": -1.02, "z": 994.91}, {"x": 10.84, "y": -1.12, "z": 995.17}, {"x": 11.22, "y": -0.71, "z": 994.46}, {"x": 11.54, "y": -1.12, "z": 995.31}, {"x": 11.1, "y": -0.9, "z": 995.89}, {"x": 10.85, "y": -1.13, "z": 995.16}, {"x": 10.73, "y": -0.87, "z": 994.93}, {"x": 11.36, "y": -1.21, "z": 995.63}, {"x": 11.09, "y": -0.8, "z": 995.45}, {"x": 10.92, "y": -0.91, "z": 995.7}, {"x": 11.19, "y": -0.84, "z": 995.55}, {"x": 11.04, "y": -0.79, "z": 995.06}, {"x": 11.21, "y": -0.86, "z": 995.22}, {"x": 11.4, "y": -0.78, "z": 995.7}, {"x": 11.31, "y": -0.79, "z": 995.41}], "DS": [{"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}, {"x": "00ffffff", "y": "02020202", "z": "03030303"}], "Status": "Ok", "Origin": "CAPTURE"}{"Status": "Ok", "Timestamp": "2022-06-03 02:20:06.272169", "Origin": "RESYNC"}'



def extract(a):
    c=0
    data=[]

    s=0
    for i in range(len(a)):
        if  a[i]=='{': c+=1
        if  a[i]=='}': c-=1
        if c==0: 
            data.append(json.loads(a[s:i+1]))
            s=i+1
    return data

d=extract(a)
for x in d:
    print(x)
