import streamlit as st
import collections
import random
import numpy as np
import pandas as pd
import math
import matplotlib.pyplot as plt
import scipy.stats as stt

# Konfigurasi Halaman (Harus di paling atas)
st.set_page_config(page_title="Queueing System Simulator", layout="wide", page_icon="⚙️")


# 1. CORE SIMULATOR LOGIC 

class QueueingSystemSimulator:
    def __init__(self, params):
        self.original_params = params
        self.reset()

    def reset(self, new_params=None):
        if new_params:
            self.original_params = new_params
        
        p = self.original_params
        self.num_servers = p['num_servers']
        self.queue_capacity = p['capacity']
        self.priority_enabled = p.get('priority_enabled', False)
        self.warmup_time = p.get('warmup_time', 0.0) 
        self.interarrival_times = collections.deque(p['interarrivals'])
        self.service_times = collections.deque(p['services'])
        self.priorities = collections.deque(p['priorities'])
        self.max_customers = len(self.service_times)
        self.cost_wait_per_unit_time = p['cost_wait']
        self.cost_server_per_unit_time = p['cost_server']

        self.servers = [{'status': 'idle', 'customer_id': None, 'departure_time': float('inf')} for _ in range(self.num_servers)]
        self.vip_queue = collections.deque()
        self.regular_queue = collections.deque()
        self.sim_clock = 0.0

        self.next_arrival_time = self.interarrival_times.popleft() if self.interarrival_times else float('inf')

        self.time_of_last_event = 0.0
        self.total_delay = 0.0
        self.total_server_busy_time = 0.0
        self.num_delayed = 0
        self.customers_served = 0
        self.customers_served_after_warmup = 0 
        self.area_under_Q_t = 0.0
        self.customers_rejected = 0
        
        self.customer_data = {}
        self.completed_customers_details = []
        self.next_customer_id = 1

    def _get_next_departure(self):
        min_dept_time = float('inf')
        server_idx = -1
        for i, server in enumerate(self.servers):
            if server['departure_time'] < min_dept_time:
                min_dept_time = server['departure_time']
                server_idx = i
        return min_dept_time, server_idx

    def _get_idle_server(self):
        for i, server in enumerate(self.servers):
            if server['status'] == 'idle':
                return i
        return -1

    def _update_stats(self):
       
        if self.sim_clock > self.time_of_last_event:
            if self.sim_clock > self.warmup_time:
                effective_last_event = max(self.time_of_last_event, self.warmup_time)
                time_since_last_update = self.sim_clock - effective_last_event
                
                num_busy_servers = sum(1 for s in self.servers if s['status'] == 'busy')
                self.area_under_Q_t += (len(self.vip_queue) + len(self.regular_queue)) * time_since_last_update
                self.total_server_busy_time += num_busy_servers * time_since_last_update

    def _arrival(self):
        arrival_time = self.sim_clock
        service_time = self.service_times.popleft() if self.service_times else 0
        priority = self.priorities.popleft() if self.priorities else 'regular'
        
        if self.interarrival_times:
            self.next_arrival_time = self.sim_clock + self.interarrival_times.popleft()
        else:
            self.next_arrival_time = float('inf')

        idle_server_idx = self._get_idle_server()
        if idle_server_idx != -1:
            log = self._serve_customer(idle_server_idx, self.next_customer_id, arrival_time, service_time)
        else:
            if (len(self.vip_queue) + len(self.regular_queue)) < self.queue_capacity:
                queue_to_join = self.vip_queue if self.priority_enabled and priority == 'vip' else self.regular_queue
                queue_to_join.append(self.next_customer_id)
                self.customer_data[self.next_customer_id] = {'arrival_time': arrival_time, 'service_time': service_time, 'priority': priority}
                log = f"Arrival C{self.next_customer_id} ({priority}), enters queue."
            else:
                self.customers_rejected += 1
                log = f"Arrival C{self.next_customer_id}, REJECTED (queue full)."
        
        self.next_customer_id += 1
        return log

    def _departure(self, server_idx):
        departed_customer_id = self.servers[server_idx]['customer_id']
        self.customers_served += 1
        
        self.servers[server_idx]['status'] = 'idle'
        self.servers[server_idx]['customer_id'] = None
        self.servers[server_idx]['departure_time'] = float('inf')

        if self.priority_enabled and len(self.vip_queue) > 0:
            next_customer_id = self.vip_queue.popleft()
            data = self.customer_data[next_customer_id]
            self._serve_customer(server_idx, next_customer_id, data['arrival_time'], data['service_time'])
        elif len(self.regular_queue) > 0:
            next_customer_id = self.regular_queue.popleft()
            data = self.customer_data[next_customer_id]
            self._serve_customer(server_idx, next_customer_id, data['arrival_time'], data['service_time'])
            
        return f"Departure C{departed_customer_id} from Server {server_idx + 1}"

    def _serve_customer(self, server_idx, cust_id, arrival_time, service_time):
        self.servers[server_idx]['status'] = 'busy'
        self.servers[server_idx]['customer_id'] = cust_id
        self.servers[server_idx]['departure_time'] = self.sim_clock + service_time
        
        delay = self.sim_clock - arrival_time
        
      
        if arrival_time >= self.warmup_time:
            self.total_delay += delay
            self.customers_served_after_warmup += 1
            if delay > 0: self.num_delayed += 1
        
        self.completed_customers_details.append({
            "id": cust_id, "arrival_time": arrival_time, "wait_delay": delay,
            "service_start_time": self.sim_clock, "service_time": service_time,
            "departure_time": self.servers[server_idx]['departure_time'],
            "server_id": server_idx + 1
        })
        return f"Arrival C{cust_id}, served by Server {server_idx + 1}."

    def step(self):
        if self.customers_served >= self.max_customers and self.max_customers > 0:
            return None, True, "Simulation Finished"

        next_dept_time, next_dept_server_idx = self._get_next_departure()
        is_arrival = self.next_arrival_time < next_dept_time
        
        if is_arrival and self.next_arrival_time != float('inf'):
            self.sim_clock = self.next_arrival_time
            self._update_stats()
            event_log = self._arrival()
        elif next_dept_time != float('inf'):
            self.sim_clock = next_dept_time
            self._update_stats()
            event_log = self._departure(next_dept_server_idx)
        else:
             return None, True, "Simulation Finished (no more events)"

        self.time_of_last_event = self.sim_clock
        is_finished = self.customers_served >= self.max_customers if self.max_customers > 0 else False
        return self.get_state(), is_finished, event_log

    def get_state(self):
        return {
            "clock": self.sim_clock, "servers": self.servers,
            "vip_queue": list(self.vip_queue), "regular_queue": list(self.regular_queue),
            "next_arrival": self.next_arrival_time, "next_departure": self._get_next_departure()[0],
            "num_delayed": self.num_delayed, "total_delay": self.total_delay,
            "area_Q_t": self.area_under_Q_t, "area_B_t": self.total_server_busy_time,
            "last_event_time": self.time_of_last_event
        }

    def calculate_report(self):
        effective_time = max(0.0, self.time_of_last_event - self.warmup_time)
        
      
        avg_delay = self.total_delay / self.customers_served_after_warmup if self.customers_served_after_warmup > 0 else 0.0
        avg_num_in_queue = self.area_under_Q_t / effective_time if effective_time > 0 else 0.0
        avg_server_utilization = self.total_server_busy_time / (self.num_servers * effective_time) if effective_time > 0 else 0.0
        
        total_wait_cost = self.total_delay * self.cost_wait_per_unit_time
        total_server_cost = self.total_server_busy_time * self.cost_server_per_unit_time

        report = {
            "d(n) - Avg Delay": avg_delay,
            "q(n) - Avg # in Queue": avg_num_in_queue,
            "u(n) - Utilization": avg_server_utilization,
            "Number of customers rejected": self.customers_rejected,
            "Total simulation time T(n)": self.time_of_last_event,
            "Effective Time (Post-Warmup)": effective_time
        }

        if self.cost_wait_per_unit_time > 0 or self.cost_server_per_unit_time > 0:
            report["Total waiting cost"] = total_wait_cost
            report["Total server operational cost"] = total_server_cost
            report["Total system cost"] = total_wait_cost + total_server_cost
        
        return report


