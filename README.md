 🏎️ F1 Race Intelligence Dashboard

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Framework](https://img.shields.io/badge/Framework-Streamlit-red)
![Status](https://img.shields.io/badge/Status-Active-success)



 🌐 Live Application

👉 https://f1-race-intelligence-x43jphvg5asrautkc4ugyt.streamlit.app/


.Overview

This project is a data-driven **Formula 1 strategy intelligence system** designed to move beyond traditional dashboards.

It combines historical race data with statistical modeling to simulate race strategies and identify optimal pit stop decisions.






.Core Capabilities

1 Strategy Intelligence

* Pit stop optimization across full race simulations
* Tyre degradation modeling using regression
* Optimal pit window detection with expected time gain
* Strategy comparison against real race outcomes


2 Race Analytics

* Season and race-level performance tracking
* Driver and constructor comparisons
* Position changes and race progression
* Historical data exploration


3 Data Processing

* Large-scale race dataset integration
* Lap-level performance analysis
* Cleaned and structured analytical pipeline





. Methodology

1 Tyre Degradation Model

* Linear regression fitted per stint
* Outlier removal for stable estimation
* Outputs degradation rate (sec/lap)

2 Strategy Simulation

* Evaluates all possible pit laps
* Projects total race time using degradation trends
* Includes pit stop time loss

 3 Optimization

* Identifies minimum race time scenario
* Produces optimal pit window with confidence range





Project Structure

f1-race-intelligence/
│
├── app.py
├── pages/
├── utils/
├── data/
├── requirements.txt
└── README.md`





Tech Stack

* Python
* Streamlit
* Pandas
* NumPy
* Plotly




 Data Sources

* Ergast Formula 1 dataset
* Public F1 datasets (GitHub)




 Limitations

* Simplified tyre performance assumptions
* No traffic or race incident modeling
* Limited weather integration





 Future Work

* Monte Carlo race simulation
* Compound-aware tyre modeling
* Traffic and clean-air effects
* Machine learning-based strategy prediction




Author

Mayank Pant

B.Sc. Statistics Student




.Focused on:

* Data Science
* Statistical Modeling
* Decision Systems

Acknowledgment

This project is an independent analytical system built for learning and portfolio development in motorsport analytics.
