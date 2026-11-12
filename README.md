# Avanza-portföljkollen

Projekt: `fanasno/Avanza-portfoljkollen`. Fristående Streamlit-demo av konceptet Sparstrategi · Avanza Akademin.

För publicering i Streamlit Community Cloud, välj detta repository, grenen `main` och startfilen `app.py`. Se [DEPLOY_STREAMLIT.md](DEPLOY_STREAMLIT.md). En publik appadress anges när publiceringen är verifierad.

En lokalt körbar konceptprototyp för historiska portfölj- och strategijämförelser. Bygger vidare på [SAVR Portföljkollen + TestSAVR](https://github.com/fanasno/savr-portfoliokollen-testsavr), commit `41a98cc`. SAVR-originalet är oförändrat.

## Kunddemo och historisk optimering · version 2.5

Informationsrutor öppnas med klick eller tryck; nyckeltal har kort hjälp och längre antaganden ligger på begäran. Datakällor, perioder och fel förblir synliga.

**Mitt konto · demo** visar separata Demo-ISK/Demo-AF och stödjer CSV-import av kända innehav med antal och valfria omkostnadsbelopp. Likvid, ny insättning, försäljningsval och likvidmål hanteras i en finansierad affärsplan. Mål sparas per konto i sessionen och kan laddas ner. Ingen bankinloggning eller orderläggning ingår; en riktig integration kräver Avanzas kundmiljö.

**Hitta en historisk fördelning** söker vikter för Sharpe, CAGR, Sortino, lägsta max drawdown eller en validerad egen formel. Varje instrument har ett villkor **min**, **=** eller **max** och ett procentvärde av hela portföljen. Exempelvis tillåter min 20 % en högre vikt, = 20 % kräver exakt 20 % och max 20 % tillåter en lägre vikt. Standard max 100 % lämnar vikten fri. Likvid- och försäljningsvillkor gäller också. Äldre historik används för sökning och senare historik för validering mot nuvarande och likaviktad fördelning. Optimeringen är före valbara avgifter och skatt; valideringens netto visas separat. Hela resultatet kan föras över till målvikter utan att ändra nuvarande innehav.

Se [OPTIMIZATION_AND_ACCOUNTS.md](OPTIMIZATION_AND_ACCOUNTS.md) för mått, datakrav, antaganden och teknisk avgränsning. `account_model.py`/`account_ui.py` hanterar kundadaptrar och kassafinansiering, `optimization_model.py`/`optimization_ui.py` historisk sökning och validering och `help_ui.py` gemensamma informationsrutor. SciPy är ett nytt låst beroende.

## Fria målvikter och verklig historik

Portföljkollens målbild består av fria instrumentrader i den befintliga kortlayouten. Varje rad har sökbart instrumentval, eget visningsnamn, målvikt och borttagningsknapp. Plusknappen lägger till en rad. Standardprofiler används som startmallar och egna ändringar aktiverar Egen profil. Alla 24 egna Avanza-fonder, referens-ETF:erna och katalogens aktier kan väljas. Instrument-ID och prisdata är separata från visningsnamnet.

Nuvarande exempelinnehav och önskade målvikter är separata. Ett nytt målinstrument börjar med noll i befintligt innehav. Ett borttaget målinstrument finns kvar i nuläget med målvikt noll om kapital redan är placerat där. Tom målbild ger inget affärsförslag. Målvikter normaliseras till 100 procent när de är positiva. Det görs ingen påhittad genomlysning av blandfondernas aktieandel.

**Marknadsdata är standard.** Avanzas egna fonder använder ursprunglig daglig NAV med verifierat fond-ID; aktier, referens-ETF:er och valutor använder Yahoo Finance. Verifierad historik sparas per instrument och period i `.cache/prices`. Om hämtningen misslyckas används komplett verifierad historik med datum och cachemärkning, eller ett tydligt fel. Ingen automatisk ersättning med exempelkurser finns kvar. Exempeldata är ett separat, uttryckligt testläge med fasta simulerade serier till och med 2 november 2026.

Simulatorn visar **historiska jämförelser** mellan buy and hold, månadsvis och kvartalsvis rebalansering. Framåtblicken är borttagen från demon enligt användarens beslut. Jämförelsen visar faktisk gemensam period, antal dagsavkastningar samt kurskällor, första och senaste rapporterade kursdag och observationer per instrument. Ingen framtida genomsnittsavkastning estimeras. Portföljen från Portföljkollen kan testas med antingen nuvarande vikter eller målvikter; då följer egna namn och nya målinstrument med.

Riskanalysens historikfönster, riskfria årsränta och Sharpe-skala väljs separat. Faktisk period och antal observationer redovisas. Färre än 20 dagsavkastningar ger saknat riskunderlag; giltiga nollvärden behålls. Målvikter med noll nuvarande innehav kortar inte riskanalysen av den nuvarande portföljen.

Ny insättning finansierar köp utan försäljningar. Förklaringen namnger de innehav vars försäljningslikvid inte används. Procenten jämför faktiskt använda köppengar efter valda avgifter med köpbehovet efter samma insättning.

## Avgifter, skatt och procent

Oberoende kryssrutor väljer handelsavgifter respektive beräknad ISK-/AF-skatt. Mini, Small, Medium, Fast Pris och villkorad Start ingår. Start räknar daterade affärer över tolv kalendermånader och har permanent övergång till Mini när villkoren upphör. Courtagets minimiavgifter omräknas till SEK och köpavgifterna ryms i budgeten. Fondavgifter som redan ligger i NAV dras inte av igen.

AF visar som standard netto om innehaven såldes vid varje datum, inklusive tänkta säljavgifter och beräknad skatt. Den värderingen ändrar inte innehav eller genomförda order. Valbar faktisk slutavveckling dubbelräknar inte kostnader eller skatt. ISK och AF jämförs med samma underlag, med årliga skattedetaljer och orderexport.

Resultat, kurvor och avdrag kan visas i kronor och procent. Procentbaser, följdeffekter och skillnader i procentenheter redovisas. Prislistans och skattereglernas kontrolltidpunkt är uttrycklig och uppdateras inte automatiskt. Se [COSTS_AND_TAX.md](COSTS_AND_TAX.md).

## Starta

Kör `./Start.ps1` i PowerShell. Appen finns på http://127.0.0.1:8510. Alternativt: `python -m streamlit run app.py --server.port 8510`. För en ny miljö, installera först `pip install -r requirements.txt`.

Streamlit kräver en Python-server. Den publika förhandsvisningen använder en separat tunnel till den lokala servern; detta är en demo och ingen publicering på Avanzas webbplats. Inga kundkonton är anslutna. Bevakningar och påminnelser är lokala exempel utan bakgrundsaviseringar.

## Dokumentation

- [DEMO_MANUS.md](DEMO_MANUS.md): manusunderlag om nyckeltal, datakällor, målbild och historisk jämförelse.
- [HISTORIK_GRANSKNING.md](HISTORIK_GRANSKNING.md): metodgranskning, verifierad fondhistorik och beslutet om framåtblicken.
- [FUNDS_AND_SHARPE.md](FUNDS_AND_SHARPE.md): fondidentiteter och riskmetod.
- [COSTS_AND_TAX.md](COSTS_AND_TAX.md): avgifter, skatt och procent.

`portfolio_model.py` hanterar instrumentidentitet, målvikter och separat nuläge. `portfolio_ui.py` hanterar de redigerbara instrumentkorten. `experience.py` hanterar navigation och datastatus; `market_data.py` hämtning och verifierad cache. Övriga beräknings- och presentationsmoduler behåller sina tidigare ansvar.

## Verifiering

Kör `python -m unittest discover -s tests -v`. Tester täcker fria instrument, namnbyte, borttagna innehav, nollinnehav, dubbletter, tom målbild, navigering, verklig/cachelagrad/utebliven prisdata, historikperioder, rebalansering, avgifter, ISK-/AF-skatt och procentavstämning. Beräkningarna jämförs även med SAVR:s referensresultat. AST-fingeravtryck kontrollerar de 29 oförändrade funktionerna i `engine.py`; de fyra anpassade funktionerna verifieras med beteendetester. Den tidigare framtidsmotorn finns enbart kvar för intern regression och visas inte i demon.
