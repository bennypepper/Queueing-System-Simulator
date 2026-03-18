import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import collections
import random
import numpy as np
import csv
import math
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class QueueingSystemSimulator:
    """
    This class contains the core logic for the multi-server queueing simulation.
    It includes priority queues, cost analysis, and detailed logging.
    """

    def __init__(self, params):
        self.original_params = params
        self.reset()

    def reset(self, new_params=None):
        """Resets the simulation to its initial state at time 0."""
        if new_params:
            self.original_params = new_params
        
        p = self.original_params

        # --- Simulation Parameters ---
        self.num_servers = p['num_servers']
        self.queue_capacity = p['capacity']
        self.priority_enabled = p.get('priority_enabled', False)
        self.interarrival_times = collections.deque(p['interarrivals'])
        self.service_times = collections.deque(p['services'])
        self.priorities = collections.deque(p['priorities'])
        self.max_customers = len(self.service_times)
        self.cost_wait_per_unit_time = p['cost_wait']
        self.cost_server_per_unit_time = p['cost_server']

        # --- System State & Clock ---
        self.servers = [{'status': 'idle', 'customer_id': None, 'departure_time': float('inf')} for _ in range(self.num_servers)]
        self.vip_queue = collections.deque()
        self.regular_queue = collections.deque()
        self.sim_clock = 0.0

        # --- Event List ---
        self.next_arrival_time = self.interarrival_times.popleft() if self.interarrival_times else float('inf')

        # --- Statistical Counters ---
        self.time_of_last_event = 0.0
        self.total_delay = 0.0
        self.total_server_busy_time = 0.0
        self.num_delayed = 0
        self.area_under_Q_t = 0.0
        self.customers_served = 0
        self.customers_rejected = 0
        
        # --- Data Logging ---
        self.customer_data = {}
        self.completed_customers_details = []
        self.next_customer_id = 1

    def _get_next_departure(self):
        """Finds the earliest departure time and the server index."""
        min_dept_time = float('inf')
        server_idx = -1
        for i, server in enumerate(self.servers):
            if server['departure_time'] < min_dept_time:
                min_dept_time = server['departure_time']
                server_idx = i
        return min_dept_time, server_idx

    def _get_idle_server(self):
        """Finds the index of an idle server, if any."""
        for i, server in enumerate(self.servers):
            if server['status'] == 'idle':
                return i
        return -1

    def _update_stats(self):
        """Updates area-based statistical counters before an event occurs."""
        if self.sim_clock > self.time_of_last_event:
            time_since_last_event = self.sim_clock - self.time_of_last_event
            num_busy_servers = sum(1 for s in self.servers if s['status'] == 'busy')
            self.area_under_Q_t += (len(self.vip_queue) + len(self.regular_queue)) * time_since_last_event
            self.total_server_busy_time += num_busy_servers * time_since_last_event

    def _arrival(self):
        """Handles a customer arrival, with priority and server logic."""
        arrival_time = self.sim_clock
        service_time = self.service_times.popleft() if self.service_times else 0
        priority = self.priorities.popleft() if self.priorities else 'regular'
        
        # Schedule next arrival
        if self.interarrival_times:
            self.next_arrival_time = self.sim_clock + self.interarrival_times.popleft()
        else:
            self.next_arrival_time = float('inf')

        idle_server_idx = self._get_idle_server()
        if idle_server_idx != -1:
            # Server is available, serve immediately
            log = self._serve_customer(idle_server_idx, self.next_customer_id, arrival_time, service_time)
        else:
            # All servers busy, try to queue
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
        """Handles a customer departure and serves the next one if available."""
        departed_customer_id = self.servers[server_idx]['customer_id']
        self.customers_served += 1
        
        # Free up the server
        self.servers[server_idx]['status'] = 'idle'
        self.servers[server_idx]['customer_id'] = None
        self.servers[server_idx]['departure_time'] = float('inf')

        # Check queue for next customer
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
        """Assigns a customer to a server and logs their data."""
        self.servers[server_idx]['status'] = 'busy'
        self.servers[server_idx]['customer_id'] = cust_id
        self.servers[server_idx]['departure_time'] = self.sim_clock + service_time
        
        delay = self.sim_clock - arrival_time
        self.total_delay += delay
        if delay > 0: self.num_delayed += 1
        
        self.completed_customers_details.append({
            "id": cust_id, "arrival_time": arrival_time, "wait_delay": delay,
            "service_start_time": self.sim_clock, "service_time": service_time,
            "departure_time": self.servers[server_idx]['departure_time'],
            "server_id": server_idx + 1
        })
        return f"Arrival C{cust_id}, served by Server {server_idx + 1}."

    def step(self):
        """Executes the next event in the simulation."""
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
        """Returns a dictionary representing the current state of the simulation."""
        return {
            "clock": self.sim_clock,
            "servers": self.servers,
            "vip_queue": list(self.vip_queue),
            "regular_queue": list(self.regular_queue),
            "next_arrival": self.next_arrival_time,
            "next_departure": self._get_next_departure()[0],
            "num_delayed": self.num_delayed,
            "total_delay": self.total_delay,
            "area_Q_t": self.area_under_Q_t,
            "area_B_t": self.total_server_busy_time,
            "last_event_time": self.time_of_last_event
        }

    def calculate_report(self):
        """Calculates and returns the final performance measures and costs."""
        final_time = self.time_of_last_event
        avg_delay = self.total_delay / self.num_delayed if self.num_delayed > 0 else 0.0
        avg_num_in_queue = self.area_under_Q_t / final_time if final_time > 0 else 0.0
        avg_server_utilization = self.total_server_busy_time / (self.num_servers * final_time) if final_time > 0 else 0.0
        
        total_wait_cost = self.total_delay * self.cost_wait_per_unit_time
        total_server_cost = self.total_server_busy_time * self.cost_server_per_unit_time

        report = {
            "d(n)": avg_delay,
            "q(n)": avg_num_in_queue,
            "u(n)": avg_server_utilization,
            "Number of customers rejected": self.customers_rejected,
            "Total simulation time T(n)": final_time,
        }

        if self.cost_wait_per_unit_time > 0 or self.cost_server_per_unit_time > 0:
            report["Total waiting cost"] = total_wait_cost
            report["Total server operational cost"] = total_server_cost
            report["Total system cost"] = total_wait_cost + total_server_cost
        
        return report

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ultimate Queueing System Simulator")
        self.geometry("1300x850")
        
        self.COLOR_BG_DARK = "#89A8B2"
        self.COLOR_BG_MEDIUM = "#B3C8CF"
        self.COLOR_CONTENT_LIGHT = "#E5E1DA"
        self.COLOR_CONTENT_ULTRALIGHT = "#F1F0E8"
        self.COLOR_TEXT_DARK = "#2c3e50"
        self.COLOR_TEXT_LIGHT = "#F1F0E8"

        self.configure(bg=self.COLOR_BG_DARK)

        self.setup_styles()
        self.initial_params = {
            'interarrivals': [0.4, 1.2, 0.5, 1.7, 0.2, 1.6, 0.2, 1.4, 1.9],
            'services': [2.0, 0.7, 0.2, 1.1, 3.7, 0.6],
            'priorities': ['regular'] * 6,
            'num_servers': 1, 'capacity': float('inf'),
            'cost_wait': 0, 'cost_server': 0,
            'priority_enabled': False
        }
        self.simulator = QueueingSystemSimulator(self.initial_params)
        
        # --- Stability Fix: State Management ---
        self.is_running_all = False
        self.is_running_replications = False
        self.after_id = None # To store the ID of the next scheduled event
        
        self.imported_interarrivals = []
        self.imported_services = []

        self.plot_time, self.plot_q_t, self.plot_b_t = [0], [0], [0]
        
        self.ui_mode = tk.StringVar(value="Default")
        self.scientific_labels = {
            "d(n)": "d(n) - Avg Delay",
            "q(n)": "q(n) - Avg # in Queue",
            "u(n)": "u(n) - Utilization",
            "Number of customers rejected": "Rejected Customers",
            "Total simulation time T(n)": "T(n) - Total Time",
        }

        self.create_widgets()
        self._perform_rebuild() # Initial build

    def setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.style.configure('.', background=self.COLOR_BG_DARK, foreground=self.COLOR_TEXT_LIGHT, font=('Segoe UI', 10))
        self.style.configure('TFrame', background=self.COLOR_BG_DARK)
        self.style.configure('TLabel', background=self.COLOR_BG_DARK, foreground=self.COLOR_TEXT_LIGHT)
        
        self.style.configure('Medium.TFrame', background=self.COLOR_BG_MEDIUM)
        self.style.configure('Medium.TLabel', background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK)
        self.style.configure('Medium.TLabelframe', background=self.COLOR_BG_MEDIUM, bordercolor=self.COLOR_BG_DARK)
        self.style.configure('Medium.TLabelframe.Label', foreground=self.COLOR_TEXT_DARK, background=self.COLOR_BG_MEDIUM, font=('Segoe UI', 11, 'bold'))
        self.style.configure('Medium.TRadiobutton', background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK)
        self.style.configure('Medium.TCheckbutton', background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK)
        
        self.style.configure('TButton', background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK, font=('Segoe UI', 10, 'bold'), borderwidth=0)
        self.style.map('TButton', background=[('active', self.COLOR_BG_DARK)])
        self.style.configure('TNotebook', background=self.COLOR_BG_DARK, borderwidth=0)
        self.style.configure('TNotebook.Tab', background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK, padding=[10, 5], font=('Segoe UI', 10))
        self.style.map('TNotebook.Tab', background=[('selected', self.COLOR_BG_DARK)])
        self.style.configure('Treeview', rowheight=25, fieldbackground=self.COLOR_CONTENT_ULTRALIGHT, background=self.COLOR_CONTENT_ULTRALIGHT, foreground=self.COLOR_TEXT_DARK)
        self.style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), background=self.COLOR_BG_MEDIUM, foreground=self.COLOR_TEXT_DARK)
        self.style.configure('TEntry', fieldbackground=self.COLOR_CONTENT_ULTRALIGHT, foreground=self.COLOR_TEXT_DARK, insertcolor=self.COLOR_TEXT_DARK)

    def stop_all_tasks(self):
        """Stability Fix: Gracefully stops any running simulation loops."""
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        
        self.is_running_all = False
        self.is_running_replications = False

        if hasattr(self, 'run_all_button'):
            self.run_all_button.config(text="⏩ Run All")
        if hasattr(self, 'run_replications_button'):
            self.run_replications_button.config(state='normal')
        if hasattr(self, 'progress_bar'):
            self.progress_bar['value'] = 0

        self.set_controls_state_running('normal')

    def create_widgets(self):
        """Creates the main window structure that doesn't change."""
        self.create_menu()

        self.main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.left_panel_container = ttk.Frame(self.main_paned_window, width=400)
        self.main_paned_window.add(self.left_panel_container, weight=1)

        self.right_frame = ttk.Frame(self.main_paned_window)
        self.main_paned_window.add(self.right_frame, weight=3)

    def rebuild_ui(self):
        """Schedules the UI rebuild to avoid crashing from destroying active widgets."""
        self.stop_all_tasks()
        self.after(1, self._perform_rebuild)

    def _perform_rebuild(self):
        """The actual UI rebuilding logic."""
        for widget in self.left_panel_container.winfo_children():
            widget.destroy()
        for widget in self.right_frame.winfo_children():
            widget.destroy()

        ui_mode_frame = ttk.LabelFrame(self.left_panel_container, text="UI Mode", style='Medium.TLabelframe')
        ui_mode_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Radiobutton(ui_mode_frame, text="Default", variable=self.ui_mode, value="Default", command=self.rebuild_ui, style='Medium.TRadiobutton').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(ui_mode_frame, text="Scientific", variable=self.ui_mode, value="Scientific", command=self.rebuild_ui, style='Medium.TRadiobutton').pack(side=tk.LEFT, padx=5)

        canvas = tk.Canvas(self.left_panel_container, bg=self.COLOR_BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.left_panel_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas, style='TFrame')
        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.create_input_panel(self.scrollable_frame)
        self.create_control_panel(self.scrollable_frame)
        
        vis_frame = ttk.LabelFrame(self.right_frame, text="System Visualization", style='Medium.TLabelframe')
        vis_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.canvas = tk.Canvas(vis_frame, bg=self.COLOR_CONTENT_LIGHT, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # [FIX] Bind the drawing update to the canvas resize event
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        
        stats_notebook = ttk.Notebook(self.right_frame)
        stats_notebook.pack(fill=tk.BOTH, expand=True)
        self.create_tabs(stats_notebook)
        
        self.update_ui() # Initial draw

    def on_canvas_resize(self, event):
        """Redraw the canvas content when the canvas is resized."""
        self.update_ui()

    def create_menu(self):
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        help_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about_window)
        help_menu.add_command(label="Notations & Formulas", command=self.show_info_window)

    def show_about_window(self):
        about_window = tk.Toplevel(self)
        about_window.title("About This Program")
        about_window.geometry("500x350")
        about_window.configure(bg=self.COLOR_BG_MEDIUM)
        about_window.resizable(False, False)

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (about_window.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (about_window.winfo_height() // 2)
        about_window.geometry(f"+{x}+{y}")

        about_frame = ttk.Frame(about_window, padding="20", style='Medium.TFrame')
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(about_frame, text="Indomaret Queing System Simulator", font=('Segoe UI', 14, 'bold'), style='Medium.TLabel').pack(pady=(0, 20))
        
        info_frame = ttk.Frame(about_frame, style='Medium.TFrame')
        info_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(info_frame, text="Developers:", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').grid(row=0, column=0, sticky='nw', padx=5, pady=2)
        dev_frame = ttk.Frame(info_frame, style='Medium.TFrame')
        dev_frame.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        ttk.Label(dev_frame, text="- Benedict Michael Pepper", style='Medium.TLabel').pack(anchor='w')
        ttk.Label(dev_frame, text="- Yudhistira Nalendra Aryadhewa Az-zhafir", style='Medium.TLabel').pack(anchor='w')
        
        ttk.Label(info_frame, text="Institution:", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').grid(row=1, column=0, sticky='nw', pady=(10,0), padx=5)
        institution_label = ttk.Label(info_frame, text="Informatics Engineering Study Program 2023, Ma Chung University", style='Medium.TLabel', wraplength=320, justify=tk.LEFT)
        institution_label.grid(row=1, column=1, sticky='w', pady=(10,0), padx=5)
        
        ttk.Label(info_frame, text="Description:", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').grid(row=2, column=0, sticky='nw', pady=(10,0), padx=5)
        desc_label = ttk.Label(info_frame, text="This simulator is a discrete-event analysis tool for multi-server queueing systems, featuring priority queues, cost analysis, and statistical replication modes.", style='Medium.TLabel', wraplength=320, justify=tk.LEFT)
        desc_label.grid(row=2, column=1, sticky='w', pady=(10,0), padx=5)
        
        info_frame.columnconfigure(1, weight=1)

        ttk.Button(about_frame, text="Close", command=about_window.destroy).pack(side=tk.BOTTOM, pady=20)

    def show_info_window(self):
        info_window = tk.Toplevel(self)
        info_window.title("Notations & Formulas")
        info_window.geometry("600x550")
        info_window.configure(bg=self.COLOR_BG_MEDIUM)

        info_text_widget = scrolledtext.ScrolledText(info_window, wrap=tk.WORD, bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat', font=('Segoe UI', 10))
        info_text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info_text_widget.tag_configure("bold", font=('Segoe UI', 11, 'bold'))
        info_text_widget.tag_configure("header", font=('Segoe UI', 14, 'bold'), justify='center', spacing3=10)
        info_text_widget.tag_configure("mono", font=('Courier New', 10))

        info_text_widget.insert(tk.END, "Notations & Formulas\n", "header")

        info_text_widget.insert(tk.END, "Input Variables & Notations\n", "bold")
        notations = [
            ("tᵢ", "Time of arrival of the i-th customer (t₀ = 0)"),
            ("Aᵢ", "Interarrival time between (i-1)st and i-th arrivals (Aᵢ = tᵢ - tᵢ₋₁)"),
            ("Sᵢ", "Time that server actually spends serving i-th customer"),
            ("Dᵢ", "Delay in queue of i-th customer"),
            ("cᵢ", "Time that i-th customer completes service and departs (cᵢ = tᵢ + Dᵢ + Sᵢ)"),
            ("eᵢ", "Time of occurrence of i-th event of any type"),
            ("λ", "Arrival Rate (customers per unit time)"),
            ("μ", "Service Rate (customers per unit time, per server)")
        ]
        for symbol, desc in notations:
            info_text_widget.insert(tk.END, f"{symbol:<5}", "mono")
            info_text_widget.insert(tk.END, f": {desc}\n")
        
        info_text_widget.insert(tk.END, "\nPerformance Measure Formulas\n", "bold")
        formulas = [
            ("d(n) = (Σ Dᵢ) / n", "Average delay in queue for n customers"),
            ("q(n) = ∫Q(t)dt / T(n)", "Time-average number of customers in queue"),
            ("u(n) = ∫B(t)dt / T(n)", "Time-average server utilization"),
        ]
        for formula, desc in formulas:
            info_text_widget.insert(tk.END, f"{formula}\n", "mono")
            info_text_widget.insert(tk.END, f"    ({desc})\n\n")

        info_text_widget.configure(state='disabled')


    def create_input_panel(self, parent):
        self.input_frame = ttk.LabelFrame(parent, text="Simulation Parameters", style='Medium.TLabelframe')
        self.input_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.gen_frame = ttk.LabelFrame(self.input_frame, text="General Settings", style='Medium.TLabelframe')
        self.gen_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(self.gen_frame, text="Number of Servers (c):", style='Medium.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.num_servers_entry = ttk.Entry(self.gen_frame, width=10); self.num_servers_entry.grid(row=0, column=1, padx=5, pady=2); self.num_servers_entry.insert(0, "1")
        ttk.Label(self.gen_frame, text="Queue Capacity (K):", style='Medium.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.capacity_entry = ttk.Entry(self.gen_frame, width=10); self.capacity_entry.grid(row=1, column=1, padx=5, pady=2); self.capacity_entry.insert(0, "inf")
        
        self.priority_enabled_var = tk.BooleanVar(value=False)
        self.priority_check = ttk.Checkbutton(self.gen_frame, text="Enable Customer Priority", variable=self.priority_enabled_var, command=self.toggle_priority_visibility, style='Medium.TCheckbutton')
        self.priority_check.grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        self.cost_enabled_var = tk.BooleanVar(value=False)
        self.cost_check = ttk.Checkbutton(self.gen_frame, text="Enable Cost Analysis", variable=self.cost_enabled_var, command=self.toggle_cost_visibility, style='Medium.TCheckbutton')
        self.cost_check.grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        self.cost_frame = ttk.LabelFrame(self.input_frame, text="Cost Analysis (per time unit)", style='Medium.TLabelframe')
        ttk.Label(self.cost_frame, text="Waiting Cost:", style='Medium.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.cost_wait_entry = ttk.Entry(self.cost_frame, width=10); self.cost_wait_entry.grid(row=0, column=1, padx=5, pady=2); self.cost_wait_entry.insert(0, "0")
        ttk.Label(self.cost_frame, text="Server Cost:", style='Medium.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.cost_server_entry = ttk.Entry(self.cost_frame, width=10); self.cost_server_entry.grid(row=1, column=1, padx=5, pady=2); self.cost_server_entry.insert(0, "0")

        self.mode_frame = ttk.LabelFrame(self.input_frame, text="Data Input Mode", style='Medium.TLabelframe')
        self.mode_frame.pack(fill=tk.X, padx=5, pady=5, after=self.gen_frame)
        self.input_mode = tk.StringVar(value="Manual")
        ttk.Radiobutton(self.mode_frame, text="Manual", variable=self.input_mode, value="Manual", command=self.toggle_input_mode, style='Medium.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(self.mode_frame, text="Distribution", variable=self.input_mode, value="Distribution", command=self.toggle_input_mode, style='Medium.TRadiobutton').pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(self.mode_frame, text="From File", variable=self.input_mode, value="From File", command=self.toggle_input_mode, style='Medium.TRadiobutton').pack(side=tk.LEFT, padx=2)

        self.manual_frame = ttk.Frame(self.input_frame, style='Medium.TFrame')
        ttk.Label(self.manual_frame, text="Inter-arrival Times (Aᵢ):", style='Medium.TLabel').grid(row=0, column=0, sticky='w', padx=5)
        self.interarrival_text = tk.Text(self.manual_frame, height=3, bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat'); self.interarrival_text.grid(row=1, column=0, sticky='ew', padx=5)
        self.interarrival_text.insert(tk.END, ', '.join(map(str, self.initial_params['interarrivals'])))
        ttk.Label(self.manual_frame, text="Service Times (Sᵢ):", style='Medium.TLabel').grid(row=2, column=0, sticky='w', padx=5)
        self.service_text = tk.Text(self.manual_frame, height=3, bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat'); self.service_text.grid(row=3, column=0, sticky='ew', padx=5)
        self.service_text.insert(tk.END, ', '.join(map(str, self.initial_params['services'])))
        self.service_text.bind('<KeyRelease>', self._update_customer_count_display)
        
        self.manual_priority_label = ttk.Label(self.manual_frame, text="Priorities (vip/regular):", style='Medium.TLabel')
        self.manual_priority_label.grid(row=4, column=0, sticky='w', padx=5)
        self.priority_text = tk.Text(self.manual_frame, height=3, bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat'); self.priority_text.grid(row=5, column=0, sticky='ew', padx=5)
        self.priority_text.insert(tk.END, ', '.join(self.initial_params['priorities']))
        self.manual_frame.columnconfigure(0, weight=1)

        self.dist_frame = ttk.Frame(self.input_frame, style='Medium.TFrame')
        
        self.random_frame = ttk.Frame(self.input_frame, style='Medium.TFrame')
        self.random_frame.columnconfigure(1, weight=1)
        ttk.Button(self.random_frame, text="Import Arrival Times (CSV)", command=lambda: self.import_random_csv('interarrival')).grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        self.interarrival_file_label = ttk.Label(self.random_frame, text="No file selected", anchor='w', style='Medium.TLabel', justify=tk.LEFT)
        self.interarrival_file_label.grid(row=0, column=1, padx=5, pady=2, sticky='w')
        ttk.Button(self.random_frame, text="Import Service Times (CSV)", command=lambda: self.import_random_csv('service')).grid(row=1, column=0, padx=5, pady=2, sticky='ew')
        self.service_file_label = ttk.Label(self.random_frame, text="No file selected", anchor='w', style='Medium.TLabel', justify=tk.LEFT)
        self.service_file_label.grid(row=1, column=1, padx=5, pady=2, sticky='w')
        
        self.count_frame = ttk.Frame(self.input_frame, style='Medium.TFrame')
        ttk.Label(self.count_frame, text="Number of Customers (n):", style='Medium.TLabel').pack(side=tk.LEFT, padx=(0,5))
        self.num_customers_var = tk.StringVar()
        self.num_customers_entry = ttk.Entry(self.count_frame, textvariable=self.num_customers_var)
        self.num_customers_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.num_customers_var.set(str(len(self.initial_params['services'])))
        
        self.toggle_input_mode()
        self.toggle_cost_visibility()

    def toggle_cost_visibility(self):
        self.stop_all_tasks()
        is_enabled = self.cost_enabled_var.get()
        if is_enabled:
            self.cost_frame.pack(fill=tk.X, padx=5, pady=5, after=self.gen_frame)
        else:
            self.cost_frame.pack_forget()

    def toggle_priority_visibility(self):
        self.stop_all_tasks()
        is_enabled = self.priority_enabled_var.get()
        if hasattr(self, 'manual_priority_label'):
            if is_enabled:
                self.manual_priority_label.grid(row=4, column=0, sticky='w', padx=5)
                self.priority_text.grid(row=5, column=0, sticky='ew', padx=5)
            else:
                self.manual_priority_label.grid_remove()
                self.priority_text.grid_remove()
        if hasattr(self, 'dist_priority_frame'):
            if is_enabled: self.dist_priority_frame.grid(row=5, column=0, columnspan=2, sticky='w')
            else: self.dist_priority_frame.grid_remove()

    def toggle_input_mode(self):
        self.stop_all_tasks()
        mode = self.input_mode.get()
        
        # Hide all frames first
        self.manual_frame.pack_forget()
        self.dist_frame.pack_forget()
        self.random_frame.pack_forget()
        self.count_frame.pack_forget()

        mode_frame = self.mode_frame

        if mode == "Manual":
            self.manual_frame.pack(fill=tk.X, padx=5, pady=5, after=mode_frame)
            self.count_frame.pack(fill=tk.X, padx=5, pady=5, after=self.manual_frame)
            self.num_customers_entry.config(state='disabled')
            self._update_customer_count_display()
        elif mode == "Distribution":
            if not self.dist_frame.winfo_children():
                f = self.dist_frame
                ttk.Label(f, text="Arrival Dist. (Exponential)", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').grid(row=0, column=0, columnspan=2, sticky='w', padx=5, pady=(5,0))
                ttk.Label(f, text="Mean Interarrival Time (1/λ):", style='Medium.TLabel').grid(row=1, column=0, sticky='w', padx=5)
                self.arrival_mean = ttk.Entry(f); self.arrival_mean.grid(row=1, column=1, sticky='ew', padx=5, pady=2); self.arrival_mean.insert(0, "1.0")
                ttk.Label(f, text="Service Dist. (Normal)", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=(10,0))
                ttk.Label(f, text="Mean Service Time (1/μ):", style='Medium.TLabel').grid(row=3, column=0, sticky='w', padx=5)
                self.service_mean = ttk.Entry(f); self.service_mean.grid(row=3, column=1, sticky='ew', padx=5, pady=2); self.service_mean.insert(0, "0.8")
                ttk.Label(f, text="Std. Dev. (σ):", style='Medium.TLabel').grid(row=4, column=0, sticky='w', padx=5)
                self.service_stdev = ttk.Entry(f); self.service_stdev.grid(row=4, column=1, sticky='ew', padx=5, pady=2); self.service_stdev.insert(0, "0.2")
                self.dist_priority_frame = ttk.Frame(f, style='Medium.TFrame'); self.dist_priority_frame.grid(row=5, column=0, columnspan=2, sticky='w')
                ttk.Label(self.dist_priority_frame, text="Priority", font=('Segoe UI', 10, 'bold'), style='Medium.TLabel').pack(anchor='w', padx=5, pady=(10,0))
                ttk.Label(self.dist_priority_frame, text="% of VIP Customers:", style='Medium.TLabel').pack(side=tk.LEFT, padx=5)
                self.vip_percentage = ttk.Entry(self.dist_priority_frame); self.vip_percentage.pack(side=tk.LEFT, padx=5, pady=2); self.vip_percentage.insert(0, "10")
                f.columnconfigure(1, weight=1)
            self.dist_frame.pack(fill=tk.X, padx=5, pady=5, after=mode_frame)
            self.count_frame.pack(fill=tk.X, padx=5, pady=5, after=self.dist_frame)
            self.num_customers_entry.config(state='normal')
        elif mode == "From File":
            self.random_frame.pack(fill=tk.X, padx=5, pady=5, after=mode_frame)
            self.count_frame.pack(fill=tk.X, padx=5, pady=5, after=self.random_frame)
            self.num_customers_entry.config(state='disabled')
            self._update_customer_count_display()

        self.toggle_priority_visibility()

    def _update_customer_count_display(self, event=None):
        count = 0
        try:
            if self.input_mode.get() == "Manual":
                services_str = self.service_text.get(1.0, tk.END).strip()
                count = len([s for s in services_str.replace(' ', '').split(',') if s]) if services_str else 0
            elif self.input_mode.get() == "From File":
                count = len(self.imported_services)
            self.num_customers_var.set(str(count))
        except (ValueError, tk.TclError):
            self.num_customers_var.set("Error")

    def create_control_panel(self, parent):
        self.control_frame = ttk.LabelFrame(parent, text="Execution & Control", style='Medium.TLabelframe')
        self.control_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.reset_button = ttk.Button(self.control_frame, text="Load & Reset", command=self.reset_simulation)
        self.reset_button.grid(row=0, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        self.step_button = ttk.Button(self.control_frame, text="▶ Next Step", command=self.run_next_event)
        self.step_button.grid(row=1, column=0, sticky='ew', padx=5, pady=2)
        self.run_all_button = ttk.Button(self.control_frame, text="⏩ Run All", command=self.toggle_run_all)
        self.run_all_button.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        ttk.Label(self.control_frame, text="Speed (ms delay):", style='Medium.TLabel').grid(row=2, column=0, sticky='w', padx=5)
        self.speed_scale = ttk.Scale(self.control_frame, from_=1000, to=50, orient=tk.HORIZONTAL); self.speed_scale.set(500)
        self.speed_scale.grid(row=2, column=1, sticky='ew', padx=5)

        ttk.Label(self.control_frame, text="Number of Replications:", style='Medium.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=(10,0))
        self.replications_entry = ttk.Entry(self.control_frame); self.replications_entry.grid(row=3, column=1, sticky='ew', padx=5, pady=(10,0)); self.replications_entry.insert(0, "100")
        self.run_replications_button = ttk.Button(self.control_frame, text="Run Replications", command=self.run_replications)
        self.run_replications_button.grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=2)
        self.progress_bar = ttk.Progressbar(self.control_frame, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=5, column=0, columnspan=2, sticky='ew', padx=5, pady=2)

        self.import_csv_button = ttk.Button(self.control_frame, text="Import Manual Data (CSV)", command=self.import_from_csv)
        self.import_csv_button.grid(row=6, column=0, sticky='ew', padx=5, pady=(10,2))
        self.export_button = ttk.Button(self.control_frame, text="Export Results (CSV)", command=self.export_to_csv, state='disabled')
        self.export_button.grid(row=6, column=1, sticky='ew', padx=5, pady=(10,2))
        self.save_graph_button = ttk.Button(self.control_frame, text="Save Graph (PNG)", command=self.save_graph_to_png)
        self.save_graph_button.grid(row=7, column=0, columnspan=2, sticky='ew', padx=5, pady=2)

    def create_tabs(self, notebook):
        graph_tab = ttk.Frame(notebook); notebook.add(graph_tab, text='Real-time Graph')
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor=self.COLOR_CONTENT_LIGHT)
        self.ax1 = self.fig.add_subplot(211); self.ax2 = self.fig.add_subplot(212)
        self.graph_canvas = FigureCanvasTkAgg(self.fig, master=graph_tab)
        self.graph_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        stats_tab = ttk.Frame(notebook); notebook.add(stats_tab, text='Customer Statistics')
        cols = ('id', 'arrival_t', 'delay_D', 'service_start_t', 'service_S', 'departure_c', 'server_id')
        col_names = ('C ID', 'tᵢ', 'Dᵢ', 'Start Time', 'Sᵢ', 'cᵢ', 'Server')
        self.stats_tree = ttk.Treeview(stats_tab, columns=cols, show='headings')
        for col, name in zip(cols, col_names): 
            self.stats_tree.heading(col, text=name)
            self.stats_tree.column(col, width=80, anchor='center')
        self.stats_tree.pack(fill=tk.BOTH, expand=True)

        log_tab = ttk.Frame(notebook); notebook.add(log_tab, text='Event Log')
        self.log_text = scrolledtext.ScrolledText(log_tab, wrap=tk.WORD, state='disabled', bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat')
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.report_tab = ttk.Frame(notebook); notebook.add(self.report_tab, text='Final Report')
        self.report_text = scrolledtext.ScrolledText(self.report_tab, wrap=tk.WORD, state='disabled', bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat')
        self.report_text.pack(fill=tk.BOTH, expand=True)

        self.replication_tab = ttk.Frame(notebook); notebook.add(self.replication_tab, text='Replication Report')
        self.replication_text = scrolledtext.ScrolledText(self.replication_tab, wrap=tk.WORD, state='disabled', bg=self.COLOR_CONTENT_ULTRALIGHT, fg=self.COLOR_TEXT_DARK, relief='flat')
        self.replication_text.pack(fill=tk.BOTH, expand=True)

    def update_plots(self):
        state = self.simulator.get_state()
        if self.simulator.sim_clock > self.plot_time[-1]:
             self.plot_time.append(self.simulator.sim_clock)
             self.plot_q_t.append(len(state['vip_queue']) + len(state['regular_queue']))
             self.plot_b_t.append(sum(1 for s in state['servers'] if s['status'] == 'busy'))

        self.ax1.clear(); self.ax1.step(self.plot_time, self.plot_q_t, where='post', color='#e67e22', label='Q(t) - Number in Queue')
        self.ax1.set_title("Number of Customers in Queue", color=self.COLOR_TEXT_DARK); self.ax1.set_ylabel("Customers", color=self.COLOR_TEXT_DARK); self.ax1.tick_params(colors=self.COLOR_TEXT_DARK); self.ax1.legend(loc='upper right')

        self.ax2.clear(); self.ax2.step(self.plot_time, self.plot_b_t, where='post', color='#27ae60', label='B(t) - Busy Servers')
        self.ax2.set_title("Number of Busy Servers", color=self.COLOR_TEXT_DARK); self.ax2.set_xlabel("Simulation Time", color=self.COLOR_TEXT_DARK); self.ax2.set_ylabel("Servers", color=self.COLOR_TEXT_DARK); self.ax2.tick_params(colors=self.COLOR_TEXT_DARK); self.ax2.legend(loc='upper right')
        
        self.fig.tight_layout(); self.graph_canvas.draw()

    def draw_default_canvas(self, state):
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 50 or ch < 50: return
        
        num_servers = len(state['servers'])
        server_w, server_h, server_gap = 80, 50, 10
        total_server_h = num_servers * server_h + (num_servers - 1) * server_gap
        start_y = (ch - total_server_h) / 2
        for i, server in enumerate(state['servers']):
            server_x = cw * 0.7; server_y = start_y + i * (server_h + server_gap)
            color = "#27ae60" if server['status'] == 'busy' else "#95a5a6"
            self.canvas.create_rectangle(server_x, server_y, server_x + server_w, server_y + server_h, fill=color, outline="")
            self.canvas.create_text(server_x + server_w/2, server_y + server_h/2, text=f"S{i+1}", fill="white", font=('Segoe UI', 10, 'bold'))
            if server['customer_id']: self.canvas.create_text(server_x + server_w/2, server_y + server_h + 10, text=f"C{server['customer_id']}", fill=self.COLOR_TEXT_DARK, font=('Segoe UI', 9, 'italic'))

        cust_w, cust_h, spacing = 40, 40, 8
        if self.simulator.priority_enabled:
            self.canvas.create_text(cw * 0.4, ch*0.25 - 30, text="VIP QUEUE", fill="#c0392b", font=('Segoe UI', 10, 'bold'))
            for i, cust_id in enumerate(state['vip_queue']):
                cust_x = cw * 0.4 - (i * (cust_w + spacing)); self.canvas.create_rectangle(cust_x, ch*0.25 - cust_h/2, cust_x - cust_w, ch*0.25 + cust_h/2, fill="#c0392b", outline=""); self.canvas.create_text(cust_x - cust_w/2, ch*0.25, text=f"C{cust_id}", fill="white", font=('Segoe UI', 9, 'bold'))
            self.canvas.create_text(cw * 0.4, ch*0.75 - 30, text="REGULAR QUEUE", fill="#e67e22", font=('Segoe UI', 10, 'bold'))
            for i, cust_id in enumerate(state['regular_queue']):
                cust_x = cw * 0.4 - (i * (cust_w + spacing)); self.canvas.create_rectangle(cust_x, ch*0.75 - cust_h/2, cust_x - cust_w, ch*0.75 + cust_h/2, fill="#e67e22", outline=""); self.canvas.create_text(cust_x - cust_w/2, ch*0.75, text=f"C{cust_id}", fill="white", font=('Segoe UI', 9, 'bold'))
        else:
            self.canvas.create_text(cw * 0.4, ch/2 - 30, text="QUEUE", fill=self.COLOR_TEXT_DARK, font=('Segoe UI', 10, 'bold'))
            for i, cust_id in enumerate(state['regular_queue']):
                cust_x = cw * 0.4 - (i * (cust_w + spacing)); self.canvas.create_rectangle(cust_x, ch/2 - cust_h/2, cust_x - cust_w, ch/2 + cust_h/2, fill="#B3C8CF", outline=""); self.canvas.create_text(cust_x - cust_w/2, ch/2, text=f"C{cust_id}", fill=self.COLOR_TEXT_DARK, font=('Segoe UI', 9, 'bold'))

    def draw_scientific_canvas(self, state):
        self.canvas.delete("all")
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 50 or ch < 50: return

        # --- Draw main containers ---
        self.canvas.create_rectangle(20, 20, cw * 0.5, ch - 20, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.25, 35, text="System State", font=('Segoe UI', 12, 'bold'), fill=self.COLOR_TEXT_DARK)
        
        self.canvas.create_rectangle(cw * 0.5 + 20, 20, cw - 20, ch * 0.5 - 10, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_rectangle(cw * 0.5 + 20, ch * 0.5 + 10, cw - 20, ch - 20, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.75, 35, text="Computer Representation", font=('Segoe UI', 12, 'bold'), fill=self.COLOR_TEXT_DARK)

        # --- System State Details ---
        box_w, box_h = 80, 50
        # Server Status
        # [FIX] Correctly count the number of busy servers
        server_status = sum(1 for s in state['servers'] if s['status'] == 'busy')
        self.canvas.create_rectangle(40, 60, 40 + box_w, 60 + box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(40 + box_w/2, 60 + box_h + 10, text="Server Status B(t)", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(40 + box_w/2, 60 + box_h/2, text=str(server_status), font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        # Number in Queue
        num_in_queue = len(state['vip_queue']) + len(state['regular_queue'])
        self.canvas.create_rectangle(140, 60, 140 + box_w, 60 + box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(140 + box_w/2, 60 + box_h + 10, text="Number in Queue Q(t)", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(140 + box_w/2, 60 + box_h/2, text=str(num_in_queue), font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        # Times of Arrival (Queue)
        self.canvas.create_rectangle(240, 60, 240 + box_w, 60 + box_h * 2, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(240 + box_w/2, 60 + box_h*2 + 10, text="Times of Arrival", fill=self.COLOR_TEXT_DARK)
        queue_content = state['vip_queue'] + state['regular_queue']
        for i, cust_id in enumerate(queue_content[:5]): # Display up to 5
            arrival_time = self.simulator.customer_data.get(cust_id, {}).get('arrival_time', '')
            if isinstance(arrival_time, (int, float)):
                self.canvas.create_text(240 + box_w/2, 75 + i*20, text=f"{arrival_time:.2f}", fill=self.COLOR_TEXT_DARK)

        # --- Computer Representation Details ---
        # Clock
        self.canvas.create_rectangle(cw * 0.5 + 40, 60, cw * 0.5 + 40 + box_w, 60 + box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.5 + 40 + box_w/2, 60 + box_h + 10, text="Clock", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.5 + 40 + box_w/2, 60 + box_h/2, text=f"{state['clock']:.2f}", font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        
        # Event List
        self.canvas.create_rectangle(cw * 0.5 + 140, 60, cw * 0.5 + 140 + box_w, 60 + box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.5 + 140 + box_w/2, 60 + box_h + 10, text="Event List", fill=self.COLOR_TEXT_DARK)
        
        # [FIX] Safely format event times, handling 'inf'
        next_arrival_str = f"{state['next_arrival']:.2f}" if state['next_arrival'] != float('inf') else "∞"
        next_departure_str = f"{state['next_departure']:.2f}" if state['next_departure'] != float('inf') else "∞"
        
        self.canvas.create_text(cw * 0.5 + 140 + box_w/2, 75, text=f"A: {next_arrival_str}", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw * 0.5 + 140 + box_w/2, 95, text=f"D: {next_departure_str}", fill=self.COLOR_TEXT_DARK)
        
        # Statistical Counters
        stat_y = ch * 0.5 + 30
        self.canvas.create_text(cw * 0.75, stat_y, text="Statistical Counters", font=('Segoe UI', 12, 'bold'), fill=self.COLOR_TEXT_DARK)
        stat_y += 30
        # Num Delayed
        self.canvas.create_rectangle(cw*0.5+30, stat_y, cw*0.5+30+box_w, stat_y+box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+30+box_w/2, stat_y+box_h+10, text="Num Delayed", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+30+box_w/2, stat_y+box_h/2, text=str(state['num_delayed']), font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        # Total Delay
        self.canvas.create_rectangle(cw*0.5+130, stat_y, cw*0.5+130+box_w, stat_y+box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+130+box_w/2, stat_y+box_h+10, text="Total Delay", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+130+box_w/2, stat_y+box_h/2, text=f"{state['total_delay']:.2f}", font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        # Area under Q(t)
        self.canvas.create_rectangle(cw*0.5+230, stat_y, cw*0.5+230+box_w, stat_y+box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+230+box_w/2, stat_y+box_h+10, text="Area under Q(t)", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+230+box_w/2, stat_y+box_h/2, text=f"{state['area_Q_t']:.2f}", font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)
        # Area under B(t)
        self.canvas.create_rectangle(cw*0.5+330, stat_y, cw*0.5+330+box_w, stat_y+box_h, outline=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+330+box_w/2, stat_y+box_h+10, text="Area under B(t)", fill=self.COLOR_TEXT_DARK)
        self.canvas.create_text(cw*0.5+330+box_w/2, stat_y+box_h/2, text=f"{state['area_B_t']:.2f}", font=('Segoe UI', 14, 'bold'), fill=self.COLOR_TEXT_DARK)

    def update_ui(self):
        if self.ui_mode.get() == "Default":
            self.draw_default_canvas(self.simulator.get_state())
        else:
            self.draw_scientific_canvas(self.simulator.get_state())

    def log_event(self, msg): self.log_text.configure(state='normal'); self.log_text.insert(tk.END, msg + "\n"); self.log_text.see(tk.END); self.log_text.configure(state='disabled')

    def run_next_event(self):
        self.stop_all_tasks() # Ensure no loops are running
        prev_num_completed = len(self.simulator.completed_customers_details)
        state, is_finished, event_log = self.simulator.step()
        if state is None:
            self.log_event(f"--- SIMULATION ALREADY FINISHED ---")
            self.show_report()
            return

        self.log_event(f"Clock {self.simulator.sim_clock:.2f}: {event_log}")
        self.update_ui()
        self.update_plots()

        if len(self.simulator.completed_customers_details) > prev_num_completed:
            d = self.simulator.completed_customers_details[-1]
            v = (d['id'], f"{d['arrival_time']:.2f}", f"{d['wait_delay']:.2f}", f"{d['service_start_time']:.2f}", f"{d['service_time']:.2f}", f"{d['departure_time']:.2f}", d['server_id'])
            self.stats_tree.insert('', tk.END, values=v)
        
        if is_finished:
            self.log_event("--- SIMULATION FINISHED ---")
            self.show_report()
            self.set_controls_state_finished()

    def toggle_run_all(self):
        if self.is_running_all:
            self.stop_all_tasks()
        else:
            self.is_running_all = True
            self.run_all_button.config(text="⏸️ Pause")
            self.set_controls_state_running('disabled', run_all_btn=False)
            self.run_all_loop()

    def run_all_loop(self):
        if not self.is_running_all: return
        
        prev_num_completed = len(self.simulator.completed_customers_details)
        state, is_finished, event_log = self.simulator.step()

        if state is None or is_finished:
            self.log_event("--- SIMULATION FINISHED ---")
            self.show_report()
            self.set_controls_state_finished()
            self.stop_all_tasks()
            return

        self.log_event(f"Clock {self.simulator.sim_clock:.2f}: {event_log}")
        self.update_ui()
        self.update_plots()

        if len(self.simulator.completed_customers_details) > prev_num_completed:
            d = self.simulator.completed_customers_details[-1]
            v = (d['id'], f"{d['arrival_time']:.2f}", f"{d['wait_delay']:.2f}", f"{d['service_start_time']:.2f}", f"{d['service_time']:.2f}", f"{d['departure_time']:.2f}", d['server_id'])
            self.stats_tree.insert('', tk.END, values=v)
        
        self.after_id = self.after(int(self.speed_scale.get()), self.run_all_loop)
            
    def get_params_from_ui(self):
        params = {}
        try:
            params['num_servers'] = int(self.num_servers_entry.get())
            capacity_str = self.capacity_entry.get().strip()
            params['capacity'] = float(capacity_str) if capacity_str.lower() != 'inf' else float('inf')
            params['priority_enabled'] = self.priority_enabled_var.get()
            
            if self.cost_enabled_var.get():
                params['cost_wait'] = float(self.cost_wait_entry.get())
                params['cost_server'] = float(self.cost_server_entry.get())
            else:
                params['cost_wait'] = 0.0
                params['cost_server'] = 0.0
            
            mode = self.input_mode.get()
            if mode == "Manual":
                self._update_customer_count_display()
                params['interarrivals'] = [float(x) for x in self.interarrival_text.get(1.0, tk.END).strip().replace(' ', '').split(',') if x]
                params['services'] = [float(x) for x in self.service_text.get(1.0, tk.END).strip().replace(' ', '').split(',') if x]
                if params['priority_enabled']:
                    priorities_str = [p.strip().lower() for p in self.priority_text.get(1.0, tk.END).strip().split(',') if p]
                    if len(priorities_str) != len(params['services']): raise ValueError("Number of priorities must match number of services.")
                    params['priorities'] = priorities_str
                else:
                    params['priorities'] = ['regular'] * len(params['services'])
            elif mode == "From File":
                if not self.imported_interarrivals or not self.imported_services: raise ValueError("Random number files have not been imported.")
                params['interarrivals'] = self.imported_interarrivals
                params['services'] = self.imported_services
                if params['priority_enabled']:
                    messagebox.showwarning("Priority Input", "For 'From File' mode, please ensure the 'Priorities' field under 'Manual' mode is filled correctly, as it will be used.")
                    priorities_str = [p.strip().lower() for p in self.priority_text.get(1.0, tk.END).strip().split(',') if p]
                    if len(priorities_str) != len(params['services']): raise ValueError("Number of priorities must match number of services from the imported file.")
                    params['priorities'] = priorities_str
                else:
                    params['priorities'] = ['regular'] * len(params['services'])
            
            else: # Distribution mode
                num_cust = int(self.num_customers_var.get())
                if num_cust <= 0: raise ValueError("Number of customers for distribution must be positive.")
                params['interarrivals'] = [random.expovariate(1.0/float(self.arrival_mean.get())) for _ in range(num_cust)]
                params['services'] = [max(0, random.normalvariate(float(self.service_mean.get()), float(self.service_stdev.get()))) for _ in range(num_cust)]
                if params['priority_enabled']:
                    params['priorities'] = ['vip' if random.random() < float(self.vip_percentage.get())/100 else 'regular' for _ in range(num_cust)]
                else:
                    params['priorities'] = ['regular'] * num_cust
            
            if not params['services']:
                raise ValueError("Service times cannot be empty. Please provide service times to define the number of customers.")

            return params
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Input Error", f"Invalid data format. Please check all inputs.\n\nError: {e}")
            return None

    def reset_simulation(self):
        self.stop_all_tasks()
        params = self.get_params_from_ui()
        if params is None: return
        self.simulator.reset(params)
        self.log_text.configure(state='normal'); self.log_text.delete(1.0, tk.END); self.log_text.configure(state='disabled')
        self.report_text.configure(state='normal'); self.report_text.delete(1.0, tk.END); self.report_text.configure(state='disabled')
        for i in self.stats_tree.get_children(): self.stats_tree.delete(i)
        self.plot_time, self.plot_q_t, self.plot_b_t = [0], [0], [0]
        self.log_event("Simulation reset with new data.")
        self.update_plots()
        self.update_ui()
        self.export_button.config(state='disabled')

    def run_replications(self):
        self.stop_all_tasks()
        try:
            self.num_replications_total = int(self.replications_entry.get())
            if self.num_replications_total <= 1: raise ValueError("Number of replications must be > 1.")
        except (ValueError, tk.TclError) as e:
            messagebox.showerror("Input Error", f"Invalid number of replications: {e}"); return

        self.base_params = self.get_params_from_ui()
        if self.base_params is None: return

        self.is_running_replications = True
        self.set_controls_state_running('disabled')
        self.progress_bar['maximum'] = self.num_replications_total
        self.progress_bar['value'] = 0
        
        self.replication_results = collections.defaultdict(list)
        self.replication_count = 0
        
        self._run_replication_step()

    def _run_replication_step(self):
        if not self.is_running_replications: return

        if self.replication_count < self.num_replications_total:
            current_params = self.get_params_from_ui() if self.input_mode.get() == "Distribution" else self.base_params
            if current_params is None:
                self.stop_all_tasks()
                return
            
            self.simulator.reset(current_params)
            while not (self.simulator.customers_served >= self.simulator.max_customers and self.simulator.max_customers > 0):
                _, is_finished, _ = self.simulator.step()
                if is_finished: break
            
            report = self.simulator.calculate_report()
            for key, value in report.items(): self.replication_results[key].append(value)
            
            self.replication_count += 1
            self.progress_bar['value'] = self.replication_count
            
            self.after_id = self.after(1, self._run_replication_step) # Schedule next step
        else:
            self.finish_replications()

    def finish_replications(self):
        final_report = "--- REPLICATION REPORT ---\n"
        final_report += f"Number of Replications: {self.num_replications_total}\n\n"
        final_report += f"{'Metric':<40} {'Mean':>15} {'Std. Dev.':>15} {'95% C.I. Half-Width':>20}\n"
        final_report += "-"*95 + "\n"

        for key, values in self.replication_results.items():
            display_key = self.scientific_labels.get(key, key)
            mean = np.mean(values); stdev = np.std(values, ddof=1) if len(values) > 1 else 0
            half_width = 1.96 * (stdev / math.sqrt(len(values))) if len(values) > 1 else 0
            final_report += f"{display_key:<40} {mean:>15.4f} {stdev:>15.4f} {half_width:>20.4f}\n"

        self.replication_text.configure(state='normal'); self.replication_text.delete(1.0, tk.END)
        self.replication_text.insert(tk.END, final_report); self.replication_text.configure(state='disabled')
        self.replication_tab.master.select(self.replication_tab)
        
        self.stop_all_tasks()

    def set_controls_state_running(self, state, run_all_btn=True):
        if hasattr(self, 'run_all_button') and run_all_btn:
            self.run_all_button.config(state=state)
        if hasattr(self, 'run_replications_button'):
            self.run_replications_button.config(state=state)

    def set_controls_state_finished(self):
        self.run_all_button.config(state='disabled')
        self.run_replications_button.config(state='disabled')
        self.export_button.config(state='normal')

    def show_report(self):
        report = self.simulator.calculate_report()
        report_str = "--- FINAL SIMULATION REPORT ---\n\n"
        for key, value in report.items():
            display_key = self.scientific_labels.get(key, key)
            report_str += f"{display_key:<40}: {value:.4f}\n"
        self.report_text.configure(state='normal'); self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report_str); self.report_text.configure(state='disabled')
        self.report_tab.master.select(self.report_tab)

    def export_to_csv(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not filepath: return
        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Final Simulation Report']); report = self.simulator.calculate_report()
                for key, value in report.items(): 
                    display_key = self.scientific_labels.get(key, key)
                    writer.writerow([display_key, f"{value:.4f}"])
                writer.writerow([])
                writer.writerow(['Detailed Customer Statistics'])
                headers = list(self.simulator.completed_customers_details[0].keys()) if self.simulator.completed_customers_details else []
                writer.writerow([h.replace('_', ' ').title() for h in headers])
                for detail in self.simulator.completed_customers_details:
                    writer.writerow([f"{v:.2f}" if isinstance(v, float) else v for v in detail.values()])
            messagebox.showinfo("Success", f"Data successfully exported to {filepath}")
        except Exception as e: messagebox.showerror("Export Error", f"Failed to save file.\n\nError: {e}")

    def import_from_csv(self):
        self.stop_all_tasks()
        filepath = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not filepath: return
        try:
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                interarrivals = next(reader)
                services = next(reader)
                
                try:
                    priorities = next(reader)
                    self.priority_enabled_var.set(True)
                except StopIteration:
                    num_services = len([s for s in services if s.strip()])
                    priorities = ['regular'] * num_services
                    self.priority_enabled_var.set(False)

                self.interarrival_text.delete(1.0, tk.END); self.interarrival_text.insert(tk.END, ','.join(interarrivals))
                self.service_text.delete(1.0, tk.END); self.service_text.insert(tk.END, ','.join(services))
                self.priority_text.delete(1.0, tk.END); self.priority_text.insert(tk.END, ','.join(priorities))
                
                self.input_mode.set("Manual")
                self.toggle_input_mode()
                self.toggle_priority_visibility()
                messagebox.showinfo("Success", "Data imported successfully. Press 'Load & Reset' to start.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read file. Ensure format is correct (2 or 3 comma-separated rows).\n\nError: {e}")

    def import_random_csv(self, file_type):
        self.stop_all_tasks()
        filepath = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not filepath: return
        try:
            with open(filepath, 'r') as f:
                reader = csv.reader(f); numbers = [float(row[0]) for row in reader]
            
            filename = filepath.split('/')[-1]
            if file_type == 'interarrival':
                self.imported_interarrivals = numbers
                self.interarrival_file_label.config(text=f"Loaded: {len(numbers)} from {filename}")
            elif file_type == 'service':
                self.imported_services = numbers
                self.service_file_label.config(text=f"Loaded: {len(numbers)} from {filename}")
                self._update_customer_count_display()
            
            messagebox.showinfo("Success", f"Successfully imported {len(numbers)} random numbers.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read file. Ensure the CSV contains only one column of numbers.\n\nError: {e}")

    def save_graph_to_png(self):
        self.stop_all_tasks()
        filepath = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if not filepath: return
        try:
            self.fig.savefig(filepath, dpi=300, bbox_inches='tight', facecolor=self.fig.get_facecolor())
            messagebox.showinfo("Success", f"Graph successfully saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Save Graph Error", f"Failed to save file.\n\nError: {e}")

if __name__ == "__main__":
    app = App()
    app.mainloop()