# 2. STREAMLIT UI & STATE MANAGEMENT


if 'simulator' not in st.session_state:
    initial_params = {
        'interarrivals': [0.4, 1.2, 0.5, 1.7, 0.2, 1.6, 0.2, 1.4, 1.9],
        'services': [2.0, 0.7, 0.2, 1.1, 3.7, 0.6],
        'priorities': ['regular'] * 6,
        'num_servers': 1, 'capacity': float('inf'),
        'cost_wait': 0.0, 'cost_server': 0.0,
        'priority_enabled': False, 'warmup_time': 0.0
    }
    st.session_state.simulator = QueueingSystemSimulator(initial_params)
    st.session_state.logs = []
    st.session_state.plot_time = [0]
    st.session_state.plot_q_t = [0]
    st.session_state.plot_b_t = [0]
    st.session_state.is_finished = False
    st.session_state.rep_report = None

def parse_list(text): return [float(x.strip()) for x in text.split(',') if x.strip()]
def parse_str_list(text): return [x.strip().lower() for x in text.split(',') if x.strip()]

def reset_sim(params, seed_val):
    # Set Seed for Reproducibility
    random.seed(seed_val)
    np.random.seed(seed_val)
    
    st.session_state.simulator.reset(params)
    st.session_state.logs = ["Simulation reset with new data (Seed Applied)."]
    st.session_state.plot_time = [0]
    st.session_state.plot_q_t = [0]
    st.session_state.plot_b_t = [0]
    st.session_state.is_finished = False
    st.session_state.rep_report = None

