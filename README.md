# PyPESOL -- README

### Python Peer-to-Peer Energy Sharing Optimization Library

First public release README file (v0.2, May 2025) -- last update March 2026.

PyPESOL is an optimization framework for modeling and solving **peer-to-peer energy sharing problems** using mathematical programming techniques.

The library is built on:

* **Pyomo** for mathematical modeling
* **GLPK** and **CBC** for linear and mixed-integer optimization
* Scientific Python stack (NumPy, SciPy, Pandas)
* Optional forecasting support via **Prophet**

Here is a small guide to start experimenting with PyPESOL.

> **Disclaimer** The code is highly experimental and has only been tested on Ubuntu and MacOS. *Use with care!*

## Re-use & cite ###

If this software is used in research work, please cite the following publication:
- *Duvignau, Romaric, Vincenzo Gulisano, and Marina Papatriantafilou. "PyPESOL: The Python P2P Energy Sharing Optimization Library." Proceedings of the Sixteenth ACM International Conference on Future Energy Systems (ACM e-energy '25). 2025. 1014-1015.* https://dl.acm.org/doi/10.1145/3679240.3734691


The library implements energy and optimization models as well as matching methods from the following publications:
- Duvignau, R., Gulisano, V., Papatriantafilou, M., & Klasing, R. (2024). Geographical Peer Matching for P2P Energy Sharing. IEEE Access.
- Duvignau, R., & Klasing, R. (2023). Greediness is not always a vice: Efficient Discovery Algorithms for Assignment Problems. Procedia Computer Science, 223, 43-52.
- Duvignau, R., Gulisano, V., & Papatriantafilou, M. (2023, January). Cost-optimization for win-win P2P energy systems. In 2023 IEEE Power & Energy Society Innovative Smart Grid Technologies Conference (ISGT) (pp. 1-5). IEEE.
- Duvignau, R., Gulisano, V., & Papatriantafilou, M. (2022, April). Efficient and scalable geographical peer matching for p2p energy sharing communities. In Proceedings of the 37th ACM/SIGAPP Symposium on Applied Computing (pp. 187-190).
- Duvignau, R., Heinisch, V., Göransson, L., Gulisano, V., & Papatriantafilou, M. (2021). Benefits of small-size communities for continuous cost-optimization in peer-to-peer energy sharing. Applied Energy, 301, 117402.
- Duvignau, R., Heinisch, V., Göransson, L., Gulisano, V., & Papatriantafilou, M. (2020, June). Small-scale communities are sufficient for cost-and data-efficient peer-to-peer energy sharing. In Proceedings of the Eleventh ACM International Conference on Future Energy Systems (pp. 35-46).

---

# Installation

PyPESOL can be installed in two ways:

* **Option 1: Python virtual environment (recommended for development)**
* **Option 2: Docker (recommended for easy deployment)**

---

# Option 1 — Installation via Python Virtual Environment

### 1. Install required system solvers

#### Ubuntu

```bash
sudo apt install glpk-utils coinor-cbc
```

#### MacOS

```
brew install cbc glpk
```

These provide:

* `glpsol` (GLPK solver)
* `cbc` (COIN-OR Branch and Cut solver)

### 2. Create and activate a virtual environment

Clone the source code in the directory of your choice and set-up a virtual enviornment for **pypesol**, Python 3.10+ (3.12 recommended).

Example command-lines:

```bash
git clone https://github.com/dcs-chalmers/pypesol.git
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### 3. Install Python dependencies

```bash
pip install -r requirements-dev.txt
```

### 4. Verify solver availability

```bash
python -c "import pyomo.environ as pyo; \
print('GLPK:', pyo.SolverFactory('glpk').available()); \
print('CBC:', pyo.SolverFactory('cbc').available())"
```

Both should return `True`.

### 5. Quick test

Activate your project venv (from project root):

```
source .venv/bin/activate
```

Then, run a lightweight Python test which loads the default optimizer and executes it over some small test data:


```
python3 -c "from optimizer import Optimizer as Opt; print(Opt.from_folder2('data_test').optimize(0))"
```

The result should be *-1.06021*, i.e., the optimized electricity cost (with optimal battery level decisions) for user *0* over the time period of the test data.

**Run the tutorial notebook**: From the same activated venv, open the Getting Started notebook:

```bash
jupyter notebook getting_started.ipynb
```

Then, you can follow the **[Jupyter Notebook tutorial](getting_started.ipynb)** -- more info at the end of this readme.

---

# Option 2 — Installation via Docker

Docker provides a fully reproducible environment including:

* Python 3.12
* All required Python dependencies including the jupyter notebook
* GLPK
* CBC

### 1. Install Docker, if needed

#### Ubuntu

```bash
sudo apt install docker.io
sudo usermod -aG docker $USER
newgrp docker
````

#### macOS

Install Docker Desktop for Mac:

[https://docs.docker.com/desktop/setup/install/mac-install/](https://docs.docker.com/desktop/setup/install/mac-install/)

After installation, start Docker Desktop.

#### Windows

We recommend using Docker Desktop with the WSL 2 backend:

[https://docs.docker.com/desktop/setup/install/windows-install/](https://docs.docker.com/desktop/setup/install/windows-install/)

During installation, enable **WSL 2** when prompted.

Then open a WSL terminal (for example Ubuntu) and run the commands below
from there.

### 2. Pull the Docker image

```bash
docker pull duvignau/pypesol:py312
```

Alternatively, manually download the container from dockerhub:

[https://hub.docker.com/r/duvignau/pypesol](https://hub.docker.com/r/duvignau/pypesol)

### 3. Run PyPESOL interactively

From the directory containing the exercise files:

```bash
docker run --rm -it \
  -v "$PWD:/app" \
  -w /app \
  duvignau/pypesol:py312
```

### 4. Run Jupyter Notebook inside Docker

```bash
docker run --rm -it \
  -p 8888:8888 \
  -v "$PWD:/app" \
  -w /app \
  duvignau/pypesol:py312 \
  jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

Open in a browser the link displayed after running the above command (containing the required token).

---

# License

The software is shared under MIT license.

---

# Getting Started

A step-by-step introduction to PyPESOL is provided in the
**[Jupyter Notebook tutorial](getting_started.ipynb)**.

The above tutorial explains the required input data structure and walks through a complete optimization example.

After completed the tutorial, you can use the following exercises to familiarize yourself with the libary:
**[Exercises of the SESBC Summer School 2026](sesbc_exercises.ipynb)**.

The above exercises were developped for the **Swedish Electricity Storage and Balancing Centre (SESBC)** [Summer School](https://www.sesbc.se/news-events/sesbc-summer-school-2026/).


## Required Input Data

Running a PyPESOL optimization requires five input CSV files.
Assume:

- **N** = number of end-users
- **T** = number of time steps

The expected input files are:

1. **`cons.csv`** — End-user electricity consumption
   - Dimension: **T × N**
   - Unit: *kWh* (default)
   - Each row corresponds to one time step.
   - Each column corresponds to one end-user.

2. **`price.csv`** — Electricity price time series
   - Dimension: **T × 1**
   - Unit: *€/kWh* (default)
   - Each row provides the electricity price for the corresponding time step.

3. **`sun.csv`** — Solar production profile
   - Dimension: **T × 1**
   - Unit: *kWh/kWp* (default)
   - Each row represents solar intensity for the corresponding time step.

4. **`pv.csv`** — Installed PV capacities
   - Dimension: **N × 1**
   - Unit: *kWp* (default)
   - Each row specifies the PV system capacity of one end-user.

5. **`battery.csv`** — Installed battery capacities
   - Dimension: **N × 1**
   - Unit: *kWh* (default)
   - Each row specifies the battery storage capacity of one end-user.

### Notes

- All files must be provided in CSV format.
- Time indexing must be consistent across all T-dimensional files (`cons.csv`, `price.csv`, `sun.csv`).
- The ordering of users must be consistent across all N-dimensional files (`cons.csv`, `pv.csv`, `battery.csv`).

For a complete example dataset and usage workflow, refer to the **Getting Started notebook**.
# energy_sharing
