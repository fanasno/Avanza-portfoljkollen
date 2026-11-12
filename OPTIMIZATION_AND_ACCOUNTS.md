# Kunddemo, informationsytor och historisk optimering

## Två sammanhang

Lär dig mer använder utbildningsportföljen. **Mitt konto · demo** använder ett markerat Demo-ISK, Demo-AF eller en CSV-import. Det är ingen bankinloggning. En riktig integration behöver autentiserade tjänster från Avanza och en separat bedömning av produktens rådgivningsroll.

`account_model.py` ger samma datastruktur för demokonton och import: instrumentidentiteter, antal, kontotyp, courtageklass, likvid och valfria omkostnadsbelopp. Målvikter och innehav är separata. Inställningar och sparade mål är separata per konto i den aktuella sessionen. Filimport och kontodata lagras inte i den gemensamma priscachen och skrivs inte till egna kontofiler på servern. Priscachen innehåller enbart offentliga prisserier. Export av målbild eller affärsförslag sker genom användarens nedladdning.

CSV behöver `instrument` (ticker, fond-ID, ISIN eller exakt katalognamn), `antal` och valfritt `omkostnadsbelopp` i SEK. Svenska decimaltecken stöds i semikolonseparerad CSV. Kända instrument identifieras med stabilt ID. Okända instrument, negativa antal och ofullständiga filer avvisas innan kontot byts.

## Likvid och affärsförslag

Nuvarande kontovärde, instrumentvikter och risk inkluderar tillgänglig likvid med antagen ränta noll. En föreslagen ny insättning påverkar finansieringsplanen och optimeringens jämförelsebelopp men ändrar inte nuvarande innehav eller kontovärde.

Kunden väljer om försäljningar och befintlig likvid får användas. En ny insättning kan finansiera köp även när befintlig likvid reserveras. Köp inklusive avgifter ryms i tillåtna likvida medel och netto från tillåtna försäljningar. Kapital och avgifter stäms av. Ett likvidmål är en uttrycklig del av målbilden; instrumentvikterna fördelar återstoden. Resultat med reserverad likvid kan föras över utan att kassavikten normaliseras bort.

AF:s skatt på föreslagna försäljningar använder angivna omkostnadsbelopp och säljkostnader. Saknas ett nödvändigt omkostnadsbelopp visas okänt skatteunderlag. Andra kapitalposter och löpande skatt ingår inte i omställningsberäkningen. Skatt antas betalas utanför kontot, enligt den befintliga kostnadsmodellen. Historiska nettoscenarier är hypotetiska nystartade sparanden, inte återgivning av kundens verkliga skattehistorik.

Affärsförslagen är modellbelopp. Verklig handel behöver hantera antal hela aktier, bryttider, okänd fond-NAV och likviddagar i bankens handelsflöde. Inga order skickas från demon. Likvid som nominell SEK-serie i historiska jämförelser räknas inte som en marknadsorder i orderlistan.

## Optimeringskontrakt

- Endast historik, ingen framåtblick.
- Valda instrument, icke-negativa vikter och total vikt 100 procent. Ett villkor per instrument: **min** är en inkluderande lägsta vikt, **=** en exakt vikt och **max** en inkluderande högsta vikt. Procentvärdet avser hela portföljen. Standard max 100 % lämnar vikten fri. Oförenliga villkor avvisas; de normaliseras inte till andra gränser.
- Kundens val att behålla innehav kan låsa befintliga positioner utanför urvalet. Reserverad likvid hanteras som nominell SEK-vikt.
- Varje kandidat utvärderas med vald buy-and-hold-, månads- eller kvartalsregel. Den snabba värdekurvan verifieras mot befintlig strategimotor.
- Målfunktionen är **före valbara handelsavgifter och kontoskatt**. Fondavgifter som redan ligger i NAV är därmed redan inräknade.
- SLSQP används med flera deterministiska startpunkter, kontroll av konvergens och en projektion som upprätthåller viktgränserna. Texten säger bästa funna fördelning och gör inget anspråk på globalt optimum.
- Resultatet förs över till målbilden och likvidmålet; nuvarande innehav ändras inte.

