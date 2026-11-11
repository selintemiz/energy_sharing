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

N = 35040
DT = 0.25



# Österreichische EEG: 2025 geltende, arbeitsbezogene Netznutzungsrabatte.
# Die Rabatte beziehen sich nur auf die Netzkomponente des Sharing-Bezugs.
AT_NETWORK_DISCOUNTS = {
    "Keine Vergünstigung / überregional": 0.0,
    "Lokale ESC (AT-Vorbild, NE 6/7)": 0.57,
    "Regionale ESC (AT-Vorbild, NE 6/7)": 0.28,
    "Regionale ESC (AT-Vorbild, NE 4/5)": 0.64,
}


def sharing_tariff(p2p, network, levies, electricity_tax, service,
                   discount, bonus):
    """Deutsche Preisbestandteile; nur Netznutzungsrabatt nach AT-Vorbild.

    Der Rabatt ist ein hypothetisches deutsches Szenario, keine geltende
    deutsche Netzentgeltregelung. Der Bonus wird extern finanziert.
    """
    network_paid = network * (1.0 - discount)
    return {
        "p_sharing_consumer": p2p + network_paid + levies + electricity_tax + service,
        "p_network_paid": network_paid,
        "p_levies_paid": levies,
        "p_tax_paid": electricity_tax,
        "p_bonus": bonus,
        "p_network_discount": discount,
    }


# ============================================================
# 2. SIMULATIONSFUNKTION
# ============================================================

