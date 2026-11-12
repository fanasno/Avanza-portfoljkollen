# Verifiering 3 november 2026

## Version 2.3 · procentuell utveckling och avdrag

92 automatiska tester passerar. Beräkningsmotorn för avgifter och skatt är oförändrad; den nya rapporteringen använder samma resultat.

- Utveckling räknas på hela startbeloppet och döljer inte redan betalda köpavgifter genom att starta nettokurvan på 0 %.
- Kronbelopp, utveckling och påverkan i procentenheter stämmer i ett kontrollerat exempel med +20 % före och +13,30 % efter avdrag.
- Startbelopp, slutvärde före avdrag och positiv vinst är separata procentbaser. Noll/negativ vinst ger ingen fabricerad procentandel; avdrag över 100 % av vinsten tillåts.
- AF:s tänkta säljkostnader och totala skatt räknas en gång. Avstängd skatt redovisas inte som avdrag. Även skattereduktion och följdeffekter stäms av.
- Varje framtidsvägs uppdelning använder just den vägens belopp. Den ersätts inte av medianen för varje kostnadspost.
- Appflödet verifierar procent vid samtliga slutvärden, byte mellan procent och kronor samt byte av procentbas utan att kronresultaten ändras.

## Version 2.2 · fondutbud och Sharpe

83 automatiska tester omfattar tidigare funktioner och den utökade fond-/riskmodellen. Alla 24 egna fonder har verifierade fond-ID, ISIN och länkar till fondbolagets originalfaktablad. Original-NAV för samtliga 24 har provhämtats och senaste värdet stämmer med Avanzas separata fonduppgifter. Även verkliga fonder blandade med Apple och USD/SEK har provhämtats utan syntetisk reservdata.

- Långa veckosamplade fondkurvor behandlas inte som dagsavkastningar. Datumintervall på högst 364 dagar ger dagligt NAV med rätt Stockholmsdatum.
- Avanza Zero får 0 courtage och 0 separat valutaväxling i alla courtageklasser. Räntefonder behåller sin fondtyp. Fondkostnad i NAV dras inte av igen.
- Alla 24 är valbara i simulatorn. Zero, Auto 1 och Ränta Kort körs tillsammans i ett appflöde; Zero väljs också i Portföljkollen.
- Historikfönstret ändrar avkastningsunderlaget, medan horisontskalan bara ändrar skalan. Årsräntan omräknas till en matchande dagsränta.
- För korta, konstanta och icke-positiva nettoserier ger inte falska Sharpe-värden på noll. Riskanalysen använder SEK och gemensamt tillgänglig historik.
- Framtidsscenariot använder valt historikunderlag utan att flytta startpunkten till ett gammalt historikdatum. Sparhorisontsknappen ändrar det faktiska slutdatumet.

Full metod och primärkällor finns i [FUNDS_AND_SHARPE.md](FUNDS_AND_SHARPE.md).

## Version 2 · kostnader och skatt

66 tester täcker den befintliga appen och den nya kostnads-/skattemodellen. Avanzas prislistor för courtageklasser, svenska instrument, utlandshandel och kontoavgifter har granskats. Skatteverkets regler för ISK 2026, historiska satser, fondschablon och förlustkvittning har använts. Testfallen innehåller bland annat:

- Fast Pris för svensk ETF skiljs från aktiecourtage och USA-minimiavgifter omräknas från USD.
- Start begränsas till berättigad svensk aktiehandel och kan inte ge fler fria order än de kvarvarande 500.
- Orderlistans avgifter, likvider och AF-realisationsvinster stäms av; köp skapar inga extra pengar.
- ISK använder kalenderkvartal och insättningar, inklusive delår, 2025/2026-grundnivåer och explicit framtidsantagande.
- AF skiljer realiserat från orealiserat, fondandelar från aktier samt kvarvarande aktieförlust från räntefondsförlust.
- Varje AF-punkt kan visa nettot vid tänkt försäljning. Värderingen stämmer med en faktisk modellerad avveckling samma dag inklusive växling, spread, courtage och skatt. En vinst på 20 000 kr med 100 000 kr i omkostnadsbelopp ger 114 000 kr efter 6 000 kr skatt när avgifter är avstängda.
- Samma års förluster kan kvitta redan realiserade vinster. Tidigare års skatt påverkas inte. Faktisk slutavveckling beskattas bara en gång; hypotetiska försäljningar förbrukar inga fria Start-order.
- AF:s datumväljare, växling mellan försäljningsvärde och enbart realiserad skatt samt sparade val vid navigering är testade.
- Skatt och handelsavgifter kan slås av var för sig. Valen består vid byte mellan verktygen.
- Samma Monte Carlo-väg kan återspelas till samma nettokurvor och redovisning. Avstämningen summerar till nettovärdet.

Metodens antaganden och begränsningar framgår av [COSTS_AND_TAX.md](COSTS_AND_TAX.md). Modellerad skatt är inte kundens fullständiga deklaration.

## Ursprunglig version 1

- 14 automatiska tester passerar med `python -m unittest discover -s tests -v`.
- Alla 33 funktioner i `engine.py` har samma AST-fingeravtryck som SAVR-originalet.
- Portföljmått, buy and hold, månadsvis och kvartalsvis rebalansering samt motsvarande Monte Carlo-resultat överensstämmer med originalets referensresultat vid samma indata.
- Originalappen och Avanza-versionen har även körts med samma simulerade prisunderlag och visar samma fem portföljmått.
- Hela Portföljkollen har körts med publika Yahoo Finance-data: inga appfel, fem portföljmått och prisdata daterad 2026-11-03. Ingen reservdata behövdes i det testet.
- Startsida, verktygsingångar och analysvyer är granskade i webbläsare. Mobilkontroll vid 390 px visar ingen horisontell sidscroll.
- Egna målvikter och instrument finns kvar efter simulatorändringar och återgång till Portföljkollen.

Exempeldata är syntetiska. Testerna verifierar att originalets metoder har överförts korrekt, inte att modellerna är oberoende finansiellt validerade. Bevakningar är exempel i den aktuella sessionen.