def step_sim():
    if st.session_state.is_finished: return
    state, finished, log = st.session_state.simulator.step()
    if state is None:
        st.session_state.is_finished = True
        st.session_state.logs.append("--- SIMULATION FINISHED ---")
        return
    
    st.session_state.logs.append(f"Clock {st.session_state.simulator.sim_clock:.2f}: {log}")
    
    sim = st.session_state.simulator
    if sim.sim_clock > st.session_state.plot_time[-1]:
        st.session_state.plot_time.append(sim.sim_clock)
        st.session_state.plot_q_t.append(len(state['vip_queue']) + len(state['regular_queue']))
        st.session_state.plot_b_t.append(sum(1 for s in state['servers'] if s['status'] == 'busy'))
        
    if finished:
        st.session_state.is_finished = True
        st.session_state.logs.append("--- SIMULATION FINISHED ---")


# SIDEBAR (Input Parameters)

st.sidebar.title("⚙️ Parameters")

with st.sidebar.expander("General Settings", expanded=True):
    random_seed = st.number_input("Random Seed (Reproducibility)", value=42, step=1)
    warmup_time = st.number_input("Warm-up Time (T_w)", min_value=0.0, value=0.0, step=1.0, help="Buang statistik awal sistem untuk menghindari Bias Inisialisasi.")
    num_servers = st.number_input("Number of Servers (c)", min_value=1, value=1)
    cap_str = st.text_input("Queue Capacity (K)", value="inf")
    capacity = float('inf') if cap_str.lower() == 'inf' else float(cap_str)
    
    priority_enabled = st.checkbox("Enable Customer Priority", value=False)
    cost_enabled = st.checkbox("Enable Cost Analysis", value=False)
    
    cost_wait, cost_server = 0.0, 0.0
    if cost_enabled:
        cost_wait = st.number_input("Waiting Cost (per unit)", min_value=0.0, value=0.0)
        cost_server = st.number_input("Server Cost (per unit)", min_value=0.0, value=0.0)

