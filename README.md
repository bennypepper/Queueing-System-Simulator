# Queueing System Simulator 

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?logo=python&logoColor=white) ![Tkinter](https://img.shields.io/badge/GUI-Tkinter-lightgrey.svg) ![Matplotlib](https://img.shields.io/badge/Data_Viz-Matplotlib-orange.svg) ![NumPy](https://img.shields.io/badge/Math-NumPy-013243.svg?logo=numpy&logoColor=white)

An interactive, GUI-based Discrete Event Simulation (DES) tool designed to model, analyze, and optimize multi-server queueing systems. Built as a virtual laboratory for a Simulation Modelling course at Ma Chung University, this program allows users to run complex "what-if" scenarios to find the optimal balance between operational costs and customer waiting times.

## 📌 Project Overview
Testing operational changes in the real world (like hiring more staff or altering service flows) is expensive and risky. This simulator uses the Discrete Event Simulation (DES) method to jump chronologically between key events (customer arrivals and departures), providing a highly efficient, industry-standard way to evaluate queue performance. It handles various models (M/M/c), priority balking, and detailed statistical reporting.

## 🛠️ Tech Stack & Libraries
* **Language:** Python
* **GUI Framework:** Tkinter
* **Data Visualization:** Matplotlib (Real-time graphing)
* **Data Processing:** NumPy, SciPy, Collections, CSV

## 🚀 Key Features
* **Multi-Server & Priority Queues:** Simulate any number of parallel servers and toggle VIP customer priorities, separating standard FIFO logic into distinct VIP vs. Regular queues.
* **Cost Analysis:** Input abstract "Waiting Costs" and "Server Costs" to mathematically calculate the optimal trade-off between customer satisfaction and business overhead.
* **Flexible Data Input:** Supports manual entry, CSV imports, or automated randomized distributions (Exponential for arrivals, Lognormal for service times).
* **Real-Time Visualization:** Watch the system dynamically update with visual representations of idle/busy servers, queue lengths, and live line charts for Q(t) and B(t).
* **Statistical Replications:** Run the simulation hundreds of times automatically to generate a "Replication Report" featuring 95% Confidence Intervals (C.I. Half-Width) for rock-solid, data-driven decision making.
* **Comprehensive Exporting:** Export event logs, customer statistics, and final system reports to `.csv`, or save the real-time plots as `.png` images.

## 💻 How to Run Locally

You can run this project either as a local Desktop App or a Web Dashboard. Both share the exact same underlying mathematical engine.

**1. Clone the repository:**
```bash
git clone https://github.com/bennypepper/Queueing-System-Simulator.git
cd Queueing-System-Simulator
```

**2. Install dependencies:**
```bash
pip install numpy scipy matplotlib streamlit
```

**3a. Launch the Desktop Simulator (Tkinter):**
```bash
python simulator.py
```
*(Ensure your Python installation includes Tkinter, which is typically bundled by default on Windows).*

**3b. Launch the Web Dashboard (Streamlit):**
```bash
streamlit run app.py
```

## 📖 Technical Guidebook

A comprehensive, mathematically detailed manual explaining the Discrete Event Simulation mechanisms, formulas, and real-world business applications of this software is provided.

👉 **[Read the Full Guidebook (`guidebook.pdf`)](guidebook.pdf)**

## 📊 Using the Simulator (Example Scenario)
To analyze whether adding a second barista to a cafe is cost-effective:
1. Enter your arrival and service distributions on the left panel.
2. Input your estimated *Waiting Cost* and *Server Cost*.
3. Set "Number of Replications" to 100 and click **Run Replications**.
4. Check the Replication Report tab for the Total System Cost and its 95% Confidence Interval.
5. Change the "Number of Servers" from 1 to 2, rerun the replications, and compare the total costs to make your final business decision.

## 👥 Authors
* Benedict Michael Pepper
* Yudhistira Nalendra Aryadhewa Az-zhafir
* *Informatics Engineering, Ma Chung University*