### Mått

| Mått | Definition |
| --- | --- |
| Sharpe | Daglig aritmetisk överavkastning mot geometriskt omräknad riskfri årsränta, dividerad med daglig standardavvikelse, gånger roten ur 252. |
| CAGR | `(slutvärde/startvärde)^(365,25/antal kalenderdagar) - 1`, uttryckt i procent. |
| Sortino | Genomsnittlig dagsavkastning över geometriskt omräknad målavkastning, dividerad med roten ur medelvärdet av kvadrerade negativa avvikelser över alla observationer, gånger roten ur 252. |
| MaxDrawdown | Största positiva procentuella förlust från tidigare topp, inklusive startvärdet. Målfunktionen minimerar förlusten. |
| Volatilitet | Daglig standardavvikelse omräknad till årsprocent. |

Noll volatilitet eller avsaknad av negativa avvikelser ger odefinierad relevant kvot, inte en artificiellt oändlig vinnare. CAGR annualiserar periodens geometriska utveckling och är inte en framtidsprognos.

### Egna formler

Endast de namngivna måtten, ändliga tal, parenteser och `+ - * /` stöds. Formeln tolkas med ett begränsat syntaxträd. Funktioner, attribut, indexering, programkod och exponering av andra namn tillåts inte. Python `eval` används inte. Längd, djup och antal syntaxnoder begränsas.

Exempel: `CAGR - 0.5 * MaxDrawdown`. CAGR och drawdown är procenttal (8 betyder 8 procent), medan Sharpe och Sortino är kvoter. Skalningen när olika enheter blandas är ett uttryckligt användarval.

## Sökning och senare validering

Standard är att använda 70 procent av gemensamma dagsavkastningar för sökningen, följt av senare historik för valideringen. Periodgränsen delar en kursnivå men ingen avkastningsobservation. Minst 252 avkastningar behövs i sökperioden och 63 i valideringen. Detta är ett produktkrav för dataunderlaget, inte en statistisk kvalitetsgaranti.

Vikterna väljs enbart på sökperiodens värdekurvor. Senare kurser ändrar inte sökresultatet. Valideringen jämför den funna fördelningen, nuvarande fördelning och en likaviktad portfölj. Jämförelseportföljerna kan ligga utanför sökningens viktgränser. Nettokolumnen använder samma senare period och vald kostnads-/skattemodell men styr inte sökningen.

Instrumenturval och kundvillkor väljs i dag. Valideringen är därför en historisk efterkontroll givet dessa val, inte en rekonstruktion av ett helt förutseende fritt historiskt placeringsbeslut. Upprepade ändringar efter inspektion av valideringen kan också överanpassas. Ändrade kursdata, namn, innehav, villkor eller målfunktion gör det visade resultatet inaktuellt tills en ny sökning körs.

## Informationshierarki

`help_ui.py` samlar en gemensam informationsruta och definitioner för nyckeltalen. Den öppnas med klick/tryck och kan användas med tangentbord. Längre metodtext och upprepade förklaringar ligger i informationsrutor eller stängda detaljsektioner. Datakälla, faktisk period, valda nettolägen, otillräckligt underlag och relevanta fel finns kvar direkt i vyn. Bevakningsexempel visas i utbildningsläget.

## Verifiering

Tester täcker bland annat alla mål och rebalanseringsregler, CAGR/Sortino/drawdown, låsta och omöjliga viktgränser, jämförelse med tät tvåtillgångssökning, oberoende av senare valideringskurser, säkra formler, kontobyten, sessionisolering, CSV, kassa- och avgiftsavstämning, okänd AF-skatt, sparade mål samt överföring av hela viktsvektorn inklusive reserverad likvid.
