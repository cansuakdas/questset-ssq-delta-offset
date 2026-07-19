'''
import pandas as pd
import numpy as np

# 1. Trafik verisi
traffic = pd.read_csv('group1_order1_user0_fast_traffic.csv')
traffic = traffic[traffic['direction'] == 'DL']
dt = traffic['time'].diff().dropna()
latency = dt.mean()
jitter = dt.std()

# 2. Hareket verisi
move = pd.read_csv('group1_order1_user0_fast_movement.csv')
v = np.sqrt(np.diff(move['HeadPosX'])**2 + np.diff(move['HeadPosY'])**2 + np.diff(move['HeadPosZ'])**2)
motion_intensity = v.mean()

# 3. SSQ data conversion to numeric values
ssq = pd.read_csv('SSQ.csv')
scale = {'None':0, 'Slight':1, 'Moderate':2, 'Severe':3}
ssq_num = ssq.replace(scale)
# Nausea subscores
nausea = ssq_num[['Nausea','Stomach awareness','Burping','Sweating']].mean(axis=1)
ocular = ssq_num[['Headache','Eyestrain','Fatigue','Difficulty focusing','Blurred vision']].mean(axis=1)
disor = ssq_num[['Dizziness (eyes open)','Dizziness (eyes closed)','Vertigo','Fullness of the head']].mean(axis=1)
ssq['SSQ_Total'] = 3.74*nausea + 5.93*ocular + 9.54*disor

# 4. Summary table
summary = pd.DataFrame({
    'ID': ['group1_order1_user0'],
    'Latency': [latency],
    'Jitter': [jitter],
    'MotionIntensity': [motion_intensity],
    'SSQ_Total': [ssq.loc[ssq['ID']=='group1_order1_user0'].iloc[-1]['SSQ_Total']]
})
 '''

import pandas as pd
import numpy as np

USER = "group1_order1_user0"
FAST_MOV = f"{USER}_fast_movement.csv"
FAST_TRA = f"{USER}_fast_traffic.csv"

traffic = pd.read_csv(FAST_TRA)
dl = traffic[traffic["direction"]=="DL"].copy()
dt = dl["time"].diff().dropna().to_numpy()          # s
latency_ms = dt.mean()*1e3
jitter_ms  = dt.std()*1e3
bitrate_mbps = (dl["size"].sum()*8) / (dl["time"].iloc[-1]-dl["time"].iloc[0]) / 1e6


move = pd.read_csv(FAST_MOV)
# Time step used to calculate physical speed
dtm = np.diff(move["time"].to_numpy())              # s, ~1/60
dx = np.diff(move["HeadPosX"].to_numpy())
dy = np.diff(move["HeadPosY"].to_numpy())
dz = np.diff(move["HeadPosZ"].to_numpy())
speed = np.sqrt(dx*dx + dy*dy + dz*dz) / dtm        # m/s
motion_intensity = np.nanmean(speed)                # Mean speed

ssq = pd.read_csv("SSQ.csv")
ssq_u = ssq[ssq["ID"]==USER].copy()

symptom_cols = [
    "General discomfort","Fatigue","Headache","Eyestrain","Difficulty focusing",
    "Increased salivation","Nausea","Difficulty concentrating","Fullness of the head",
    "Blurred vision","Dizziness (eyes closed)","Dizziness (eyes open)","Vertigo",
    "Stomach awareness","Burping","Sweating"
]

scale = {"None":0, "Slight":1, "Moderate":2, "Severe":3}
for c in symptom_cols:
    ssq_u[c] = ssq_u[c].map(scale).astype("Int64")

N_cols = ["Nausea","Stomach awareness","Burping","Sweating"]
O_cols = ["General discomfort","Fatigue","Headache","Eyestrain","Difficulty focusing","Blurred vision","Difficulty concentrating"]
D_cols = ["Fullness of the head","Dizziness (eyes open)","Dizziness (eyes closed)","Vertigo"]
N = ssq_u[N_cols].sum(axis=1)
O = ssq_u[O_cols].sum(axis=1)
D = ssq_u[D_cols].sum(axis=1)

ssq_u["SSQ_Total"] = 9.54*N + 7.58*O + 13.92*D

# Oturum sonu anketi (Questionnaire number = 4) skoru:
ssq_end = ssq_u.sort_values("Questionnaire number").iloc[-1]["SSQ_Total"]

row = {
    "ID": USER,
    "Latency_ms": latency_ms,
    "Jitter_ms": jitter_ms,
    "Bitrate_Mbps": bitrate_mbps,
    "MotionIntensity_mps": motion_intensity,
    "SSQ_Total": float(ssq_end)
}
print(row)







