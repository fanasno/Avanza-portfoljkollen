> Aktuell demo från 11 november 2026: framåtblicken är borttagen. Portföljkollens målbild har fria instrumentrader. Stycken nedan om den tidigare framtidsmotorn är metodhistorik, inte funktioner som visas i demon. Verklig historik är standard och hämtfel ersätts inte med simulerade kurser. Se HISTORIK_GRANSKNING.md och DEMO_MANUS.md.

# Avanza-fonder och Sharpe · 3 november 2026

## Fondutbud och identifiering

De 24 egna fonder som finns i [Avanzas officiella utbud](https://investors.avanza.se/om/avanza-fonder/vara-fonder/) och publika fondsökning är registrerade i `avanza_funds.json`. Varje post har fondnamn, ISIN, Avanzas orderboks-ID, SEK som andelsvaluta, fondtyp, fondstart, aktuellt redovisad fondkostnad och en länk till originalfaktabladet. Katalogen innehåller aktuella andelsklasser, bland annat Avanza Sweden SEK A och Avanza Sweden All Cap A. Auto 1–6 är sex separata fonder.

Alla 24 kan väljas fritt i strategisimulatorn. Ett filter skiljer egna fonder, referens-ETF:er och aktier. Portföljkollens befintliga sex kategorier erbjuder de egna fonder som passar respektive kategori; bland-, Auto-, fastighets- och vårdfonder pressas inte in i en missvisande kategori. De är tillgängliga i simulatorn. Standardprofilernas tidigare referensinstrument är kvar.

## Kurser och fondkostnader

I läget **Marknadsdata** hämtas originalfondens NAV från Avanzas publika fondkurvskälla med `raw=true`. Interna nycklar som `AVANZA:41567` är inte Yahoo-symboler. Övriga instrument och valutakurser hämtas från Yahoo Finance. Ingen ETF används som ersättning för en fondkurva.

Avanzas långa grafintervall samplar normalt kursserien till veckopunkter. Adaptern hämtar därför högst 364 kalenderdagar åt gången, behåller dagliga NAV-punkter och avvisar glesa serier. Tidsstämplar konverteras från UTC till kursdag i Stockholm. Det skapas inga värden före fondstart. Jämförelser och framtidsscenarier utgår från senast gemensamt tillgängliga kursdag för de valda instrumenten. Fondernas NAV kan ligga en dag efter börshandlade instrument.

Alla 24 originalserier har provhämtats. Senaste NAV för varje fond stämde med Avanzas separata fonduppgifter vid kontrollen. Även ett blandat underlag med Avanza Zero, Avanza Ränta Kort, Apple och USD/SEK har verifierats. Om någon källa misslyckas byter hela underlaget till tydligt märkta exempeldata. Verkliga och syntetiska instrumentpriser blandas inte.

**Exempeldata är syntetiska även när ett verkligt fondnamn valts.** De är för demonstrationsbruk och visas inte som faktisk fondhistorik. Fondstart respekteras även där. Katalogens fondkostnad används som ett antaget löpande avdrag i den syntetiska NAV-serien.

Vanliga fondaffärer i SEK har 0 kr i modellerat onlinecourtage och inget separat valutaväxlingspåslag för kunden. Fondens underliggande valutaexponering och förvaltningskostnader ligger redan i NAV. Den redovisade totala fondkostnaden är information och dras inte av igen. Avgiftsrutan styr ytterligare handels-/extrakostnader; den kan inte återställa redan kursinbakade fondkostnader. Start-erbjudandets eventuella fondavgiftsåterbetalning modelleras inte. Fondorder antas ske till vald kursdags NAV utan verkliga bryttider, okänd orderkurs eller likvidfördröjningar.

## Historik och Sharpe är två olika val

Tidigare användes redan valbara 1, 3 eller 5 års historik, med 3 år som standard. Sharpe uttrycktes på årsbasis. Det fanns alltså inget tvingat ettårigt historikunderlag, men skillnaden var otydlig i gränssnittet.

Nu är följande separata och synliga inställningar:

- Historik: 1, 3 eller 6 månader; 1, 3 eller 5 år; eller egna från-/tilldatum.
- Riskfri ränta: en redigerbar effektiv årsränta.
- Sparhorisont: 1–120 månader.
- Sharpe-skala: årsbasis eller vald sparhorisont.

Ett fönster på 252 dagsavkastningar behöver 253 kursobservationer. Appen redovisar den faktiskt använda perioden och antalet avkastningar. När någon fond har kortare historik används den gemensamma perioden och begränsningen visas. Inga riskmått bygger på extrapolerade kurser före fondstart.

Sharpe beräknas från aritmetiska dagsavkastningar i SEK. Den effektiva riskfria årsräntan omräknas till en dagsränta:

`rf_dag = (1 + rf_år)^(1/252) - 1`

`Sharpe_år = medel(r_dag - rf_dag) / std(r_dag, ddof=1) × sqrt(252)`

Sparhorisontsskalan är separat:

`Sharpe_H = Sharpe_år × sqrt(månader / 12)`

Detta är en vanlig tidsomräkning under antagande om stabila, okorrelerade avkastningar. Det är inte en prognos för den faktiska risken eller avkastningen under hela spartiden. Seriekorrelation kan göra skalningen missvisande. Att höja antalet månader förbättrar inte strategin; därför visas års-Sharpe också, och profilmålen ligger kvar på årsbasis. Det visade målvärdet skalas med samma faktor om en annan visningsskala väljs.

Primärkällor: [William F. Sharpe om annualisering](https://web.stanford.edu/~wfsharpe/art/stars/stars3.htm) och [Andrew W. Lo, The Statistics of Sharpe Ratios](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios).

Portföljkollens historiska avkastning, volatilitet och drawdown visas som **—** vid saknade eller ogiltiga data eller färre än 20 dagsavkastningar. Giltiga nollvärden behålls. Sharpe visas dessutom som **—** vid noll volatilitet eller en nettokurva som når noll/negativa värden. Riskmål lagras på årsbasis; Sharpevärden och jämförelsemål visas på samma valda skala i sammanfattning, diagnos och varningar. Även ett giltigt mått från kortare än ett år markeras som känsligt för vald period.

## Portfölj och strategier

Portföljkollens historiska riskmått använder dagens vikter som konstanta vikter över analysperioden, före valbara handelsavgifter och kontoskatt. Utländska instrument omräknas till SEK före beräkningen. Simuleringarna använder däremot den faktiska modellerade strategins värdekurva inklusive valda avgifter, kontoskatter och AF:s valda försäljningsvärdering.

Strategiernas Sharpe redovisas på årsbasis och på den valda horisontsskalan. Historiska kurvor avgränsas av valt analysfönster. För framtidsscenarier beräknas Sharpe för varje modellväg och därefter medianen av giltiga skattningar, inte Sharpe från mediankurvan. Framtidsmodellens bootstrap använder det valda historikfönstret men börjar fortfarande vid senaste gemensamma kursdag. Knappen **Använd min sparhorisont** sätter även scenariots faktiska slutdatum.

Den ursprungliga `engine.py` med 33 funktioner är oförändrad och regressionstestad. Den utökade riskberäkningen och valutaomräkningen finns i `risk_model.py`.
