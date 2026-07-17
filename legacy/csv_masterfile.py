import numpy as np
import pandas as pd
import heapq

# ===================== GLOBAL PARAMETERS =====================

np.random.seed(42)

DT = 0.01                 # scheduling interval (s)
SIM_TIME = 1.0            # total simulation time (s)

SNR_THRESHOLD_DB = 5.0
SNR_THRESHOLD = 10 ** (SNR_THRESHOLD_DB / 10)

TX_POWER = 100.0
SIGMA_RAYLEIGH = 1.0

RISK_WEIGHT = 0.7         # risk priority factor

# ===================== DATA STRUCTURES =====================

class Packet:
    def __init__(self, pid, user_id, arrival, deadline, risk):
        self.pid = pid
        self.user_id = user_id
        self.arrival = arrival
        self.deadline = deadline
        self.risk = risk

    def slack(self, now):
        return self.deadline - now

    def __lt__(self, other):
        return self.deadline < other.deadline

# ===================== CHANNEL MODEL =====================

def rayleigh_channel():
    h = np.random.rayleigh(SIGMA_RAYLEIGH)
    snr = (h ** 2) * TX_POWER
    return snr

# ===================== SCHEDULER =====================

def select_packet(queue, now):
    """
    Risk + delay aware EDF scheduling
    """
    best_pkt = None
    best_metric = np.inf

    for pkt in queue:
        metric = pkt.slack(now)

        if pkt.risk == 1:
            metric *= RISK_WEIGHT

        if metric < best_metric:
            best_metric = metric
            best_pkt = pkt

    queue.remove(best_pkt)
    heapq.heapify(queue)
    return best_pkt

# ===================== LOAD CSV DATA =====================

# Example CSV format:
# packet_id,user_id,arrival_time,deadline,risk_flag
df = pd.read_csv("packets_per_user.csv")

packet_queue = []
all_packets = []

for _, row in df.iterrows():
    pkt = Packet(
        pid=row["packet_id"],
        user_id=row["user_id"],
        arrival=row["arrival_time"],
        deadline=row["deadline"],
        risk=row["risk_flag"]
    )
    all_packets.append(pkt)

# ===================== USER CHANNELS =====================

user_channels = {}
for uid in df["user_id"].unique():
    user_channels[uid] = rayleigh_channel()

# ===================== SIMULATION =====================

time = 0.0
sent = 0
dropped = 0

while time < SIM_TIME:

    # Activate arriving packets
    for pkt in all_packets:
        if abs(pkt.arrival - time) < 1e-6:
            heapq.heappush(packet_queue, pkt)

    if packet_queue:
        pkt = select_packet(packet_queue, time)
        snr = user_channels[pkt.user_id]

        threshold = SNR_THRESHOLD
        if pkt.risk == 1:
            threshold *= RISK_WEIGHT

        if snr >= threshold:
            sent += 1
        else:
            heapq.heappush(packet_queue, pkt)

    # Drop expired packets
    alive = []
    for pkt in packet_queue:
        if pkt.deadline < time:
            dropped += 1
        else:
            alive.append(pkt)

    packet_queue = alive
    heapq.heapify(packet_queue)

    time += DT

print("SIMULATION RESULTS")
print("------------------")
print(f"Sent packets   : {sent}")
print(f"Dropped packets: {dropped}")
print(f"Remaining      : {len(packet_queue)}")