with st.sidebar.expander("Data Input Mode", expanded=True):
    input_mode = st.radio("Mode:", ["Manual", "Distribution"])
    
    if input_mode == "Manual":
        inter_txt = st.text_area("Inter-arrival Times (Aᵢ)", "0.4, 1.2, 0.5, 1.7, 0.2, 1.6, 0.2, 1.4, 1.9")
        serv_txt = st.text_area("Service Times (Sᵢ)", "2.0, 0.7, 0.2, 1.1, 3.7, 0.6")
        if priority_enabled:
            prio_txt = st.text_area("Priorities (vip/regular)", "regular, regular, regular, regular, regular, regular")
            
        try:
            interarrivals = parse_list(inter_txt)
            services = parse_list(serv_txt)
            priorities = parse_str_list(prio_txt) if priority_enabled else ['regular'] * len(services)
        except:
            st.error("Format Data Error")
            
    elif input_mode == "Distribution":
        arr_mean = st.number_input("Mean Interarrival (1/λ)", value=1.0)
        srv_mean = st.number_input("Mean Service Time (1/μ)", value=0.8)
        srv_std = st.number_input("Service Std. Dev. (σ)", value=0.2)
        num_cust = st.number_input("Number of Customers (n)", min_value=1, value=50)
        
        vip_pct = 0.0
        if priority_enabled:
            vip_pct = st.slider("% VIP Customers", 0, 100, 10) / 100.0
            
      
        mu_lognorm = math.log(srv_mean**2 / math.sqrt(srv_mean**2 + srv_std**2))
        sigma_lognorm = math.sqrt(math.log(1 + (srv_std**2 / srv_mean**2)))
        
      
        random.seed(random_seed)
        interarrivals = [random.expovariate(1.0/arr_mean) for _ in range(num_cust)]
        services = [random.lognormvariate(mu_lognorm, sigma_lognorm) for _ in range(num_cust)]
        priorities = ['vip' if random.random() < vip_pct else 'regular' for _ in range(num_cust)]

st.sidebar.markdown("---")

col1, col2 = st.sidebar.columns(2)
if col1.button("🔄 Load & Reset", use_container_width=True):
    params = {
        'num_servers': num_servers, 'capacity': capacity, 'warmup_time': warmup_time,
        'priority_enabled': priority_enabled, 'cost_wait': cost_wait, 'cost_server': cost_server,
        'interarrivals': interarrivals, 'services': services, 'priorities': priorities
    }
    reset_sim(params, random_seed)

if col2.button("▶ Next Step", use_container_width=True, disabled=st.session_state.is_finished):
    step_sim()

if st.sidebar.button("⏩ Fast Forward (Run All)", type="primary", use_container_width=True, disabled=st.session_state.is_finished):
    with st.spinner("Running simulation..."):
        while not st.session_state.is_finished:
            step_sim()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Replications")
num_reps = st.sidebar.number_input("Number of Replications", min_value=2, value=100)
if st.sidebar.button("Run Replications", use_container_width=True):
    with st.spinner(f"Running {num_reps} replications..."):
        rep_results = collections.defaultdict(list)
        progress_bar = st.sidebar.progress(0)
        
        base_p = {
            'num_servers': num_servers, 'capacity': capacity, 'warmup_time': warmup_time,
            'priority_enabled': priority_enabled, 'cost_wait': cost_wait, 'cost_server': cost_server,
            'interarrivals': interarrivals, 'services': services, 'priorities': priorities
        }
        
       
        for i in range(num_reps):
            random.seed(random_seed + i) 
            
         
            if input_mode == "Distribution":
                base_p['interarrivals'] = [random.expovariate(1.0/arr_mean) for _ in range(num_cust)]
                base_p['services'] = [random.lognormvariate(mu_lognorm, sigma_lognorm) for _ in range(num_cust)]
                base_p['priorities'] = ['vip' if random.random() < vip_pct else 'regular' for _ in range(num_cust)]

            sim = QueueingSystemSimulator(base_p)
            while not (sim.customers_served >= sim.max_customers and sim.max_customers > 0):
                _, finished, _ = sim.step()
                if finished: break
            
            report = sim.calculate_report()
            for k, v in report.items(): rep_results[k].append(v)
            progress_bar.progress((i + 1) / num_reps)
            
        st.session_state.rep_report = rep_results
        st.success("Replications finished! Check the Replication Report tab.")