def run_simulation(allocation_keys_by_prosumer, prices, pv_capacities, members_config):
    """Deterministische statische PV-Zuteilung ohne Umverteilung oder Speicher.

    Verwendet 35.040 synthetische Viertelstundenwerte für das Kalenderjahr 2025.
    Die Profile sind plausible Szenarien, keine gemessenen ENTSO-E-Daten.
    """
    opt = Optimizer.from_folder2(str(DATA_FOLDER))
    member_ids = sorted(members_config)
    prosumers = [h for h in member_ids if members_config[h]["role"] == "prosumer"]
    consumers = [h for h in member_ids if h not in prosumers]
    lengths = [len(opt.cons[h]) for h in member_ids] + [len(opt.sun[h]) for h in member_ids]
    lengths.append(len(opt.price[0]))
    if any(length != N for length in lengths):
        raise ValueError(f"Jahresprofile benötigen genau {N} Viertelstundenwerte; gefunden: {lengths}")
    n = N
    time = pd.date_range("2025-01-01", periods=n, freq="15min")
    demand = {h: np.asarray(opt.cons[h][:n], dtype=float) for h in member_ids}
    generation = {
        p: np.asarray(opt.sun[p][:n], dtype=float) * float(pv_capacities[p])
        for p in prosumers
    }
    # Eigenanteil zuerst; andere PV-Anteile nur auf den noch offenen Bedarf.
    # Dies vermeidet, dass ein Haushalt Energie über seinen Verbrauch hinaus erhält.
    own = {h: np.zeros(n) for h in member_ids}
    sharing_in = {h: np.zeros(n) for h in member_ids}
    sharing_out = {p: np.zeros(n) for p in prosumers}
    surplus = {p: np.zeros(n) for p in prosumers}
    flows = {(p, h): np.zeros(n) for p in prosumers for h in member_ids if h != p}
    for p in prosumers:
        alpha = allocation_keys_by_prosumer[p]
        own[p] = np.minimum(demand[p], alpha.get(p, 0.0) * generation[p])
    remaining = {h: np.maximum(0.0, demand[h] - own[h]) for h in member_ids}
    # Bei mehreren Prosumern: festgelegte Priorität nach Mitglieds-ID.
    # Ungenutzte Zuteilungen werden nicht an andere Empfänger umverteilt.
    for p in sorted(prosumers):
        for h in member_ids:
            if h == p:
                continue
            entitlement = allocation_keys_by_prosumer[p].get(h, 0.0) * generation[p]
            used = np.minimum(entitlement, remaining[h])
            flows[p, h] = used
            sharing_in[h] += used
            sharing_out[p] += used
            remaining[h] -= used
        surplus[p] = np.maximum(0.0, generation[p] - own[p] - sharing_out[p])
    grid = remaining
    df_time = pd.DataFrame(index=time)
    df_time.index.name = "Stunde"
    df_time["PV-Erzeugung"] = sum(generation.values(), np.zeros(n))
    df_time["Energy Sharing"] = sum(sharing_out.values(), np.zeros(n))
    df_time["Eigenverbrauch"] = sum(own.values(), np.zeros(n))
    df_time["Netzeinspeisung"] = sum(surplus.values(), np.zeros(n))
    df_time["Netzbezug Prosumer"] = sum((grid[p] for p in prosumers), np.zeros(n))
    member_timeseries = {}
    for h in member_ids:
        member_timeseries[h] = pd.DataFrame({
            "Verbrauch": demand[h],
            "PV-Erzeugung": generation.get(h, np.zeros(n)),
            "Energy Sharing": sharing_in[h],
            "Netzbezug": grid[h],
            "Eigenverbrauch": own[h],
            "Sharing-Abgabe": sharing_out.get(h, np.zeros(n)),
            "Netzeinspeisung": surplus.get(h, np.zeros(n)),
        }, index=time)
        for col in ("Verbrauch", "Energy Sharing"):
            df_time[f"{col} Mitglied {h}"] = member_timeseries[h][col]
    pv_usage = {
        p: {"Eigenverbrauch": float(own[p].sum()),
            "Energy Sharing": float(sharing_out[p].sum()),
            "Netzeinspeisung": float(surplus[p].sum())}
        for p in prosumers
    }
    consumer_rows = []
    total_consumer_savings = 0.0
    for c in consumers:
        e_demand, e_shared, e_grid = (float(x.sum()) for x in (demand[c], sharing_in[c], grid[c]))
        without = e_demand * prices["p_grid"]
        with_es = e_grid * prices["p_grid"] + e_shared * prices["p_sharing_consumer"]
        total_consumer_savings += without - with_es
        consumer_rows.append({
            "Teilnehmer": f"Consumer {c}", "Verbrauch [kWh]": e_demand,
            "PV-Eigenverbrauch [kWh]": 0.0, "Sharing-Bezug [kWh]": e_shared,
            "Reststrombezug [kWh]": e_grid,
            "Einspeisevergütung Reststrombezug [kWh]": e_demand,
            "Einspeisevergütung Netzbezugskosten [€]": without,
            "ES Reststrombezugskosten [€]": e_grid * prices["p_grid"],
            "ES Sharing-Bezugskosten [€]": e_shared * prices["p_sharing_consumer"],
            "Sharing [kWh]": e_shared, "Netzbezug [kWh]": e_grid,
            "Ohne ES [€]": without, "Mit ES [€]": with_es,
            "Ersparnis [€]": without - with_es
        })
    df_consumers = pd.DataFrame(consumer_rows, columns=[
        "Teilnehmer", "Verbrauch [kWh]", "PV-Eigenverbrauch [kWh]",
        "Sharing-Bezug [kWh]", "Reststrombezug [kWh]",
        "Einspeisevergütung Reststrombezug [kWh]",
        "Einspeisevergütung Netzbezugskosten [€]",
        "ES Reststrombezugskosten [€]", "ES Sharing-Bezugskosten [€]",
        "Sharing [kWh]", "Netzbezug [kWh]",
        "Ohne ES [€]", "Mit ES [€]", "Ersparnis [€]"
    ]).set_index("Teilnehmer")
    # Vergleich pro Prosumer: Referenz = Eigenverbrauch vor Einspeisung mit Vergütung.
    # ES = statische Zuteilung; Restüberschuss wird physisch eingespeist, aber nicht vergütet.
    prosumer_cost_rows = []
    total_prosumer_savings = 0.0
    for p in prosumers:
        ref_own = np.minimum(generation[p], demand[p])
        ref_grid = np.maximum(0.0, demand[p] - ref_own)
        ref_feed = np.maximum(0.0, generation[p] - ref_own)
        assert np.allclose(generation[p], ref_own + ref_feed), f"PV-Bilanzfehler bei Prosumer {p}"
        assert np.allclose(demand[p], ref_own + ref_grid), f"Verbrauchsbilanzfehler bei Prosumer {p}"
        ref_grid_cost = float(ref_grid.sum()) * prices["p_grid"]
        ref_revenue = float(ref_feed.sum()) * prices["p_feed_in"]
        es_grid_cost = float(grid[p].sum()) * prices["p_grid"]
        es_revenue = float(sharing_out[p].sum()) * (prices["p_sharing"] + prices.get("p_bonus", 0.0))
        # Ein Prosumer kann zusätzlich Strom von anderen Prosumern beziehen.
        es_sharing_cost = float(sharing_in[p].sum()) * prices["p_sharing_consumer"]
        ref_net = ref_grid_cost - ref_revenue
        es_net = es_grid_cost + es_sharing_cost - es_revenue
        total_prosumer_savings += ref_net - es_net
        prosumer_cost_rows.append({
            "Prosumer": f"Prosumer {p}",
            "PV-Erzeugung [kWh]": float(generation[p].sum()),
            "Eigenbedarf [kWh]": float(demand[p].sum()),
            "Referenz Eigenverbrauch [kWh]": float(ref_own.sum()),
            "Referenz Netzbezug [kWh]": float(ref_grid.sum()),
            "Referenz Einspeisung [kWh]": float(ref_feed.sum()),
            "ES Eigenverbrauch [kWh]": float(own[p].sum()),
            "ES Sharing-Abgabe [kWh]": float(sharing_out[p].sum()),
            "ES Sharing-Bezug [kWh]": float(sharing_in[p].sum()),
            "ES Netzbezug [kWh]": float(grid[p].sum()),
            "ES Unvergütete Einspeisung [kWh]": float(surplus[p].sum()),
            "Referenz Netzbezugskosten [€]": ref_grid_cost,
            "Referenz Einspeiseerlöse [€]": ref_revenue,
            "Referenz Nettostromkosten [€]": ref_net,
            "ES Netzbezugskosten [€]": es_grid_cost,
            "ES Sharing-Bezugskosten [€]": es_sharing_cost,
            "ES P2P-Erlöse [€]": float(sharing_out[p].sum()) * prices["p_sharing"],
            "ES Sharing-Bonus [€]": float(sharing_out[p].sum()) * prices.get("p_bonus", 0.0),
            "ES Restüberschuss-Erlöse [€]": 0.0,
            "ES Nettostromkosten [€]": es_net,
            "Vorteil ES [€]": ref_net - es_net
        })
    df_prosumer = pd.DataFrame(prosumer_cost_rows).set_index("Prosumer")
    # Monatswerte für Kosten, Erlöse und Energiemengen (kWh / EUR)
    monthly = pd.DataFrame(index=time)
    monthly["Verbrauch [kWh]"] = sum(demand.values(), np.zeros(n))
    monthly["PV-Erzeugung [kWh]"] = sum(generation.values(), np.zeros(n))
    monthly["PV-Eigenverbrauch [kWh]"] = sum(own.values(), np.zeros(n))
    monthly["Sharing [kWh]"] = sum(sharing_out.values(), np.zeros(n))
    monthly["Restnetzbezug [kWh]"] = sum(grid.values(), np.zeros(n))
    monthly["Unvergütete Einspeisung ES [kWh]"] = sum(surplus.values(), np.zeros(n))
    monthly["P2P-Erlöse ES [€]"] = monthly["Sharing [kWh]"] * prices["p_sharing"]
    monthly["Sharing-Bonus ES [€]"] = monthly["Sharing [kWh]"] * prices.get("p_bonus", 0.0)
    monthly["Netzbezugskosten ES [€]"] = monthly["Restnetzbezug [kWh]"] * prices["p_grid"]
    monthly["Sharing-Bezugskosten ES [€]"] = sum(sharing_in.values(), np.zeros(n)) * prices["p_sharing_consumer"]
    monthly["Einspeiseerlöse Referenz [€]"] = sum(
        (np.maximum(0, generation[p] - np.minimum(generation[p], demand[p])) for p in prosumers),
        np.zeros(n)
    ) * prices["p_feed_in"]
    # Referenzmodell und ES-Modell als vollständige Monatsabrechnung.
    # Referenz: kein Sharing, lokale PV-Nutzung zuerst, Überschuss mit Vergütung.
    ref_grid_ts = sum(
        (np.maximum(0.0, demand[h] - np.minimum(generation[h], demand[h]))
         if h in prosumers else demand[h] for h in member_ids),
        np.zeros(n)
    )
    monthly["Netzbezugskosten Referenz [€]"] = ref_grid_ts * prices["p_grid"]
    monthly["Nettostromkosten Referenz [€]"] = (
        monthly["Netzbezugskosten Referenz [€]"]
        - monthly["Einspeiseerlöse Referenz [€]"]
    )
    monthly["Nettostromkosten ES [€]"] = (
        monthly["Netzbezugskosten ES [€]"]
        + monthly["Sharing-Bezugskosten ES [€]"]
        - monthly["P2P-Erlöse ES [€]"]
        - monthly["Sharing-Bonus ES [€]"]
    )
    monthly["Vorteil ES [€]"] = (
        monthly["Nettostromkosten Referenz [€]"]
        - monthly["Nettostromkosten ES [€]"]
    )
    monthly = monthly.resample("MS").sum()
    monthly.index = monthly.index.strftime("%Y-%m")
    annual = monthly.sum(numeric_only=True).to_frame("Gesamtjahr 2025")
    annual.index.name = "Kennzahl"
    e_shared = float(sum(v.sum() for v in sharing_out.values()))
    components = {
        "Prosumer-Vergütung": prices["p_sharing"],
        "Netzentgelte (reduziert)": prices["p_network_paid"],
        "Deutsche Umlagen und Abgaben": prices["p_levies_paid"],
        "Deutsche Stromsteuer": prices["p_tax_paid"],
        "Servicegebühr": prices["p_servicegebühr"],
    }
    df_payments = pd.DataFrame([
        {"Bestandteil": name, "Preis [ct/kWh]": price * 100,
         "Betrag [€]": e_shared * price}
        for name, price in components.items()
    ]).set_index("Bestandteil")
    bonus_cost = e_shared * prices.get("p_bonus", 0.0)
    network_relief = e_shared * prices["p_netzentgelte"] * prices["p_network_discount"]
    levy_relief = 0.0  # Deutsche Umlagen bleiben auch beim Sharing bestehen.
    tax_relief = 0.0   # Keine pauschale Stromsteuerbefreiung im Modell.
    e_generation = float(sum(v.sum() for v in generation.values()))
    e_self = float(sum(v.sum() for v in own.values()))
    e_surplus = float(sum(v.sum() for v in surplus.values()))
    e_grid = float(sum(v.sum() for v in grid.values()))
    e_demand = float(sum(v.sum() for v in demand.values()))
    pv_error = max(float(np.max(np.abs(generation[p] - own[p] - sharing_out[p] - surplus[p]))) for p in prosumers)
    member_error = max(float(np.max(np.abs(demand[h] - own[h] - sharing_in[h] - grid[h]))) for h in member_ids)
    sharing_error = float(np.max(np.abs(sum(sharing_out.values(), np.zeros(n)) - sum(sharing_in.values(), np.zeros(n)))))
    payment_error = abs(float(df_payments["Betrag [€]"].sum()) - e_shared * prices["p_sharing_consumer"])
    return {
        "timeseries": df_time, "monthly": monthly, "annual": annual, "member_timeseries": member_timeseries,
        "prosumer_pv_usage": pv_usage, "consumers": df_consumers,
        "prosumer": df_prosumer, "payments": df_payments,
        "generation": e_generation, "shared": e_shared, "self": e_self,
        "surplus": e_surplus, "grid": e_grid, "demand": e_demand,
        "autarky": 100 * (e_self + e_shared) / e_demand if e_demand else 0.0,
        "pv_utilization": 100 * (e_self + e_shared) / e_generation if e_generation else 0.0,
        "prosumer_savings": total_prosumer_savings,
        "consumer_savings": total_consumer_savings,
        "community_benefit": total_prosumer_savings + total_consumer_savings,
        "external_bonus_cost": bonus_cost,
        "network_relief": network_relief,
        "levy_relief": levy_relief,
        "tax_relief": tax_relief,
        "checks": {"PV-Bilanz": pv_error, "Mitglieder-Bilanz": member_error,
                   "Sharing-Bilanz": sharing_error, "Zahlungsbilanz": payment_error},
        "parameters": {
            "pv_capacities": pv_capacities.copy(),
            "allocation_keys_by_prosumer": {p: keys.copy() for p, keys in allocation_keys_by_prosumer.items()},
            "prices": prices.copy(), "N": n, "DT": DT,
        },
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
            "allocation_keys": {
                0: 20.0,
                1: 40.0,
                2: 25.0,
                3: 15.0
            }
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
            expanded=(config["role"] == "prosumer")
        ):

            # Rolle ändern
            role = st.selectbox(
                "Rolle",
                ["consumer", "prosumer"],
                index=(
                    1 if config["role"] == "prosumer" else 0
                ),
                key=f"role_{h}"
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

                recipients = list(st.session_state.members_config)

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

                own_alpha = new_keys.get(h, 0.0)
                st.caption(
                    f"Eigener PV-Zuteilungsschlüssel: {own_alpha:.1f} %. "
                    "Dies ist nicht der tatsächliche PV-Eigenverbrauch. "
                    "Dieser wird durch das Verbrauchsprofil begrenzt."
                )

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
            if st.button(
                "🗑️ Mitglied entfernen", key=f"remove_{h}"
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

    # Vorläufiger statischer Zuteilungsanspruch; keine Solver-Ergebnisse.
    # Der tatsächliche Eigenverbrauch hängt vom Verbrauchsprofil ab.
    allocation_preview = []
    for p in PROSUMERS:
        cfg = st.session_state.members_config[p]
        allocation_preview.append({
            "Prosumer": p,
            "PV-Leistung [kWp]": cfg["pv_kwp"],
            "Eigener Schlüssel [%]": cfg["allocation_keys"].get(p, 0.0),
            "Schlüssel anderer Mitglieder [%]": sum(
                v for c, v in cfg["allocation_keys"].items() if c != p
            )
        })

    # AB HIER BLEIBT DEIN BESTEHENDER CODE:
    with st.expander("Aufteilungsschlüssel – Übersicht", expanded=False):
        st.dataframe(pd.DataFrame(allocation_preview), hide_index=True)
        st.caption("Zuteilungsansprüche, keine simulierten Energieflüsse.")

    st.subheader("Preisparameter [€/kWh]")
    st.caption("Konstante Tarifannahmen für das gesamte Jahr; Jahressummen werden aus den Energiemengen berechnet.")

    # Der reguläre Strompreis wird aus den editierbaren Tarifbestandteilen
    # berechnet. Beim Restnetzbezug gelten keine Sharing-Vergünstigungen.
    p_supply = st.number_input(
        "Energiebeschaffung und Vertrieb (ohne Sharing)",
        value=0.135,
        min_value=0.0,
        step=0.005,
        format="%.3f",
        help="Modellannahme für den Energie- und Vertriebsanteil des regulären Netzstroms."
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
        "Stromsteuer (Deutschland)",
        value=0.0205,
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

    # Regulärer Netz-/Reststrompreis ohne Netzentgeltrabatte oder
    # EEG-Abgabenbefreiungen. Dieselben Komponenten werden nur einmal addiert.
    p_grid = p_supply + p_network + p_levies + p_tax + p_service

    p_feed_in = st.number_input(
        "Einspeisevergütung ohne Energy Sharing [€/kWh]",
        value=0.08,
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

    st.divider()
    st.subheader("Anreizmechanismen – Modelljahr 2025")
    st.caption(
        "Netznutzungsrabatte gelten ausschließlich für tatsächlich geteilte kWh, nicht für Reststrombezug oder Einspeisung und basieren auf der Gemeinschaftsform (lokale ESC, regionale ESC und überregionale ESC). "
    )
    incentives_enabled = st.radio(
        "Anreizmechanismen aktivieren?",
        options=[True, False],
        format_func=lambda enabled: "Ja – Energy Sharing mit zusätzlichen Anreizen" if enabled
            else "Nein – Energy Sharing ohne zusätzliche Anreize",
        horizontal=True,
        help="Bei Nein bleiben P2P-Vergütung und Sharing bestehen, aber es gelten "
             "keine Netznutzungsrabatte und kein Sharing-Bonus. Deutsche Steuern und Umlagen bleiben in beiden Fällen bestehen."
    )
    at_model = st.selectbox(
        "Netzgebiet / Gemeinschaftsform",
        list(AT_NETWORK_DISCOUNTS),
        index=1,
        disabled=not incentives_enabled,
    )
    at_discount = AT_NETWORK_DISCOUNTS[at_model] if incentives_enabled else 0.0
    bonus_input = st.number_input(
        "Hypothetischer Sharing-Bonus für Prosumer [€/geteilter kWh]",
        value=0.0, min_value=0.0, step=0.01, format="%.3f",
        disabled=not incentives_enabled,
        help="Kein allgemeiner gesetzlicher österreichischer Sharing-Bonus. "
             "Externer Fördertopf; Standard 0."
    )
    p_bonus = bonus_input if incentives_enabled else 0.0
    at_tariff = sharing_tariff(
        p_sharing, p_network, p_levies, p_tax, p_service,
        at_discount, p_bonus
    )
    p_es = at_tariff["p_sharing_consumer"]
    # Der Endpreis ist ein berechneter Tarif, kein zusätzlicher Kostenbestandteil.
    st.metric("Endpreis für Endverbraucher (Sharing)", f"{p_es:.3f} €/kWh")
    st.caption(
        f"Berechnung: P2P {p_sharing:.3f} + Netz {at_tariff['p_network_paid']:.3f} "
        f"+ Umlagen {at_tariff['p_levies_paid']:.3f} "
        f"+ Stromsteuer {at_tariff['p_tax_paid']:.3f} "
        f"+ Service {p_service:.3f} = {p_es:.3f} €/kWh. "
    )
    st.metric("Endpreis für Endverbraucher (ohne Sharing)", f"{p_grid:.3f} €/kWh")
    st.caption(
        f"Berechnung: Energie/Vertrieb {p_supply:.3f} + Netz {p_network:.3f} "
        f"+ Umlagen {p_levies:.3f} + Stromsteuer {p_tax:.3f} "
        f"+ Service {p_service:.3f} = {p_grid:.3f} €/kWh. "
        "Gilt für regulären Netz- und Reststrombezug ohne Sharing-Vergünstigungen."
    )
    if incentives_enabled:
        st.caption(f"Hypothetischer Netznutzungsrabatt: {at_discount:.0%}. Deutsche Stromsteuer und Umlagen bleiben unverändert.")
    else:
        st.info(
            "Ohne Anreize: 0 % Netznutzungsrabatt, Abgaben bleiben bestehen "
            "und 0 €/kWh Sharing-Bonus. Energy Sharing und P2P-Zahlungen bleiben aktiv."
        )
    p_residual = 0.0
    st.caption("Nicht geteilter PV-Restüberschuss wird im ES-Modell weiterhin unvergütet eingespeist (bestehende Modellannahme).")

    st.divider()

    run_button = st.button(
        "▶ Simulation starten",
        type="primary",
        use_container_width=True
    )

# ============================================================
# 4. SIMULATION AUSFÜHREN
# ============================================================

prices = {
    "p_grid": p_grid,
    "p_supply": p_supply,
    "p_sharing": p_sharing,
    "p_netzentgelte": p_network,
    "p_umlagen_abgaben": p_levies,
    "p_stromsteuer": p_tax,
    "p_servicegebühr": p_service,
    "p_feed_in": p_feed_in,
    "p_residual": p_residual,
    "p_sharing_consumer": p_es,
    **at_tariff
}

if run_button:

    if not allocation_valid:
        st.error("Bitte die Aufteilungsschlüssel korrigieren.")

    else:
        try:
            with st.spinner("Optimierung wird durchgeführt..."):
                results = run_simulation(
                    allocation_keys_by_prosumer,
                    prices,
                    pv_capacities,
                    st.session_state.members_config
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚡ Energiebilanz",
        "💶 Wirtschaftlichkeit",
        "🔍 Modellkontrolle",
        "⚙️ Simulationsparameter",
        "🎯 Anreizmechanismen"
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
        if len(r["timeseries"]) < 35040:
            st.warning(
                f"Die Eingabedaten enthalten {len(r['timeseries']):,} Viertelstundenwerte "
                "statt 35.040 für ein vollständiges Jahr. "
                "Bitte ersetze data_test/cons.csv, sun.csv und price.csv durch echte Jahresprofile "
                "(35.040 Werte, ohne Kopfzeile). Bis dahin wird nur der vorhandene Zeitraum gezeigt."
            )
        else:
            st.caption("Synthetisches Modelljahr 2025 – 35.040 Viertelstundenwerte; Zoom im Diagramm möglich.")

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

            view = st.radio(
                "Zeitauflösung",
                ["Monatssummen", "Tagessummen", "15 Minuten"],
                horizontal=True,
                key="energy_time_resolution"
            )
            if view == "Monatssummen":
                df_plot = df_selected.resample("MS").sum()
                unit = "Energie pro Monat [kWh]"
            elif view == "Tagessummen":
                df_plot = df_selected.resample("D").sum()
                unit = "Energie pro Tag [kWh]"
            else:
                df_plot = df_selected
                unit = "Energie je 15 Minuten [kWh]"

            fig = px.line(
                df_plot,
                x=df_plot.index,
                y=df_plot.columns,
                labels={
                    "x": "Uhrzeit",
                    "value": unit,
                    "variable": "Energiefluss"
                }
            )

            fig.update_xaxes(tickformat="%d.%m.%Y", title="Datum")
            fig.update_layout(xaxis_rangeslider_visible=True)

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

        st.subheader("PV-Erzeugung: Vergleich der Vermarktungsszenarien")
        st.caption(
            "Zwei alternative Szenarien für dieselbe PV-Erzeugung. "
            "Jeder Balken stellt eine vollständige, eigenständige Jahresbilanz dar; "
            "die Balken dürfen nicht addiert werden."
        )

        prosumer_df = r["prosumer"]
        prosumer_options = ["Alle Prosumer"] + list(prosumer_df.index)
        selected_prosumer = st.selectbox(
            "Prosumer auswählen",
            options=prosumer_options,
            index=0,
            key="chart_selected_prosumer"
        )
        if selected_prosumer == "Alle Prosumer":
            selected_rows = prosumer_df
        else:
            selected_rows = prosumer_df.loc[[selected_prosumer]]

        scenario_charts = [
            (
                "Einspeisevergütung (ohne Energy Sharing)",
                [
                    ("PV-Eigenverbrauch", "Referenz Eigenverbrauch [kWh]", "#2E86AB"),
                    ("Vergütete Netzeinspeisung", "Referenz Einspeisung [kWh]", "#7CB342"),
                ],
            ),
            (
                "Energy Sharing (ohne Restüberschussvergütung)",
                [
                    ("PV-Eigenverbrauch", "ES Eigenverbrauch [kWh]", "#2E86AB"),
                    ("Sharing-Abgabe", "ES Sharing-Abgabe [kWh]", "#F4A261"),
                    ("Unvergütete Netzeinspeisung", "ES Unvergütete Einspeisung [kWh]", "#A0A0A0"),
                ],
            ),
        ]
        # Gemeinsame Skala: Ein Balken je Prosumer und Szenario entspricht
        # der jeweiligen gesamten PV-Erzeugung (kWh/Jahr).
        max_generation = max(float(selected_rows["PV-Erzeugung [kWh]"].max()), 1.0)
        chart_cols = st.columns(2)
        for col, (scenario_title, components) in zip(chart_cols, scenario_charts):
            with col:
                st.markdown(f"**{scenario_title}**")
                fig = go.Figure()
                for label, column, color in components:
                    fig.add_trace(go.Bar(
                        name=label,
                        y=list(selected_rows.index),
                        x=selected_rows[column].tolist(),
                        orientation="h",
                        marker_color=color,
                        hovertemplate=(
                            "%{y}<br>" + label + ": %{x:,.2f} kWh"
                            + "<extra></extra>"
                        ),
                    ))
                fig.update_layout(
                    barmode="stack",
                    xaxis=dict(title="PV-Erzeugung [kWh/Jahr]", range=[0, max_generation * 1.08]),
                    yaxis=dict(title="", autorange="reversed"),
                    legend=dict(orientation="h", y=-0.25, x=0),
                    height=max(370, 95 * len(selected_rows) + 200),
                    margin=dict(l=10, r=10, t=15, b=80),
                )
                st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Bilanzprüfung je Prosumer: PV-Erzeugung = PV-Eigenverbrauch + "
            "vergütete Einspeisung (Einspeisevergütung) beziehungsweise "
            "PV-Eigenverbrauch + Sharing-Abgabe + unvergütete Einspeisung (Energy Sharing)."
        )

        st.subheader("Jahresbilanz 2025 – Energie und Kosten")
        st.dataframe(r["annual"].style.format("{:.2f}"), use_container_width=True)
        st.download_button(
            "Jahresbilanz als CSV herunterladen",
            data=r["annual"].to_csv().encode("utf-8-sig"),
            file_name="energy_sharing_jahresbilanz_2025.csv", mime="text/csv"
        )

        st.subheader("Monatliche Energie- und Zahlungsbilanz")
        st.dataframe(r["monthly"].style.format("{:.2f}"), use_container_width=True)
        st.download_button(
            "Monatswerte als CSV herunterladen",
            data=r["monthly"].to_csv().encode("utf-8"),
            file_name="energy_sharing_monatswerte_2025.csv", mime="text/csv"
        )

        st.subheader("Energiebilanz der Consumer – Gesamtjahr 2025")

        st.dataframe(
            r["consumers"][[
                "Verbrauch [kWh]",
                "Sharing [kWh]",
                "Netzbezug [kWh]"
            ]].style.format("{:.3f}"),
            use_container_width=True
        )

        st.subheader("Energiebilanz der Gemeinschaft – Gesamtjahr 2025")

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

        st.subheader("Wirtschaftlicher Vergleich – Gesamtjahr 2025")
        st.caption("Alle Euro-Beträge sind Jahressummen aus 35.040 Viertelstunden. Tarife sind konstante Annahmen, keine Börsenpreise.")

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

        st.subheader("Prosumer – Vergleich der Vermarktungsmodelle")
        st.caption("PV-Eigenverbrauch bedeutet Deckung durch die eigene PV-Anlage. Eigener Strombedarf umfasst PV-Eigenverbrauch, Sharing-Bezug und Reststrombezug.")

        for prosumer_id, row in r["prosumer"].iterrows():
            st.markdown(f"#### {prosumer_id}")
            prosumer_energy = pd.DataFrame({
                "Einspeisevergütung": {
                    "PV-Erzeugung": row["PV-Erzeugung [kWh]"],
                    "Eigener Strombedarf": row["Eigenbedarf [kWh]"],
                    "Davon: PV-Eigenverbrauch (eigene PV)": row["Referenz Eigenverbrauch [kWh]"],
                    "Davon: Sharing-Bezug": 0.0,
                    "Davon: Reststrombezug (Netz)": row["Referenz Netzbezug [kWh]"],
                    "Sharing-Abgabe an andere Mitglieder": 0.0,
                    "PV-Netzeinspeisung": row["Referenz Einspeisung [kWh]"],
                },
                "Energy Sharing": {
                    "PV-Erzeugung": row["PV-Erzeugung [kWh]"],
                    "Eigener Strombedarf": row["Eigenbedarf [kWh]"],
                    "Davon: PV-Eigenverbrauch (eigene PV)": row["ES Eigenverbrauch [kWh]"],
                    "Davon: Sharing-Bezug": row["ES Sharing-Bezug [kWh]"],
                    "Davon: Reststrombezug (Netz)": row["ES Netzbezug [kWh]"],
                    "Sharing-Abgabe an andere Mitglieder": row["ES Sharing-Abgabe [kWh]"],
                    "PV-Netzeinspeisung": row["ES Unvergütete Einspeisung [kWh]"],
                },
            })
            st.markdown("**Energiebilanz [kWh/Jahr]**")
            st.dataframe(prosumer_energy.style.format("{:,.2f}"), use_container_width=True)

            prosumer_costs = pd.DataFrame({
                "Einspeisevergütung": {
                    "Reststrombezugskosten": row["Referenz Netzbezugskosten [€]"],
                    "Sharing-Bezugskosten": 0.0,
                    "Einspeiseerlöse": row["Referenz Einspeiseerlöse [€]"],
                    "P2P-Erlöse": 0.0,
                    "Nettostromkosten": row["Referenz Nettostromkosten [€]"],
                },
                "Energy Sharing": {
                    "Reststrombezugskosten": row["ES Netzbezugskosten [€]"],
                    "Sharing-Bezugskosten": row["ES Sharing-Bezugskosten [€]"],
                    "Einspeiseerlöse": row["ES Restüberschuss-Erlöse [€]"],
                    "P2P-Erlöse": row["ES P2P-Erlöse [€]"],
                    "Hypothetischer Sharing-Bonus": row["ES Sharing-Bonus [€]"],
                    "Nettostromkosten": row["ES Nettostromkosten [€]"],
                },
            })
            st.markdown("**Wirtschaftlichkeit [€/Jahr]**")
            st.dataframe(prosumer_costs.style.format("{:,.2f} €"), use_container_width=True)
            st.metric("Vorteil durch Energy Sharing gegenüber Einspeisevergütung", f"{row['Vorteil ES [€]']:+,.2f} €")
            st.divider()

        st.subheader("Consumer – Vergleich der Versorgungsmodelle")
        st.caption("Consumer besitzen keine eigene PV-Anlage. Ihr Strombedarf wird ohne Energy Sharing vollständig durch Reststrom aus dem Netz gedeckt; mit Energy Sharing teilweise durch Sharing-Bezug.")

        for consumer_id, row in r["consumers"].iterrows():
            st.markdown(f"#### {consumer_id}")
            consumer_energy = pd.DataFrame({
                "Einspeisevergütung (ohne Sharing)": {
                    "Eigener Strombedarf": row["Verbrauch [kWh]"],
                    "Davon: PV-Eigenverbrauch (eigene PV)": 0.0,
                    "Davon: Sharing-Bezug": 0.0,
                    "Davon: Reststrombezug (Netz)": row["Einspeisevergütung Reststrombezug [kWh]"],
                },
                "Energy Sharing": {
                    "Eigener Strombedarf": row["Verbrauch [kWh]"],
                    "Davon: PV-Eigenverbrauch (eigene PV)": row["PV-Eigenverbrauch [kWh]"],
                    "Davon: Sharing-Bezug": row["Sharing-Bezug [kWh]"],
                    "Davon: Reststrombezug (Netz)": row["Reststrombezug [kWh]"],
                },
            })
            st.markdown("**Energiebilanz [kWh/Jahr]**")
            st.dataframe(consumer_energy.style.format("{:,.2f}"), use_container_width=True)

            consumer_costs = pd.DataFrame({
                "Einspeisevergütung (ohne Sharing)": {
                    "Reststrombezugskosten": row["Einspeisevergütung Netzbezugskosten [€]"],
                    "Sharing-Bezugskosten": 0.0,
                    "Nettostromkosten": row["Ohne ES [€]"],
                },
                "Energy Sharing": {
                    "Reststrombezugskosten": row["ES Reststrombezugskosten [€]"],
                    "Sharing-Bezugskosten": row["ES Sharing-Bezugskosten [€]"],
                    "Nettostromkosten": row["Mit ES [€]"],
                },
            })
            st.markdown("**Wirtschaftlichkeit [€/Jahr]**")
            st.dataframe(consumer_costs.style.format("{:,.2f} €"), use_container_width=True)
            st.metric("Ersparnis durch Energy Sharing", f"{row['Ersparnis [€]']:+,.2f} €")
            st.divider()

        st.subheader("Monatlicher Kostenvergleich – 2025")
        monthly_costs = r["monthly"][[
            "Nettostromkosten Referenz [€]", "Nettostromkosten ES [€]"
        ]]
        st.line_chart(monthly_costs)
        st.caption("Monatssummen der Haushalts-Nettostromkosten; die Jahreswerte stehen in den Tabellen oben.")

        st.subheader("Zahlungsbilanz Energy Sharing – Gesamtjahr 2025")

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
            "p_grid": "Endpreis ohne Sharing",
            "p_sharing": "P2P-Vergütung",
            "p_sharing_consumer": "Sharing-Endpreis",
            "p_netzentgelte": "Netzentgelte",
            "p_umlagen_abgaben": "Umlagen und Abgaben",
            "p_stromsteuer": "Stromsteuer",
            "p_servicegebühr": "Servicegebühr",
            "p_feed_in": "Einspeisevergütung",
            "p_residual": "Restüberschussvergütung",
            "p_bonus": "Hypothetischer Sharing-Bonus",
            "p_network_discount": "Netznutzungsrabatt (Anteil)",
            "p_network_paid": "Netznutzungsentgelt nach Rabatt",
            "p_levies_paid": "Deutsche Umlagen beim Sharing",
            "p_tax_paid": "Deutsche Stromsteuer beim Sharing"
        }

        df_prices = pd.DataFrame([
            {
                "Preisbestandteil": price_names.get(key, key),
                "Preis [ct/kWh]": value * 100
            }
            for key, value in params["prices"].items() if isinstance(value, (int, float)) and not isinstance(value, bool)
        ])

        st.dataframe(
            df_prices.style.format({
                "Preis [ct/kWh]": "{:.2f}"
            }),
            hide_index=True,
            use_container_width=True
        )
    # --------------------------------------------------------
    # TAB 5: ANREIZMECHANISMEN / SENSITIVITÄT
    # --------------------------------------------------------
    with tab5:
        st.subheader("Anreizmechanismen – Modelljahr 2025")
        st.caption("Die Energiemengen sind bei dieser Preissensitivität unverändert; es werden nur die hypothetischen finanziellen Effekte gezeigt.")
        st.caption("Aktive Anreizmechanismen: " + ("Ja" if incentives_enabled else "Nein") +
                   ". Die folgenden Sensitivitäten zeigen hypothetische Alternativen und ändern nicht die aktuelle Simulation.")
        pp = r["parameters"]["prices"]
        total_shared = r["shared"]
        total_bonus = r["external_bonus_cost"]
        st.markdown("### Regulatorische Entlastungen und zusätzliche Förderungen – Jahresbilanz")
        st.caption(
            "Die Beträge beziehen sich auf die tatsächlich innerhalb der Gemeinschaft "
            "geteilten und verbrauchten kWh des Modelljahres 2025. "
            "Regulatorische Entlastungen senken die Kosten der Sharing-Bezieher; "
            "der optionale Sharing-Bonus ist eine zusätzliche externe Zahlung an Prosumer."
        )
        st.metric("Tatsächlich geteilte Energie", f"{total_shared:,.0f} kWh/Jahr")
        st.caption(f"Netzentgeltrabatt der Simulation: {pp['p_network_discount']:.0%}")

        st.markdown("**A. Regulatorische Entlastungen (Vorteil für Sharing-Bezieher)**")
        st.caption(
            "Jeder Consumer und jeder Sharing-beziehende Prosumer wird einzeln ausgewiesen. "
            "Nur auf tatsächlich bezogene Sharing-kWh wird der hypothetische "
            "Netzentgeltrabatt nach österreichischem Vorbild angewendet. "
            "Deutsche Umlagen, Abgaben und Stromsteuer bleiben im Modell unverändert."
        )
        network_discount_ct = (
            pp["p_netzentgelte"] * pp["p_network_discount"] * 100.0
        )
        # Umlagen und Abgaben sind im Eingabemenü ein gemeinsamer Preisparameter.
        # Ihre einzelnen absoluten Anteile sind deshalb nicht getrennt bekannt.
        # Die Entlastung beträgt bei beiden ausdrücklich 0 EUR.
        relief_totals = []
        for member_id, member_df in sorted(r["member_timeseries"].items()):
            shared_kwh = float(member_df["Energy Sharing"].sum())
            if shared_kwh <= 1e-9:
                continue
            role = "Prosumer" if f"Prosumer {member_id}" in r["prosumer"].index else "Consumer"
            member_name = f"{role} {member_id}"
            st.markdown(f"**{member_name}**")
            st.caption(f"Sharing-Bezug: {shared_kwh:,.2f} kWh/Jahr")
            member_reliefs = [
                ("Reduziertes Netzentgelt", network_discount_ct),
                ("Umlage", 0.0),
                ("Abgabe", 0.0),
                ("Stromsteuer", 0.0),
            ]
            member_table = pd.DataFrame([
                {"Anreiz": name, "Entlastung [ct/kWh]": rate,
                 "Entlastung [€/Jahr]": shared_kwh * rate / 100.0}
                for name, rate in member_reliefs
            ] + [{
                "Anreiz": "SUMME",
                "Entlastung [ct/kWh]": sum(rate for _, rate in member_reliefs),
                "Entlastung [€/Jahr]": shared_kwh * sum(rate for _, rate in member_reliefs) / 100.0,
            }])
            st.dataframe(member_table.style.format({
                "Entlastung [ct/kWh]": "{:.3f}",
                "Entlastung [€/Jahr]": "{:,.2f}",
            }), hide_index=True, use_container_width=True)
            relief_totals.append({"Mitglied": member_name,
                                  "Sharing-Bezug [kWh]": shared_kwh,
                                  "Entlastung [€]": shared_kwh * network_discount_ct / 100.0})
        if relief_totals:
            st.metric("Gesamte regulatorische Entlastung der Sharing-Bezieher",
                      f"{sum(x['Entlastung [€]'] for x in relief_totals):,.2f} €/Jahr")
        else:
            st.info("Kein Sharing-Bezug vorhanden; es entstehen keine Entlastungen.")
        st.caption(
            "Umlagen und Abgaben sind im Eingabemenü ein gemeinsamer Tarifparameter. "
            "Die hier separat dargestellten Entlastungen betragen jeweils 0 €, "
            "ebenso die Stromsteuerentlastung. Nur der Netzentgeltrabatt ist eine "
            "hypothetische Szenarioannahme nach österreichischem Vorbild."
        )

        st.markdown("**B. Vorteil für Prosumer – Erlöse und Vergleich mit Einspeisevergütung**")
        st.caption("Je Prosumer zwei kompakte Tabellen: Erlöse und vollständiger Kostenvergleich. "
                   "Die Szenarien sind Alternativen und werden nicht addiert.")
        for prosumer_name, prosumer in r["prosumer"].iterrows():
            st.markdown(f"#### {prosumer_name}")
            es_p2p = float(prosumer["ES P2P-Erlöse [€]"])
            es_bonus = float(prosumer["ES Sharing-Bonus [€]"])
            ref_revenue = float(prosumer["Referenz Einspeiseerlöse [€]"])
            es_revenue = es_p2p + es_bonus + float(prosumer["ES Restüberschuss-Erlöse [€]"])
            st.markdown("**Erlösvergleich [€/Jahr]**")
            revenues = pd.DataFrame({
                "Position": ["Einspeisevergütung", "P2P-Erlöse", "Externer Sharing-Bonus", "Gesamterlöse", "Erlösdifferenz ES – Referenz"],
                "Ohne Sharing [€]": [ref_revenue, 0.0, 0.0, ref_revenue, None],
                "Energy Sharing [€]": [0.0, es_p2p, es_bonus, es_revenue, es_revenue-ref_revenue],
            })
            st.dataframe(revenues.style.format({"Ohne Sharing [€]": "{:,.2f}",
                                                "Energy Sharing [€]": "{:,.2f}"}, na_rep="–"),
                         hide_index=True, use_container_width=True)
            st.markdown("**Wirtschaftlicher Gesamtvergleich [€/Jahr]**")
            costs = pd.DataFrame({
                "Position": ["Netzbezugskosten", "Sharing-Bezugskosten", "Abzüglich Erlöse", "Nettostromkosten"],
                "Einspeisevergütung [€]": [
                    float(prosumer["Referenz Netzbezugskosten [€]"]), 0.0,
                    -ref_revenue, float(prosumer["Referenz Nettostromkosten [€]"])],
                "Energy Sharing [€]": [
                    float(prosumer["ES Netzbezugskosten [€]"]),
                    float(prosumer["ES Sharing-Bezugskosten [€]"]),
                    -es_revenue, float(prosumer["ES Nettostromkosten [€]"])],
            })
            st.dataframe(costs.style.format({"Einspeisevergütung [€]": "{:,.2f}",
                                             "Energy Sharing [€]": "{:,.2f}"}),
                         hide_index=True, use_container_width=True)
            st.metric("Wirtschaftlicher Vorteil durch Energy Sharing",
                      f"{float(prosumer['Vorteil ES [€]']):+,.2f} €/Jahr")
            st.divider()
        st.caption("Erlöse und Nettostromkosten sind unterschiedliche Kennzahlen: "
                   "Der Gesamtvergleich berücksichtigt auch den veränderten Eigenverbrauch "
                   "sowie den Netz- und Sharing-Bezug.")

        st.markdown("**C. Zusammenfassung und wirtschaftliche Einordnung**")
        total_network = sum(x["Entlastung [€]"] for x in relief_totals)
        total_bonus = float(r["external_bonus_cost"])
        summary_table = pd.DataFrame({
            "Kennzahl": [
                "Netzentgeltentlastung", "Umlagen-/Abgabenentlastung", "Stromsteuerentlastung",
                "Gesamte regulatorische Entlastung", "Zusätzlicher Sharing-Bonus",
                "Wirtschaftlicher Vorteil Prosumer", "Wirtschaftlicher Vorteil Consumer",
                "Wirtschaftlicher Vorteil der Gemeinschaft"],
            "Relevant für": [
                "Sharing-beziehende Consumer und Prosumer", "Sharing-Bezieher (hier keine Befreiung)",
                "Sharing-Bezieher (hier keine Befreiung)", "Alle Sharing-Bezieher",
                "Prosumer (Erlös); externer Fördergeber (Kosten)", "Prosumer", "Consumer",
                "Prosumer und Consumer"],
            "Wert [€/Jahr]": [
                total_network, 0.0, 0.0, total_network, total_bonus,
                float(r["prosumer_savings"]), float(r["consumer_savings"]),
                float(r["community_benefit"])],
        })
        st.dataframe(summary_table.style.format({"Wert [€/Jahr]": "{:,.2f}"}),
                     hide_index=True, use_container_width=True)
        st.caption(
            "Die regulatorische Entlastung ist bereits in den Sharing-Bezugskosten "
            "und damit im wirtschaftlichen Vorteil enthalten; nicht nochmals addieren. "
            "Der P2P-Preis ist eine Zahlung innerhalb der Gemeinschaft. Der Sharing-Bonus "
            "ist eine externe Zahlung an Prosumer und verursacht externe Förderkosten. "
            "Der Gemeinschaftsvorteil berücksichtigt auch Eigenverbrauch und entgangene Einspeiseerlöse."
        )
        if not incentives_enabled:
            st.caption("Zusätzliche Anreize deaktiviert: Netzentgeltrabatt und Sharing-Bonus betragen 0.")
        if total_shared <= 0:
            st.warning("Es wurde keine Energie geteilt; kWh-bezogene Entlastungen und Bonuszahlungen entfallen.")

        st.markdown("**Sensitivität des P2P-Preises**")
        p2p_values = np.linspace(0.04, 0.25, 22)
        base_p2p = pp["p_sharing"]
        sensitivity = pd.DataFrame({
            "P2P-Preis [ct/kWh]": p2p_values * 100,
            "Prosumer-Vorteil [€/Jahr]": r["prosumer_savings"] + (p2p_values - base_p2p) * total_shared,
            "Consumer-Vorteil [€/Jahr]": r["consumer_savings"] - (p2p_values - base_p2p) * total_shared,
        }).set_index("P2P-Preis [ct/kWh]")
        sensitivity["Gemeinschaftsvorteil [€/Jahr]"] = sensitivity.sum(axis=1)
        st.line_chart(sensitivity)
        st.caption("Der P2P-Preis verschiebt den Vorteil zwischen Prosumern und Consumern. Bei fixen Energiemengen bleibt die Summe unverändert.")
        st.markdown("**Vergleich hypothetischer Netzentgeltrabatte nach österreichischem Vorbild**")
        comparisons = []
        for name, discount in AT_NETWORK_DISCOUNTS.items():
            scenario_tariff = sharing_tariff(
                pp["p_sharing"], pp["p_netzentgelte"], pp["p_umlagen_abgaben"],
                pp["p_stromsteuer"], pp["p_servicegebühr"], discount,
                pp["p_bonus"]
            )
            consumer_delta = (pp["p_sharing_consumer"] - scenario_tariff["p_sharing_consumer"]) * total_shared
            comparisons.append({
                "Gemeinschaftsform": name,
                "Netzentgeltreduktion [%]": discount * 100,
                "Sharing-Endpreis [ct/kWh]": scenario_tariff["p_sharing_consumer"] * 100,
                "Prosumer-Vorteil [€/Jahr]": r["prosumer_savings"],
                "Consumer-Vorteil [€/Jahr]": r["consumer_savings"] + consumer_delta,
                "Gemeinschaftsvorteil [€/Jahr]": r["community_benefit"] + consumer_delta,
            })
        comparison_df = pd.DataFrame(comparisons).set_index("Gemeinschaftsform")
        st.dataframe(comparison_df.style.format("{:,.2f}"), use_container_width=True)
        st.caption("Hypothetischer Vergleich: deutsche Strompreisbestandteile, österreichische Netzentgeltrabatte als Szenarioannahme. Keine geltende deutsche Netzentgeltvergünstigung.")
        st.markdown("**Hypothetischer externer Sharing-Bonus**")
        bonus_values = np.linspace(0, 0.10, 11)
        bonus_sens = pd.DataFrame({
            "Bonus [ct/kWh]": bonus_values * 100,
            "Prosumer-Vorteil [€/Jahr]": r["prosumer_savings"] + (bonus_values - pp["p_bonus"]) * total_shared,
            "Consumer-Vorteil [€/Jahr]": np.full(len(bonus_values), r["consumer_savings"]),
            "Externe Bonuskosten [€/Jahr]": bonus_values * total_shared,
        }).set_index("Bonus [ct/kWh]")
        st.line_chart(bonus_sens)
        st.caption("Forschungs-Szenario, keine bestehende pauschale österreichische Förderung.")
