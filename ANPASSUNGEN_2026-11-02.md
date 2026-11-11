# Änderungen am Energy Sharing Simulator

- `app.py` verwendet für das statische Energy Sharing eine direkte, deterministische Viertelstunden-Zuteilung. Die bestehende Pyomo-Klasse `SolverStaticSharing` bleibt als Originalcode erhalten, wird von dieser App aber nicht mehr aufgerufen. Speicher und Netzverluste sind in dieser vereinfachten Variante nicht berücksichtigt.
- Prosumer können beliebige Mitglieder sein; mehrere Prosumer sind möglich. Für jede PV-Anlage müssen die Aufteilungsschlüssel über alle Mitglieder 100 % ergeben.
- Zunächst erhält jeder Prosumer seinen eigenen zugeteilten Anteil, begrenzt durch seinen Bedarf. Die Zuteilung an andere Mitglieder ist auf deren verbleibenden Bedarf begrenzt. Bei mehreren PV-Anlagen werden die Ansprüche in aufsteigender Prosumer-ID abgearbeitet; eine gleichzeitige anteilige Kürzung wird nicht vorgenommen.
- Nicht genutzte PV-Zuteilungen fallen an die jeweilige Erzeugungsanlage zurück und werden eingespeist. Die Einspeisevergütung im Energy-Sharing-Modell ist **0 €/kWh**.
- Referenzmodell: direkte Eigennutzung, Rest mit der konfigurierbaren Einspeisevergütung (standardmäßig 0,08 €/kWh). Energy-Sharing-Modell: P2P-Vergütung (standardmäßig 0,13 €/kWh) für tatsächliche Sharing-Abgabe, keine Vergütung für Restüberschuss.
- **Jahreszeitreihen:** Die mitgelieferten `data_test`-Profile enthalten nur 96 Viertelstundenwerte. Die Anwendung erzeugt daraus ausdrücklich **kein erfundenes Jahr**. Für eine echte Jahresansicht `data_test/cons.csv` (eine Zeile pro Mitglied), `data_test/sun.csv` (eine Spalte) und `data_test/price.csv` (eine Spalte) durch konsistente 35.040-Werte-Profile für 2026 ersetzen. Das Diagramm wechselt dann automatisch auf eine Jahresdatumsachse mit Zoom.
- Die Daten werden wie bisher als Energie **je Viertelstunde in kWh** interpretiert. PV-Kapazität wird mit dem vorhandenen PV-Profil multipliziert.

## Ausführen

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install streamlit
python3 -m streamlit run app.py
```

Die App benötigt für die vereinfachte statische Zuteilung keinen LP-Solver. Für die übrigen Skripte im Repository gelten weiterhin deren eigene Abhängigkeiten.
