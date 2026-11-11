# Österreichische Anreizmechanismen – Modelljahr 2025

## Quellen und Geltungsbereich

- Koordinationsstelle Energiegemeinschaften: https://energiegemeinschaften.gv.at/formen-von-energiegemeinschaften/
- Übersicht 2025 zu Elektrizitätsabgabe, Förderbeitrag und EEG: https://energiegemeinschaften.gv.at/2025-das-jahr-der-erneuerbare-energie-gemeinschaften/
- FAQs zu Förderungen: https://energiegemeinschaften.gv.at/faqs/
- Rechtsänderungen ab Oktober 2026 und erwartete Netzentgeltverordnung ab 2027: https://energiegemeinschaften.gv.at/detailwissen/
- Tarifgestaltung und unterschiedliche Steuerbehandlung: https://energiegemeinschaften.gv.at/tarifgestaltung/

### Netznutzung für tatsächlich innerhalb der Gemeinschaft verbrauchte kWh

- Lokale EEG (NE 6/7): 57 % Rabatt auf den **arbeitsbezogenen Netznutzungspreis**.
- Regionale EEG (NE 6/7): 28 % Rabatt.
- Regionale EEG (NE 4/5): 64 % Rabatt.
- Überregionale BEG im Rechtsrahmen 2025: kein Rabatt.

Es wird **nicht** der gesamte Endkundenstrompreis um diese Prozentsätze reduziert. Auch andere Netzkomponenten wie Netzverlustentgelt und fixe Leistungspreise werden nicht pauschal reduziert. Reststrom aus dem öffentlichen Netz wird zum normalen Netzbezugstarif abgerechnet.

### Abgaben

- Bei 2025 EEG-intern verbrauchter Energie: Entfall der Elektrizitätsabgabe und des Erneuerbaren-Förderbeitrags.
- Elektrizitätsabgabe 2025: 1,5 ct/kWh als Standardwert der App.
- Für den variablen Erneuerbaren-Förderbeitrag werden als **vereinfachte Modellannahme** 0,737 ct/kWh Netznutzung + 0,059 ct/kWh Netzverlust = 0,796 ct/kWh angesetzt; diese Komponente ist als Teil des editierbaren Parameters 'Umlagen und Abgaben' modelliert und wird **nicht zusätzlich** aufgeschlagen.
- Die 7 ct/kWh im Parameter 'Umlagen und Abgaben' sind ein **synthetischer pauschaler Modelltarif**, keine konkrete österreichische Abgabenrechnung. Bei einer tatsächlichen Tarifstudie muss dieser Parameter nach Komponenten und Netzgebiet aufgelöst werden.
- Die Haushaltsstrompreise, P2P-Preise, Netzarbeitspreise und Servicekosten sind editierbare Modellannahmen und nicht amtliche Tarife.

### Sharing-Bonus

Es ist **kein allgemeiner, fester österreichischer Sharing-Bonus pro geteilter kWh** dokumentiert. Förderprogramme für Aufbau/Digitalisierung von Energiegemeinschaften sowie mögliche Marktprämien für bestimmte Überschussmengen sind davon zu unterscheiden. Der Sharing-Bonus ist daher als **hypothetischer externer Zuschuss** mit Default 0 ct/kWh implementiert; Kosten werden separat ausgewiesen. Der Bonus fließt dem Prosumer für tatsächlich geteilte kWh zu und erhöht **nicht** den Sharing-Endpreis des Consumers.

### Wirtschaftliche Abrechnung

- Ohne ES: Prosumer deckt zuerst seinen Verbrauch mit der eigenen PV; Überschuss erhält die eingestellte Einspeisevergütung. Consumer deckt vollständig mit Netzstrom.
- Mit ES: PV wird statisch nach Viertelstunden-Aufteilungsschlüsseln zugeteilt; Prosumer-Eigenverbrauch, Sharing, Netzbezug und Überschuss werden bilanziert. Der ES-Restüberschuss bleibt gemäß bisheriger Modellannahme unvergütet.
- ES-Consumer-Endpreis = P2P-Preis + rabattierter Netznutzungs-Arbeitspreis + nicht befreite Umlagen + ggf. Elektrizitätsabgabe + Servicegebühr.
- ES-Prosumer-Erlös = P2P-Preis * geteilte kWh + hypothetischer Bonus * geteilte kWh.
- Externe Kosten des Bonus, Netzentgeltentlastung und Abgabenbefreiung werden separat ausgewiesen. Ein P2P-Preiswechsel allein verschiebt Zahlungen zwischen Mitgliedern.
- Sensitivitätsanalysen halten die 15-Minuten-Energieflüsse konstant. Dynamische Verhaltensreaktionen, Speicher, Flexibilitätsaktivierung und erneute Allokationsoptimierung sind nicht enthalten.
- Das synthetische Profiljahr 2025 hat 35.040 Viertelstunden und modelliert keine Sommer-/Winterzeitumstellung.

### Einschränkungen

Keine rechtsverbindliche Tarifberechnung. Umsatzsteuer, individuelle Netzentgeltbestandteile, Netzzonen, Betreiberkosten, Leistungs-/Grundpreise und künftige regulatorische Änderungen sind nicht vollständig modelliert. Für den österreichischen Rechtsrahmen ab Oktober 2026/2027 sind gesonderte Szenarien nötig.