# MAIN CONTENT AREA

st.title("Queueing System Simulator")
st.markdown("Advanced Discrete Event Simulation (DES) Tool with Prioritized Queues & Data-Driven Insights.")


def render_canvas(state, priority_enabled):
    servers_html = ""
    for i, s in enumerate(state['servers']):
        bg_color = "#27ae60" if s['status'] == 'busy' else "#95a5a6"
        cust_text = f"<br><small>C{s['customer_id']}</small>" if s['customer_id'] else ""
        servers_html += f"""
        <div style="background-color: {bg_color}; color: white; padding: 10px; margin: 5px; border-radius: 5px; text-align: center; width: 80px;">
            <b>S{i+1}</b>{cust_text}
        </div>
        """
        
    def render_q(q_list, color, title):
        q_html = f"<div style='margin-bottom: 20px;'><b>{title}</b><div style='display: flex; flex-direction: row-reverse; justify-content: flex-end; flex-wrap: wrap; gap: 8px;'>"
        for c in reversed(q_list):
             q_html += f"<div style='background-color: {color}; color: white; width: 40px; height: 40px; border-radius: 5px; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;'>C{c}</div>"
        q_html += "</div></div>"
        return q_html

    queues_html = ""
    if priority_enabled:
        queues_html += render_q(state['vip_queue'], "#c0392b", "VIP QUEUE")
        queues_html += render_q(state['regular_queue'], "#e67e22", "REGULAR QUEUE")
    else:
        queues_html += render_q(state['regular_queue'], "#3498db", "QUEUE")

    html = f"""
    <div style="background-color: #E5E1DA; padding: 20px; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; min-height: 250px;">
        <div style="flex-grow: 1; margin-right: 50px;">
            {queues_html}
        </div>
        <div style="display: flex; flex-direction: column;">
            {servers_html}
        </div>
    </div>
    """
    return html

# Show Visualization
st.markdown("### 🖥️ System Visualization")
current_state = st.session_state.simulator.get_state()
st.components.v1.html(render_canvas(current_state, st.session_state.simulator.priority_enabled), height=280)

# TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📈 Real-time Graph", "📋 Statistics", "📝 Event Log", 
    "📄 Final Report", "📊 Replication Report", "ℹ️ Help & About"
])

with tab1:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
    
    ax1.step(st.session_state.plot_time, st.session_state.plot_q_t, where='post', color='#e67e22')
    ax1.axvline(x=warmup_time, color='r', linestyle='--', alpha=0.5, label='Warm-up End')
    ax1.set_title("Number of Customers in Queue (Q(t))")
    ax1.set_ylabel("Customers")
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    ax2.step(st.session_state.plot_time, st.session_state.plot_b_t, where='post', color='#27ae60')
    ax2.axvline(x=warmup_time, color='r', linestyle='--', alpha=0.5, label='Warm-up End')
    ax2.set_title("Number of Busy Servers (B(t))")
    ax2.set_xlabel("Simulation Time")
    ax2.set_ylabel("Servers")
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    plt.tight_layout()
    st.pyplot(fig)

with tab2:
    if st.session_state.simulator.completed_customers_details:
        df = pd.DataFrame(st.session_state.simulator.completed_customers_details)
        df.columns = ['C ID', 'tᵢ (Arrival)', 'Dᵢ (Delay)', 'Start Time', 'Sᵢ (Service)', 'cᵢ (Departure)', 'Server']
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No customers have completed service yet.")

with tab3:
    log_str = "\n".join(st.session_state.logs)
    st.text_area("Event History", log_str, height=300, disabled=True)

