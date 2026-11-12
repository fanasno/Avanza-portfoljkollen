# Historikgranskning och beslut om framåtblick · 11 november 2026

## Beslut

Användaren valde att ta bort framåtblicken från demon och fokusera på historiska jämförelser. Framtidsflik, datumknappar, Monte Carlo-beskrivningar och prognosresonemang visas därför inte längre. Den tidigare fristående beräkningsmotorn finns kvar för regressionstester; den anropas inte från demon.

## Den tidigare metoden

Framåtblicken drog gemensamma sammanhängande block om normalt tio dagsavkastningar från det valda historikfönstret, för instrument och valuta tillsammans. Blocken sammanfogades till 1 000 förlopp och följdes av strategi-, avgifts- och skatteberäkningar. Koden tillät så lite som två gemensamma dagsavkastningar. Samma korta underlag kunde alltså återanvändas många gånger utan att fler historiska observationer tillfördes.

## Historik som används nu

Den historiska jämförelsen återspelar vald periods prisrörelser i SEK. Den estimerar ingen framtida genomsnittsavkastning. Riskanalysen har ett separat historikval; det ändrar inte jämförelsens startdatum. Varje strategi använder samma gemensamma tillgängliga kursperiod. Startdatum efter senare fondstart, källornas verkliga slutdatum och antal gemensamma dagsavkastningar redovisas.

En tabell visar första och senast rapporterade kursdag, antal kursobservationer och källa för varje valt instrument. Fonder tilldelas ingen historik före fondstart. Instrument i målbilden med nuvarande innehav noll kortar inte riskunderlaget för den nuvarande portföljen.

## Hämtning verifierad 11 november 2026

- Alla 24 Avanza-fonder kunde hämtas med daglig, ursprunglig NAV och kontrollerat fond-ID.
- Avanza Zero gav 1 256 observationer från 2021-11-11 till 2026-11-10.
- Den kortaste hämtade fondhistoriken var Avanza Sweden SEK A: 118 observationer från 2026-05-28 till 2026-11-10.
- Standardportföljens referens-ETF:er, aktier och valuta kunde hämtas från Yahoo Finance. Antal observationer och slutdatum varierar mellan marknader och valuta; en senare valutadag förlänger inte fondens rapporterade historik.

## Datakällans beteende

Marknadsdata är standard, även vid migrering av äldre sessioner. Verifierade verkliga serier sparas per instrument och period. Vid hämtningsfel används enbart komplett verifierad historik för samtliga efterfrågade instrument, med datum och cachemärkning. Saknas sådan historik avbryts analysen med ett tydligt fel. Ingen automatisk övergång till syntetiska priser finns kvar. Testläget Exempeldata är ett separat uttryckligt val.
