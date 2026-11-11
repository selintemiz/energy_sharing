# Synthetische Jahresprofile 2025 – Herkunft und Annahmen

## Transparenz
Die Profile in `data_test/` sind **synthetisch modellierte Szenariodaten** und **keine heruntergeladenen oder gemessenen Zeitreihen** der ENTSO-E Transparency Platform, PVGIS oder BDEW. Sie sind für einen nachvollziehbaren ersten Jahrestest gedacht, nicht für wissenschaftlich belastbare Marktpreis- oder Ertragsprognosen.

## Zeitskala
Kalenderjahr 2025, 365 Tage, 35.040 Viertelstunden, durchgehende lokale Modellzeit ohne Sommerzeitumstellung. `cons.csv` enthält vier Zeilen mit jeweils 35.040 kWh-Werten. `sun.csv` enthält 35.040 Werte in kWh je kWp und Viertelstunde. `price.csv` enthält 35.040 **synthetische** Großhandels-Preisindikatoren in EUR/kWh, die in der aktuellen App **nicht** für die Tarife verwendet werden.

## Modellannahmen
- PV: astronomisch inspirierter Sonnenstand für ~50,8° N, Südausrichtung idealisiert, tägliche Bewölkungsfaktoren und reproduzierbares Rauschen, normiert auf **950 kWh/kWp pro Jahr**. Keine lokale PVGIS-Simulation, keine Verschattung/Wechselrichtermodellierung.
- Verbrauch: H0-typische Tagesmuster (Morgen- und Abendspitzen), höhere Winterlast, Wochenendunterschiede, Haushaltsstreuung und reproduzierbares Rauschen. **Keine amtlichen BDEW-H0-Originalkoeffizienten**. Jahresverbräuche Mitglieder 0–3: **3.600 / 2.700 / 4.200 / 3.100 kWh**.
- Preisindikator: synthetische Großhandelszeitreihe mit Tages-/Jahresschwankungen, kein ENTSO-E-Export. **Finanzielle Ergebnisse** werden stattdessen mit den konstanten Sidebar-Tarifen (€/kWh) aus den Jahressummen berechnet.
- Statische Energy-Sharing-Zuteilung: Nicht genutzte Anteile werden physisch eingespeist, aber im Sharing-Modell nicht vergütet. Referenzmodell vergütet die PV-Überschüsse mit `p_feed_in` (Standard 0,08 €/kWh).
- Keine Batteriespeicher, Netzrestriktionen, Steuer-/Abgabenänderungen oder zeitvariablen Endkundenpreise. Die direkte Rechenroutine ersetzt für diesen Szenariolauf den Pyomo-Solver.

## Referenzquellen für eine spätere datenbasierte Version
- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) – tatsächliche aggregierte Erzeugungs- und Marktzeitreihen, **keine individuellen Haushaltslastprofile**.
- [EU JRC PVGIS](https://re.jrc.ec.europa.eu/pvg_tools/en/) – standortabhängige PV-Ertragszeitreihen.
- [BDEW](https://www.bdew.de/) – Standardlastprofil H0 und zugehörige Methodik (Originalparameter gesondert beziehen).

## Validierung
Test mit Prosumer 2 und vier Mitgliedern: 35.040 Zeitschritte, 12 Monatszeilen, Bilanzfehler nahe null. Python-Syntax geprüft. Streamlit-End-to-End-Lauf in dieser Umgebung nicht möglich (Pyomo nicht installiert).