with tab4:
    if st.session_state.is_finished:
        st.subheader("Final Performance Measures")
        if warmup_time > 0:
            st.warning(f"Note: Stats collected AFTER warm-up time ({warmup_time}).")
        
        report = st.session_state.simulator.calculate_report()
        for k, v in report.items():
            st.metric(label=k, value=f"{v:.4f}")
            
        df = pd.DataFrame([report])
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Report (CSV)", csv, "final_report.csv", "text/csv")
    else:
        st.info("Simulation must finish to generate the final report.")

with tab5:
    if st.session_state.rep_report:
        st.subheader(f"Replication Results (n={num_reps})")
        
        rep_data = []
        for key, values in st.session_state.rep_report.items():
            mean = np.mean(values)
            stdev = np.std(values, ddof=1) if len(values) > 1 else 0
            
            
            if len(values) > 1:
                t_crit = stt.t.ppf(0.975, df=len(values)-1)
                half_width = t_crit * (stdev / math.sqrt(len(values)))
            else:
                half_width = 0.0
                
            rep_data.append({
                "Metric": key, "Mean": mean, "Std. Dev.": stdev, "95% C.I. Half-Width": half_width
            })
            
        rep_df = pd.DataFrame(rep_data)
        st.dataframe(rep_df, use_container_width=True)
        
        csv_rep = rep_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Replication Report (CSV)", csv_rep, "replication_report.csv", "text/csv")
    else:
        st.info("Run Replications from the sidebar to see results here.")


# 3. HELP & ABOUT TAB

with tab6:
    st.header("Notations & Formulas")
    st.markdown("### Input Variables & Notations")
    colA, colB = st.columns(2)
    with colA:
        st.markdown("""
        * **$t_i$** : Waktu kedatangan pelanggan ke-i ($t_0 = 0$)
        * **$A_i$** : Waktu antar-kedatangan (*Interarrival time*) antara kedatangan ke-(i-1) dan ke-i ($A_i = t_i - t_{i-1}$)
        * **$S_i$** : Waktu yang dihabiskan server melayani pelanggan ke-i (*Service time*)
        * **$D_i$** : Waktu tunggu (delay) di antrean pelanggan ke-i
        """)
    with colB:
        st.markdown("""
        * **$c_i$** : Waktu pelanggan ke-i selesai dan pergi ($c_i = t_i + D_i + S_i$)
        * **$e_i$** : Waktu kemunculan event ke-i
        * **$\lambda$** : Tingkat Kedatangan / Arrival Rate (pelanggan per unit waktu)
        * **$\mu$** : Tingkat Layanan / Service Rate (pelanggan per unit waktu, per server)
        """)

    st.markdown("### Performance Measure Formulas (Updated)")
    st.latex(r"d(n) = \frac{\sum_{i=1}^{n} D_i}{n}")
    st.caption("Rata-rata penundaan di antrean untuk $n$ pelanggan (Termasuk yang delay-nya 0).")
    
    st.latex(r"q(n) = \frac{\int_0^{T(n)} Q(t)dt}{T(n)}")
    st.caption("Rata-rata waktu jumlah pelanggan di dalam antrean.")
    
    st.latex(r"u(n) = \frac{\int_0^{T(n)} B(t)dt}{c \times T(n)}")
    st.caption("Rata-rata waktu pemanfaatan (utilization) server. ($c$ = jumlah server)")

    st.markdown("---")
    st.header("About This Program")
    st.markdown("""
    **Developers:**
    * Benedict Michael Pepper
    * Yudhistira Nalendra Aryadhewa Az-zhafir
    
    **Institution:**
    * Informatics Engineering Study Program, Ma Chung University
    
    **Description:**
    This simulator is an advanced discrete-event analysis tool for multi-server queueing systems.
    **V2 Edition:** Now features initialization bias removal (Warm-up Period), reproducible stochastic seeds, mathematically correct Lognormal service time distributions, and valid T-Distribution Confidence Intervals.
    """)