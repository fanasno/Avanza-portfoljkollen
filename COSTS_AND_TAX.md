# Kostnader och kontoskatt · kontrollerat 3 november 2026

## Prislista och omfattning

Fyra ordinarie klasser: Mini, Small, Medium och Fast Pris. Start är ett separat villkorat erbjudande. För svenska aktier på Stockholmsbörsen gäller:

| Klass | Rörligt courtage | Minst / fast |
| --- | ---: | ---: |
| Mini | 0,25 % | 1 kr |
| Small | 0,15 % | 39 kr |
| Medium | 0,069 % | 69 kr |
| Fast Pris | 0 % | 99 kr |
| Start | 0 % för berättigad svensk aktiehandel | 0 kr |

Det högsta av minimibelopp och procentbelopp används; dessa adderas inte. USA har 0,25 / 0,15 / 0,089 / 0,079 % och minst 1 / 6 / 8 / 12 USD. Start följer Mini utanför berättigad handel. Svensknoterad ETF har i Fast Pris 0,045 %, minst 99 kr, inte obegränsat fast 99 kr. Vanliga fonder har normalt inget onlinecourtage. Produktundantag, exempelvis köpavgift för Brummerfonder, måste anges separat.

Prismotorn innehåller även andra avlästa nordiska och europeiska grundtariffer. Gränssnittets automatiska klassificering omfattar valda aktier, referens-ETF:er och vanliga fonder, inklusive Avanzas egna fonder. Derivat, blankning, belåning, mäklarorder och Private Banking/Pro modelleras inte.

