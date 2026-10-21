# für streamlit in der Webanwendung führe im Terminal im Projektordner 
# folgenden Befehl aus: python3 -m streamlit run app.py

#Was dieser Code bereits kann
#- Deine bestehenden Pyomo-Berechnungen ausführen
#- PV-Leistung und Aufteilungsschlüssel anpassen
#- Strompreise und Sharing-Endpreis verändern
#- Energiebilanzen der einzelnen Teilnehmer darstellen
#- Wirtschaftlichkeit mit und ohne Energy Sharing vergleichen
#- Zahlungsströme nach Preisbestandteilen auswerten
#- Bilanzprüfungen durchführen
#- Zeitreihen als CSV exportieren


from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from optimizer import Optimizer


# ============================================================
# 1. GRUNDKONFIGURATION
# ============================================================

# Webanwendung konfigurieren

st.set_page_config(
    page_title="Energy Sharing Simulator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

col_title, col_author = st.columns([4, 1])

with col_title:
        st.title("⚡ Energy Sharing Simulator")
        st.caption("Interaktive Simulation einer Energiegemeinschaft")

with col_author:
        st.markdown(
            """
            <div style="text-align: right; padding-top: 20px;">
                <span style="font-size: 13px; color: gray;">
                    Entwickelt von
                </span><br>
                <strong style="font-size: 15px;">
                    Selin Temiz
                </strong>
            </div>
            """,
            unsafe_allow_html=True
        )

BASE_DIR = Path(__file__).resolve().parent
DATA_FOLDER = BASE_DIR / "data_test"

N = 96
DT = 0.25
PROSUMER = 0
CONSUMERS = [1, 2, 3]


# ============================================================
# 2. SIMULATIONSFUNKTION
# ============================================================

def run_simulation(allocation_keys, prices, pv_capacities):

    # Eingangsdaten laden
    opt = Optimizer.from_folder2(str(DATA_FOLDER))

    # PV-Leistung für diesen Simulationslauf anpassen
    for h, capacity in pv_capacities.items():
        opt.pv[h] = capacity

    # Solver erstellen
    solver = opt.static_sharing_solver(
        allocation_keys=allocation_keys,
        prosumer=PROSUMER,
        p_p2p=prices["p_sharing"],
        p_feed_in=prices["p_feed_in"],
        residual_price=prices["p_residual"]
    )

    # Optimierung
    solver.solve(N)

    # Bestehende Auswertungsmethoden
    balance = solver.prosumer_energy_balance(N)

    sharing = solver.prosumer_costs(
        N=N,
        grid_price=prices["p_grid"]
    )

    reference = solver.prosumer_reference_costs(
        N=N,
        grid_price=prices["p_grid"]
    )

    consumers = solver.consumer_costs(
        N=N,
        grid_price=prices["p_grid"],
        sharing_price=prices["p_sharing_consumer"]
    )

    # --------------------------------------------------------
    # Zeitreihen
    # --------------------------------------------------------

    time = pd.date_range(
    start="2026-01-01 00:00",
    periods=N,
    freq="15min"
)

    generation = np.asarray(
        balance["generation"], dtype=float
    )
    shared = np.asarray(
        balance["shared"], dtype=float
    )
    self_pv = np.asarray(
        balance["self_consumption_own_pv"], dtype=float
    )
    surplus = np.asarray(
        balance["surplus"], dtype=float
    )
    grid_prosumer = np.asarray(
        balance["grid_import"], dtype=float
    )

    df_time = pd.DataFrame({
        "Stunde": time,
        "PV-Erzeugung": generation,
        "Energy Sharing": shared,
        "Eigenverbrauch": self_pv,
        "Netzeinspeisung": surplus,
        "Netzbezug Prosumer": grid_prosumer
    }).set_index("Stunde")

    # --------------------------------------------------------
    # Zeitreihen je ESC-Mitglied
    # --------------------------------------------------------

    member_timeseries = {}

    for h in range(len(opt.cons)):

        demand_h = np.array([
            solver.consf(h, t)
            for t in range(N)
        ], dtype=float)

        grid_h = np.array([
            solver.model.el_in[h, t].value
            for t in range(N)
        ], dtype=float)

        sharing_h = np.array([
            solver.model.imported[h, t].value
            for t in range(N)
        ], dtype=float)

        pv_h = np.array([
            solver.sunf(h, t) * opt.pv[h]
            for t in range(N)
        ], dtype=float)

        member_timeseries[h] = pd.DataFrame({
            "Stunde": time,
            "Verbrauch": demand_h,
            "PV-Erzeugung": pv_h,
            "Energy Sharing": sharing_h,
            "Netzbezug": grid_h
        }).set_index("Stunde")

    # Eigenverbrauch und abgegebene Sharing-Energie
    # für den bisherigen Prosumer 0 ergänzen
    member_timeseries[PROSUMER]["Eigenverbrauch"] = self_pv
    member_timeseries[PROSUMER]["Sharing-Abgabe"] = shared
    member_timeseries[PROSUMER]["Netzeinspeisung"] = surplus

    # Bei den übrigen Mitgliedern zunächst keine PV-Abgabe
    for h in member_timeseries:
        if h != PROSUMER:
            member_timeseries[h]["Eigenverbrauch"] = 0.0
            member_timeseries[h]["Sharing-Abgabe"] = 0.0
            member_timeseries[h]["Netzeinspeisung"] = 0.0

    # --------------------------------------------------------
    # Consumer-Energiebilanzen
    # --------------------------------------------------------

    consumer_rows = []
    total_consumer_savings = 0.0
    total_consumer_grid = 0.0
    total_consumer_demand = 0.0
    total_consumer_shared = 0.0

    for c in CONSUMERS:

        demand = np.array([
            solver.consf(c, t)
            for t in range(N)
        ], dtype=float)

        shared_c = np.array([
            solver.model.imported[c, t].value
            for t in range(N)
        ], dtype=float)

        grid_c = np.array([
            solver.model.el_in[c, t].value
            for t in range(N)
        ], dtype=float)

        E_demand = demand.sum()
        E_shared_c = shared_c.sum()
        E_grid_c = grid_c.sum()

        total_consumer_demand += E_demand
        total_consumer_shared += E_shared_c
        total_consumer_grid += E_grid_c
        total_consumer_savings += consumers[c]["savings"]

        consumer_rows.append({
            "Teilnehmer": f"Consumer {c}",
            "Verbrauch [kWh]": E_demand,
            "Sharing [kWh]": E_shared_c,
            "Netzbezug [kWh]": E_grid_c,
            "Ohne ES [€]": consumers[c]["cost_without_es"],
            "Mit ES [€]": consumers[c]["cost_with_es"],
            "Ersparnis [€]": consumers[c]["savings"]
        })

        df_time[f"Verbrauch Consumer {c}"] = demand
        df_time[f"Sharing Consumer {c}"] = shared_c

    df_consumers = pd.DataFrame(
        consumer_rows
    ).set_index("Teilnehmer")

    # --------------------------------------------------------
    # Prosumer-Kostenvergleich
    # --------------------------------------------------------

    revenue_sharing = (
        sharing["sharing_revenue"]
        + sharing["residual_revenue"]
    )

    df_prosumer = pd.DataFrame({
        "Ohne ES": {
            "Netzbezugskosten": reference["grid_cost"],
            "Vermarktungserlöse": reference["feed_in_revenue"],
            "Nettostromkosten": reference["net_cost"]
        },
        "Mit ES": {
            "Netzbezugskosten": sharing["grid_cost"],
            "Vermarktungserlöse": revenue_sharing,
            "Nettostromkosten": sharing["net_cost"]
        }
    })

    df_prosumer["Veränderung"] = (
        df_prosumer["Mit ES"] - df_prosumer["Ohne ES"]
    )

    # --------------------------------------------------------
    # Zahlungsbilanz
    # --------------------------------------------------------

    E_shared = shared.sum()

    components = {
        "Prosumer-Vergütung": prices["p_sharing"],
        "Netzentgelte": prices["p_netzentgelte"],
        "Umlagen und Abgaben": prices["p_umlagen_abgaben"],
        "Stromsteuer": prices["p_stromsteuer"],
        "Servicegebühr": prices["p_servicegebühr"]
    }

    df_payments = pd.DataFrame([
        {
            "Bestandteil": name,
            "Preis [ct/kWh]": price * 100,
            "Betrag [€]": E_shared * price
        }
        for name, price in components.items()
    ]).set_index("Bestandteil")

    # --------------------------------------------------------
    # Kennzahlen und Bilanzkontrollen
    # --------------------------------------------------------

    E_generation = generation.sum()
    E_self = self_pv.sum()
    E_surplus = surplus.sum()

    E_total_demand = (
        total_consumer_demand
        + sum(solver.consf(PROSUMER, t) for t in range(N))
    )

    E_total_grid = (
        total_consumer_grid + grid_prosumer.sum()
    )

    E_local_pv = E_self + total_consumer_shared

    autarky = (
        100 * E_local_pv / E_total_demand
        if E_total_demand > 0 else 0
    )

    pv_utilization = (
        100 * E_local_pv / E_generation
        if E_generation > 0 else 0
    )

    prosumer_savings = (
        reference["net_cost"] - sharing["net_cost"]
    )

    community_benefit = (
        prosumer_savings + total_consumer_savings
    )

    # Bilanzprüfungen über alle Zeitschritte
    pv_error = np.max(np.abs(
        generation - shared - self_pv - surplus
    ))

    # Summe der Sharing-Energie aller Consumer je Zeitschritt
    consumer_sharing_ts = np.array([
        [
            solver.model.imported[c, t].value
            for t in range(N)
        ]
        for c in CONSUMERS
    ], dtype=float)

    total_sharing_ts = consumer_sharing_ts.sum(axis=0)

    # Maximale Abweichung über alle Zeitschritte
    sharing_error = np.max(
        np.abs(shared - total_sharing_ts)
    )

    payment_error = abs(
        df_payments["Betrag [€]"].sum()
        - E_shared * prices["p_sharing_consumer"]
    )

    # Ergebnisse unabhängig vom Solver zurückgeben
    return {
        "timeseries": df_time,
            "member_timeseries": member_timeseries,
    "prosumer_pv_usage": {
        PROSUMER: {
            "Eigenverbrauch": float(self_pv.sum()),
            "Energy Sharing": float(shared.sum()),
            "Netzeinspeisung": float(surplus.sum())
        }
    },
        "consumers": df_consumers,
        "prosumer": df_prosumer,
        "payments": df_payments,
        "generation": E_generation,
        "shared": E_shared,
        "self": E_self,
        "surplus": E_surplus,
        "grid": E_total_grid,
        "demand": E_total_demand,
        "autarky": autarky,
        "pv_utilization": pv_utilization,
        "prosumer_savings": prosumer_savings,
        "consumer_savings": total_consumer_savings,
        "community_benefit": community_benefit,
        "checks": {
            "PV-Bilanz": pv_error,
            "Sharing-Bilanz (Tag)": sharing_error,
            "Zahlungsbilanz": payment_error
        },
        "parameters": {
            "pv_capacities": pv_capacities.copy(),
            "allocation_keys_by_prosumer": {
                p: keys.copy()
                for p, keys in allocation_keys_by_prosumer.items()
            },
            "prices": prices.copy(),
            "N": N,
            "DT": DT
        }
    }


# ============================================================
# 3. BENUTZEROBERFLÄCHE
# ============================================================

# Verfügbare Mitglieder aus den Eingangsdaten
opt_config = Optimizer.from_folder2(str(DATA_FOLDER))
AVAILABLE_MEMBERS = list(range(len(opt_config.cons)))

# Mitgliederverwaltung initialisieren
if "members_config" not in st.session_state:
    st.session_state.members_config = {
        0: {
            "role": "prosumer",
            "pv_kwp": 5.0,
            "allocation_keys": {1: 50.0, 2: 30.0, 3: 20.0}
        },
        1: {
            "role": "consumer",
            "pv_kwp": 0.0,
            "allocation_keys": {}
        },
        2: {
            "role": "consumer",
            "pv_kwp": 0.0,
            "allocation_keys": {}
        },
        3: {
            "role": "consumer",
            "pv_kwp": 0.0,
            "allocation_keys": {}
        }
    }

with st.sidebar:

    st.header("⚙️ Modellparameter")
    st.subheader("ESC-Mitglieder")

    # -----------------------------------------
    # Neue Mitglieder hinzufügen
    # -----------------------------------------

    available_to_add = [
        h for h in AVAILABLE_MEMBERS
        if h not in st.session_state.members_config
    ]

    if available_to_add:

        new_member = st.selectbox(
            "Mitglied auswählen",
            available_to_add,
            format_func=lambda h: f"Mitglied {h}"
        )

        new_role = st.radio(
            "Mitglied hinzufügen als",
            ["Consumer", "Prosumer"],
            horizontal=True
        )

        if st.button("➕ Mitglied hinzufügen"):

            st.session_state.members_config[new_member] = {
                "role": new_role.lower(),
                "pv_kwp": 3.0 if new_role == "Prosumer" else 0.0,
                "allocation_keys": {}
            }

            st.rerun()

    # -----------------------------------------
    # Bestehende Mitglieder konfigurieren
    # -----------------------------------------

    for h in list(st.session_state.members_config):

        config = st.session_state.members_config[h]

        with st.expander(
            f"Mitglied {h} – {config['role'].capitalize()}",
            expanded=(h == 0)
        ):

            # Rolle ändern
            role = st.selectbox(
                "Rolle",
                ["consumer", "prosumer"],
                index=(
                    1 if config["role"] == "prosumer" else 0
                ),
                key=f"role_{h}",
                disabled=(h == 0)
            )

            config["role"] = role

            if role == "prosumer":

                config["pv_kwp"] = st.number_input(
                    "PV-Leistung [kWp]",
                    min_value=0.1,
                    value=max(float(config["pv_kwp"]), 0.1),
                    step=0.5,
                    key=f"pv_{h}"
                )

                st.markdown("**Aufteilungsschlüssel**")

                recipients = [
                    c for c in st.session_state.members_config
                    if c != h
                ]

                new_keys = {}

                for c in recipients:

                    default_alpha = config[
                        "allocation_keys"
                    ].get(c, 0.0)

                    alpha = st.number_input(
                        f"Mitglied {c} [%]",
                        min_value=0.0,
                        max_value=100.0,
                        value=float(default_alpha),
                        step=5.0,
                        key=f"alpha_{h}_{c}"
                    )

                    new_keys[c] = alpha

                config["allocation_keys"] = new_keys

                total = sum(new_keys.values())

                if abs(total - 100.0) < 1e-6:
                    st.success("Aufteilung: 100 %")
                else:
                    st.error(
                        f"Aufteilung: {total:.1f} % "
                        "(erforderlich: 100 %)"
                    )

            else:
                config["pv_kwp"] = 0.0
                config["allocation_keys"] = {}

            # Mitglied entfernen
            if h != 0:

                if st.button(
                    "🗑️ Mitglied entfernen",
                    key=f"remove_{h}"
                ):
                    del st.session_state.members_config[h]
                    st.rerun()

    st.divider()

    # -----------------------------------------
    # Simulationsparameter ableiten
    # -----------------------------------------

    MEMBERS = list(st.session_state.members_config)

    PROSUMERS = [
        h for h in MEMBERS
        if st.session_state.members_config[h]["role"] == "prosumer"
    ]

    CONSUMERS = [
        h for h in MEMBERS
        if h not in PROSUMERS
    ]

    pv_capacities = {
        h: 0.0 for h in AVAILABLE_MEMBERS
    }

    allocation_keys_by_prosumer = {}

    for p in PROSUMERS:

        config = st.session_state.members_config[p]

        pv_capacities[p] = config["pv_kwp"]

        allocation_keys_by_prosumer[p] = {
            c: alpha / 100.0
            for c, alpha in config["allocation_keys"].items()
        }

    allocation_valid = all(
        abs(sum(keys.values()) - 1.0) < 1e-6
        for keys in allocation_keys_by_prosumer.values()
    )

    allocation_valid = allocation_valid and bool(PROSUMERS)

    # AB HIER BLEIBT DEIN BESTEHENDER CODE:
    st.subheader("Strompreise [€/kWh]")

    st.subheader("Strompreise [€/kWh]")

    p_grid = st.number_input(
        "Haushaltsstrompreis",
        value=0.37,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_sharing = st.number_input(
        "P2P-Vergütung",
        value=0.13,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_network = st.number_input(
        "Netzentgelte",
        value=0.09,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_levies = st.number_input(
        "Umlagen und Abgaben",
        value=0.07,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_tax = st.number_input(
        "Stromsteuer",
        value=0.02,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_service = st.number_input(
        "Servicegebühr",
        value=0.01,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_feed_in = st.number_input(
        "Einspeisevergütung",
        value=0.08,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_residual = st.number_input(
        "Restüberschussvergütung",
        value=0.00,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    p_es = (
        p_sharing + p_network
        + p_levies + p_tax + p_service
    )

    st.metric(
        "Sharing-Endpreis",
        f"{p_es:.3f} €/kWh"
    )

    st.divider()

    run_button = st.button(
        "▶ Simulation starten",
        type="primary",
        use_container_width=True
    )

# ============================================================
# 4. SIMULATION AUSFÜHREN
# ============================================================

# Für den bisherigen Single-Prosumer-Solver
allocation_keys = allocation_keys_by_prosumer.get(0, {})

prices = {
    "p_grid": p_grid,
    "p_sharing": p_sharing,
    "p_netzentgelte": p_network,
    "p_umlagen_abgaben": p_levies,
    "p_stromsteuer": p_tax,
    "p_servicegebühr": p_service,
    "p_feed_in": p_feed_in,
    "p_residual": p_residual,
    "p_sharing_consumer": p_es
}

if run_button:

    if not allocation_valid:
        st.error("Bitte die Aufteilungsschlüssel korrigieren.")

    elif set(MEMBERS) != set(AVAILABLE_MEMBERS):
        st.warning(
            "Das Entfernen von Mitgliedern ist in der Oberfläche "
            "vorbereitet, aber noch nicht mit dem Solver verbunden."
        )

    elif PROSUMERS != [0]:
        st.warning(
            "Mehrere Prosumer werden erst nach der "
            "Erweiterung des Solvers unterstützt."
        )

    else:
        try:
            with st.spinner("Optimierung wird durchgeführt..."):
                results = run_simulation(
                    allocation_keys_by_prosumer[0],
                    prices,
                    pv_capacities
                )

            st.session_state["results"] = results
            st.success("Simulation erfolgreich abgeschlossen!")

        except Exception as exc:
            st.error("Simulation fehlgeschlagen.")
            st.exception(exc)


# ============================================================
# 5. DASHBOARD
# ============================================================

if "results" not in st.session_state:

    st.info(
        "Wähle links deine Modellparameter "
        "und starte die Simulation."
    )

else:

    r = st.session_state["results"]

    # Parameter der letzten Simulation
    previous = r["parameters"]

    # Aktuell eingestellte Parameter
    current = {
        "pv_capacities": pv_capacities.copy(),
        "allocation_keys_by_prosumer": {
            p: keys.copy()
            for p, keys in allocation_keys_by_prosumer.items()
        },
        "prices": prices.copy(),
        "N": N,
        "DT": DT
    }

    # Änderungen erkennen
    parameters_changed = previous != current

    if parameters_changed:
        st.warning(
            "⚠️ Die Eingabeparameter wurden verändert. "
            "Die angezeigten Ergebnisse gehören noch zur "
            "letzten Simulation. Bitte starte die Simulation erneut."
        )
    else:
        st.success(
            "Die angezeigten Ergebnisse entsprechen "
            "den aktuellen Modellparametern."
        )

    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ Energiebilanz",
        "💶 Wirtschaftlichkeit",
        "🔍 Modellkontrolle",
        "⚙️ Simulationsparameter"
    ])

    # --------------------------------------------------------
    # TAB 1: ENERGIEBILANZ
    # --------------------------------------------------------

    with tab1:

        st.subheader("Energiebilanz der Gemeinschaft")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "PV-Erzeugung",
            f"{r['generation']:.2f} kWh"
        )
        c2.metric(
            "Energy Sharing",
            f"{r['shared']:.2f} kWh"
        )
        c3.metric(
            "Autarkiegrad",
            f"{r['autarky']:.1f} %"
        )
        c4.metric(
            "PV-Nutzungsgrad",
            f"{r['pv_utilization']:.1f} %"
        )

        st.divider()

        st.subheader("Zeitlicher Verlauf")

        member_data = r["member_timeseries"]
        member_ids = sorted(member_data.keys())

        selected_members = st.multiselect(
            "ESC-Mitglieder auswählen",
            options=member_ids,
            default=member_ids,
            format_func=lambda h: f"Mitglied {h}",
            key="chart_selected_members"
        )

        if selected_members:

            # Zeitreihen der ausgewählten Mitglieder summieren
            df_selected = pd.DataFrame(
                0.0,
                index=member_data[selected_members[0]].index,
                columns=[
                    "Verbrauchsprofil",
                    "PV-Erzeugungsprofil",
                    "PV-Eigenverbrauchsprofil",
                    "Eigenverbrauch",
                    "Sharing-Bezug",
                    "Sharing-Abgabe",
                    "Reststrombezug"
                ]
            )

            for h in selected_members:

                data_h = member_data[h]

                # Gesamter Stromverbrauch aus data_test
                df_selected["Verbrauchsprofil"] += data_h["Verbrauch"]

                # PV-Erzeugung der ausgewählten Mitglieder
                df_selected["PV-Erzeugungsprofil"] += data_h["PV-Erzeugung"]

                # Direkt selbst verbrauchter PV-Strom
                df_selected["PV-Eigenverbrauchsprofil"] += data_h["Eigenverbrauch"]

                # Energy Sharing
                df_selected["Sharing-Bezug"] += data_h["Energy Sharing"]
                df_selected["Sharing-Abgabe"] += data_h["Sharing-Abgabe"]

                # Reststrom aus dem öffentlichen Netz
                df_selected["Reststrombezug"] += data_h["Netzbezug"]

            fig = px.line(
                df_selected,
                x=df_selected.index,
                y=df_selected.columns,
                labels={
                    "x": "Uhrzeit",
                    "value": "Energie je 15 Minuten [kWh]",
                    "variable": "Energiefluss"
                }
            )

            fig.update_xaxes(
                tickformat="%H:%M",
                dtick=2 * 60 * 60 * 1000,
                title="Uhrzeit"
            )

            fig.update_layout(
                hovermode="x unified",
                height=450
            )

            st.plotly_chart(
                fig,
                use_container_width=True
            )

        else:
            st.info("Bitte mindestens ein ESC-Mitglied auswählen.")

        st.subheader("Verwendung der PV-Erzeugung")

        pv_usage = r["prosumer_pv_usage"]
        prosumer_ids = sorted(pv_usage.keys())

        prosumer_options = ["Alle Prosumer"] + [
            f"Prosumer {p}" for p in prosumer_ids
        ]

        selected_prosumer = st.selectbox(
            "Prosumer auswählen",
            options=prosumer_options,
            index=0,
            key="chart_selected_prosumer"
        )

        if selected_prosumer == "Alle Prosumer":
            selected_prosumers = prosumer_ids
        else:
            selected_prosumers = [
                int(selected_prosumer.split()[-1])
            ]

        labels = [
            f"Prosumer {p}"
            for p in selected_prosumers
        ]

        fig = go.Figure()

        colors = {
            "Eigenverbrauch": "#2E86AB",
            "Energy Sharing": "#F4A261",
            "Netzeinspeisung": "#7CB342"
        }

        for category in [
            "Eigenverbrauch",
            "Energy Sharing",
            "Netzeinspeisung"
        ]:

            values = [
                pv_usage[p][category]
                for p in selected_prosumers
            ]

            fig.add_trace(
                go.Bar(
                    name=category,
                    y=labels,
                    x=values,
                    orientation="h",
                    marker_color=colors[category],
                    hovertemplate=(
                        "%{y}<br>"
                        + category
                        + ": %{x:.2f} kWh"
                        + "<extra></extra>"
                    )
                )
            )

        fig.update_layout(
            barmode="stack",
            xaxis_title="Energie [kWh]",
            yaxis_title="",
            legend_title="Verwendung",
            height=max(300, 100 * len(selected_prosumers)),
            margin=dict(l=20, r=20, t=20, b=20)
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        st.subheader("Energiebilanz der Consumer")

        st.dataframe(
            r["consumers"][[
                "Verbrauch [kWh]",
                "Sharing [kWh]",
                "Netzbezug [kWh]"
            ]].style.format("{:.3f}"),
            use_container_width=True
        )

        st.subheader("Energiebilanz der Gemeinschaft")

        df_total = pd.DataFrame({
            "Energie [kWh]": {
                "Gesamtverbrauch": r["demand"],
                "PV-Erzeugung": r["generation"],
                "Energy Sharing": r["shared"],
                "Eigenverbrauch": r["self"],
                "Gesamter Netzbezug": r["grid"],
                "PV-Netzeinspeisung": r["surplus"]
            }
        })

        st.dataframe(
            df_total.style.format("{:.3f}"),
            use_container_width=True
        )

    # --------------------------------------------------------
    # TAB 2: WIRTSCHAFTLICHKEIT
    # --------------------------------------------------------

    with tab2:

        st.subheader("Wirtschaftlicher Vergleich")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Prosumer-Vorteil",
            f"{r['prosumer_savings']:+.2f} €"
        )

        c2.metric(
            "Consumer-Ersparnis",
            f"{r['consumer_savings']:+.2f} €"
        )

        c3.metric(
            "Gesamter Haushaltsvorteil",
            f"{r['community_benefit']:+.2f} €"
        )

        st.divider()

        st.subheader("Prosumer")

        st.dataframe(
            r["prosumer"].style.format("{:.2f} €"),
            use_container_width=True
        )

        st.subheader("Consumer")

        st.dataframe(
            r["consumers"][[
                "Ohne ES [€]",
                "Mit ES [€]",
                "Ersparnis [€]"
            ]].style.format("{:.2f} €"),
            use_container_width=True
        )

        st.subheader("Zahlungsbilanz Energy Sharing")

        st.dataframe(
            r["payments"].style.format({
                "Preis [ct/kWh]": "{:.2f}",
                "Betrag [€]": "{:.2f}"
            }),
            use_container_width=True
        )

        st.bar_chart(
            r["payments"][["Betrag [€]"]]
        )

        st.caption(
            "Die Gesamtbewertung umfasst die finanziellen "
            "Vorteile der Haushalte. Zahlungen an externe "
            "Akteure sind keine zusätzlichen Haushaltsvorteile."
        )

    # --------------------------------------------------------
    # TAB 3: MODELLKONTROLLE
    # --------------------------------------------------------

    with tab3:

        st.subheader("Bilanzprüfungen")

        df_checks = pd.DataFrame([
            {
                "Prüfung": name,
                "Abweichung": error,
                "Status": (
                    "OK" if error < 1e-6 else "Prüfen"
                )
            }
            for name, error in r["checks"].items()
        ]).set_index("Prüfung")

        st.dataframe(
            df_checks,
            use_container_width=True
        )

        st.subheader("Simulationsdaten")

        st.dataframe(
            r["timeseries"],
            use_container_width=True
        )

        csv = r["timeseries"].to_csv().encode("utf-8")

        st.download_button(
            "Zeitreihen als CSV herunterladen",
            data=csv,
            file_name="energy_sharing_results.csv",
            mime="text/csv"
        )

    # --------------------------------------------------------
    # TAB 4: SIMULATIONSPARAMETER
    # --------------------------------------------------------

    with tab4:

        st.subheader("Verwendete Simulationsparameter")

        params = r["parameters"]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Installierte PV-Leistung",
            f"{sum(params['pv_capacities'].values()):.1f} kWp"
        )

        col2.metric(
            "Simulationsdauer",
            f"{params['N'] * params['DT']:.1f} h"
        )

        col3.metric(
            "Zeitschritte",
            params["N"]
        )

        st.divider()

        st.subheader("Aufteilungsschlüssel")

        df_allocation = pd.DataFrame([
            {
                "Prosumer": p,
                "Empfänger": c,
                "Aufteilung [%]": alpha * 100
            }
            for p, keys in params["allocation_keys_by_prosumer"].items()
            for c, alpha in keys.items()
        ])

        st.dataframe(
            df_allocation,
            hide_index=True,
            use_container_width=True
        )

        st.subheader("Strompreise")

        price_names = {
            "p_grid": "Haushaltsstrompreis",
            "p_sharing": "P2P-Vergütung",
            "p_sharing_consumer": "Sharing-Endpreis",
            "p_netzentgelte": "Netzentgelte",
            "p_umlagen_abgaben": "Umlagen und Abgaben",
            "p_stromsteuer": "Stromsteuer",
            "p_servicegebühr": "Servicegebühr",
            "p_feed_in": "Einspeisevergütung",
            "p_residual": "Restüberschussvergütung"
        }

        df_prices = pd.DataFrame([
            {
                "Preisbestandteil": price_names.get(key, key),
                "Preis [ct/kWh]": value * 100
            }
            for key, value in params["prices"].items()
        ])

        st.dataframe(
            df_prices.style.format({
                "Preis [ct/kWh]": "{:.2f}"
            }),
            hide_index=True,
            use_container_width=True
        )