- [Avanzas courtageklasser](https://www.avanza.se/konton-lan-prislista/prislista/courtageklasser.html)
- [Svenska värdepapper](https://www.avanza.se/konton-lan-prislista/prislista/handel-sverige.html)
- [Utländska värdepapper och valutaväxling](https://www.avanza.se/konton-lan-prislista/prislista/handel-utland.html)

ISK och AF har enligt Avanzas kontoprislista 0 kr i kontoavgifter. Detta är skilt från instrumentens avgifter och återges som en egen nollpost i avstämningen: [Kontoavgifter](https://www.avanza.se/konton-lan-prislista/prislista/kontoavgifter.html).

## Start och daterad affärshistorik

Start använder ett rullande fönster `(beräkningsdag − 12 kalendermånader, beräkningsdag]`. Högst 500 kvalificerade aktieordrar får gratiscourtage inom fönstret; nästa sådan order prissätts enligt Mini och rätten till Start upphör permanent. Äldre affärer faller ur räknaren om gränsen inte har passerats. Ett samlat Avanza-värde på minst 50 000 kr avslutar också rätten permanent, även om värdet senare faller. Varje Monte Carlo-väg har en egen räknare och behörighet.

Tidigare gratisaffärer anges med datum och antal. Endast poster före respektive simulerings startdatum räknas; tom historik innebär ett uttryckligt antagande om inga tidigare gratisaffärer. Tidigare förlorad behörighet behöver beaktas när Start-villkoren bekräftas. Endast genomförda kvalificerade aktieordrar förbrukar utrymme; AF:s hypotetiska försäljningar gör det inte. Samma daterade räknare används för Portföljkollens orderkostnader.

## Så finansieras avgifterna

Startbeloppet omfattar köpen **och** köpavgifterna. Det tillförs inga extra fiktiva pengar. Vid rebalansering säljs övervikt när försäljningen täcker säljkostnaden. Nettolikviden fördelas till undervikt med köpavgifterna inräknade i likvidbudgeten. Kundens ordergräns kan göra att små affärer hoppas över; därför kan målvikterna bara nås ungefärligt efter kostnader.

Modellen räknar en order per instrument, riktning och datum. Avslutande försäljning väljs separat. Om avslutsavgifterna överstiger tillgänglig likvid visas det extra kontantbehovet. Avanzas minimiavgift i USD omräknas till SEK med den tillgängliga valutaserien; ingen valutakurs fabriceras.

Automatisk valutaväxling har ett förvalt påslag om 0,25 % per riktning. Valutaväxlingsunderlaget inkluderar courtage vid köp och är efter courtage vid försäljning. Ett valutakontos egna valutakassor och manuella växlingsflöden modelleras inte. Den redigerbara satsen är en per-affärsmodell.

Full köp-/säljspread anges av användaren och hälften används per riktning. Extra avgift per order, procentuell köpskatt och extra löpande avgift anges per instrument. Dessa är antaganden, inte hämtade instrumentspecifika priser. Värdet 0 ska inte tolkas som en verifierad nollkostnad. Till exempel stämpelskatt, särskilda administrativa avgifter och depåbevisavgifter behöver anges när relevanta. Avanza anger dessa möjliga tillägg i sin prislista.

Fondens eller ETF:ens avgift som redan ligger i NAV/kursen dras inte av igen. En extra löpande avgift representerar endast ett ytterligare värdeavdrag. Start-återbetalning av vanliga fondavgifter beräknas inte för referens-ETF:erna, och de amerikanska referens-ETF:ernas köpbarhet hos Avanza är inte verifierad.

## ISK

För varje kalenderår beräknas kapitalunderlaget som summan av värden vid ingången av kalenderkvartal och externa insättningar, dividerat med fyra. Senaste värde före kvartalsöppning används. Startbeloppet är en ny insättning; inget innehav före start eller extra insättningar under perioden antas. Vid valt avslut säljs och tas kapitalet ut. Endast kvartal som infaller under modellen ingår; ett sent insatt belopp får därför inte automatiskt ett helt års skatt.

Fastställda effektiva skattesatser i modellen: 2020–2022 0,375 %, 2023 0,882 %, 2024 1,086 %, 2025 0,888 %, 2026 1,065 %. Grundnivån är 0 kr till och med 2024, 150 000 kr för 2025 och 300 000 kr från 2026 enligt dagens regler. Angiven del som reserverats för övrigt ISK/KF/PEPP-sparande minskar modellens tillgängliga grundnivå; detta är ett användarantagande om fördelningen, inte en automatisk beräkning av personens samtliga konton eller turordningsregler.

ISK-satsen för 2027 kan inte fastställas per 3 november 2026 eftersom den beror på statslåneräntan 30 november 2026. För 2027 och senare är både sats och oförändrad grundnivå därför uttryckligen antaganden. Den antagna satsen kan ändras.

- [Skatteverket: belopp och procent 2026](https://www.skatteverket.se/privat/skatter/beloppochprocent/2026.4.1522bf3f19aea8075ba21.html)
- [Skatteverket: historiska schablonintäkter](https://www.skatteverket.se/investeringssparkonto)
- [Skatteverket: kvartalsvärden och kapitalunderlag](https://www.skatteverket.se/privat/skattevardepappeinvesteringssparkontoisk/raknautschablonintakt.4.7eada0316ed67d72823b57.html)

## Aktie- och fondkonto (AF)

Aktie-/aktiefondsvinster och förluster nettas inom samma modellår. Köpkostnader ingår i genomsnittligt omkostnadsbelopp. Vid delvis försäljning används en proportionell del av omkostnadsbeloppet. Försäljningskostnader minskar försäljningsintäkten. Återstående aktieförlust kvoteras till 70 %. De noterade räntefondsreferensernas förluster dras av fullt ut, enligt Skatteverkets vägledning även för motsvarande utländska räntefonder.

Schablonintäkten för fond-/ETF-andelar är 0,4 % av modellens fondvärde vid kalenderårets ingång, med kapitalinkomstskatt 30 % (0,12 % före kvittning). Nyinköpta andelar efter årets ingång belastas inte retroaktivt med ett helt års fondschablon. Vanliga aktier har inte denna fondschablon.

Överskott av kapital beskattas med 30 %. En valbar skattereduktion använder 30 % av underskott upp till 100 000 kr och 21 % över gränsen. Den är avstängd som standard, eftersom möjligheten att utnyttja den beror på annan slutlig skatt. Andra kapitalinkomster, ränteavdrag, utländsk avräkning och personlig deklarationsavrundning modelleras inte automatiskt.

AF visas som standard **som om kvarvarande innehav såldes vid varje datum**. Varje punkt använder just den dagens värden, valutakurser, kvarvarande genomsnittliga omkostnadsbelopp och eventuella säljavgifter. Försäljningsvinsten eller förlusten läggs till samma kalenderårs redan realiserade resultat; årets skatt räknas om och tidigare års skatt lämnas oförändrad. Nettot drar av ackumulerad AF-skatt efter denna tänkta försäljning och ytterligare säljkostnader. Kvittning kan minska redan reserverad skatt samma år; en förlust ger inte en utlovad skattereduktion när den valbara reduktionen är avstängd.

Varje datum är ett oberoende försäljningsscenario. Det ändrar inte innehaven, omkostnadsbeloppen, orderlistan, Start-gratisaffärerna eller strategins fortsatta rebalanseringar. Vid en verklig modellerad slutavveckling är innehaven redan sålda: extra säljavgifter och latent skatt blir då noll, medan faktisk säljkostnad och realiserad skatt redan ingår. De dras aldrig av två gånger.

Kryssrutan **AF: visa netto om jag sålde vid varje datum** kan stängas av för att visa enbart realiserad och löpande skatt i AF-kurvan. Det vanliga skattevalet styr fortfarande om skatt över huvud taget ingår i resultatet. En datumväljare i AF-resultatet visar avstämningen för en tänkt försäljning vid ett historiskt eller modellerat framtida datum. Helger använder föregående tillgängliga kursdag. Framtidsdetaljen visar samma enskilda modellväg som avstämningen, inte delposter från olika medianer.

Om innehaven behålls vid slutdatum realiseras ingen faktisk slutvinst. Beräknad skatt vid tänkt försäljning särredovisas från realiserad skatt och genomförda order. Portföljkollens befintliga omviktning kräver egna omkostnadsbelopp för att uppskatta AF-skatt. Där är förvalet dagens värde uttryckligen ett nyanskaffningsantagande.

- [Skatteverket: fonder och fondschablon](https://www.skatteverket.se/privat/skatter/vardepapper/omovrigavardepapper/fonder.4.19b9f599116a9e8ef36800010782.html)
- [Skatteverket: kvittning och skattereduktion](https://www.skatteverket.se/privat/etjansterochblanketter/svarpavanligafragor/vardepapper/privatvardepapperfaq/kanjagkvittavinstmotforlustnarjagharsaltvardepapper.5.2b543913a42158acf800015357.html)
- [Skatteverket: marknadsnoterad utländsk räntefond](https://www4.skatteverket.se/rattsligvagledning/edition/2026.14/2818.html)

## Utdelningar, skattebetalning och avstämning

Justerade kurser innehåller redan återinvesterad bruttoavkastning. Ett angivet årligt utdelningsantagande delas jämnt över dagarna för att uppskatta utdelningsskatt och ökat AF-omkostnadsbelopp; utdelningen adderas inte till kursavkastningen igen. Det är inte faktisk utdelningshistorik. Med 0 anges ingen separat utdelning under innehavstiden; återinvesterad avkastning blir då en del av realisationsvinsten vid AF-försäljning. Modellen räknar inte separata återinvesteringsorder och deras courtage. Antagen utländsk utdelning belastas med valutaväxlingspåslag. Ej återfådd/avräknad källskatt anges separat av användaren och dess faktiska återbetalningstid modelleras inte.

**Skatten är en skuld utanför portföljen**, som antas betalas med andra medel. Nettovärdet är portföljvärde efter handelsavgifter minus ackumulerad modellskatt. Skatt finansieras alltså inte genom extra fiktiva försäljningar och minskar inte det återinvesterade portföljkapitalet mellan skatteåren. Detta framgår intill resultatet.

Alla utländska serier omräknas till SEK för värde, omkostnadsbelopp och skatt. Detta korrigerar v1-simulatorns jämförelse i instrumentens prisvaluta.

Monte Carlo använder samma bootstrap-dragningar för alla strategier. Nettokvantiler beräknas från varje vägs avgifter och skatt; skatt på en mediankurva används inte som ersättning för skatt i varje simulering. Detaljredovisningen väljer en faktisk väg nära valt kontos median. Avstämningen innehåller brutto, varje direkt avgift, följdeffekten av ändrad exponering och eventuell ordergräns, skatt och netto. Därför adderar samtliga poster till samma slutvärde. Årsunderlag och orderlista med CSV-export kan granskas.

## Utveckling och avdrag i procent · version 2.3

Sammanlagd utveckling är `(värde / hela startbeloppet − 1) × 100`. Det är periodens kumulativa utveckling, inte en årsavkastning. Samma startbelopp används för varje punkt, kurva och strategi. Om köpavgifter redan har betalats vid första kurvpunkten kan nettokurvan börja under 0 %. Den normaliseras inte om till noll efter avgiften. AF:s tänkta försäljningsvärdering fungerar på samma sätt.

Alla slutvärden visar utveckling i procent tillsammans med kronor. Kurvans och strategitabellens enhet kan växlas mellan procent och kronor. Hovring visar båda, och framtidens P10–P90-intervall omräknas med samma startbelopp. Vid AF:s valda försäljningsdatum visas också utveckling i procent för värden och avdrag i procent av startbeloppet för kostnadsrader.

Skillnaden mellan nettoavkastning och avkastning före valda avdrag anges i **procentenheter**. Exempel: 100 000 kr blir 120 000 kr före avdrag, och 113 300 kr efter 1 000 kr avgifter och 5 700 kr skatt. Utvecklingen är +20,00 % respektive +13,30 %. Avdragens påverkan är −6,70 procentenheter; detta är inte en skattesats på 6,70 %.

Detaljrutan har tre möjliga procentbaser:

- **Startbeloppet:** varje avdrag divideras med det ursprungliga investeringsbeloppet.
- **Slutvärdet före avdrag:** varje avdrag divideras med scenariots värde före valda avgifter och skatt.
- **Vinsten före avdrag:** varje avdrag divideras med värdet före avdrag minus startbeloppet. Om vinsten inte är positiv visas ingen procentandel av vinsten, men kronbeloppen finns kvar. Avdragen får överstiga 100 % av en positiv vinst; värdet klipps inte.

Procentbasen och dess kronbelopp visas. Positiva poster är avdrag, medan negativa poster visar en förbättring eller skattereduktion. Direkta avgifter, tänkta återstående säljavgifter för AF, skatt och följdeffekten av ändrad exponering stäms av mot skillnaden mellan före- och nettovärde. Skatt som är avstängd räknas inte som ett avdrag. Varken genomförda säljavgifter eller realiserad skatt läggs på en gång till i AF:s försäljningsvärdering.

För framtidsscenarier visar huvudvärdena medianer, och den synliga skillnaden mellan deras avkastningar är en skillnad mellan medianutfall. Detaljuppdelningen använder däremot samma enskilda modellväg som kostnadsavstämningen. Procentsatserna för delposterna adderar därför till denna modellvägs totala avdrag, utan att summera delposter från olika medianer.

Fondkostnader som redan ingår i NAV ligger i prisserien också före valda avdrag. Den faktiska kursinbakade kostnaden särberäknas inte och dras inte av igen. Den visade posten extra löpande avgift avser endast ett användarangivet tillägg.
