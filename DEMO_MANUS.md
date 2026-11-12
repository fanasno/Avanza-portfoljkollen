# Manusunderlag: vad Portföljkollen följer

Utkast att gå igenom inför presentationen. Det här är manusunderlag, inte ny hjälptext i gränssnittet.

## Portföljen och målbilden

”Vi börjar med en exempelportfölj. Innehaven och beloppen är exempel, medan standardläget använder verkliga marknadskurser. Verktyget är inte anslutet till ett kundkonto.”

”Här skiljer vi mellan vad jag har och vad jag vill ha. I målbilden kan jag välja instrument, sätta egna namn och målvikter. Ett namnbyte ändrar inte fonden eller prisdatan. Ett nytt instrument börjar med noll i nuvarande innehav. Tar jag bort ett befintligt innehav ur målbilden finns kapitalet kvar i nuläget, men målvikt noll kan ge ett säljförslag.”

## Vad nyckeltalen svarar på

| Nyckeltal | Frågan det svarar på | Underlag |
| --- | --- | --- |
| Portföljvärde | Hur mycket är exempelinnehaven värda vid värderingsdatumet? | Exempelpositioner, senast tillgängliga priser och valutakurser. |
| Aktieexponering | Hur stor del ligger i instrument som modellen klassificerar som aktier/aktiefonder? | Nuvarande värden och instrumentens typ. Det är ingen fullständig genomlysning av blandfonders underliggande innehav. |
| Sharpe | Hur har avkastningen över den valda riskfria räntan förhållit sig till svängningarna? | Dagsavkastningar i SEK under valt historikfönster. |
| Volatilitet | Hur stora har de historiska svängningarna varit? | Standardavvikelsen för portföljens dagsavkastningar, omräknad till årsbasis. |
| Största innehav | Hur koncentrerad är portföljen till ett enskilt instrument? | Det största nuvarande innehavets värde och andel av totalvärdet. |

”Riskanalysen använder nuvarande portföljvikter konstant genom historikfönstret. Den beskriver hur den sammansättningen hade betett sig under perioden, inte en kunds faktiska historiska affärer. Målvikterna styr jämförelsen och affärsförslagen; de ersätter inte nulägets vikter i dessa riskmått.”

## Historik, årsbasis och sparhorisont

”Historikfönstret väljer vilka kursdagar som ingår. Årsbasis är en omräkning till en jämförbar enhet. Den valbara Sharpe-skalan för sparhorisonten är en approximation under antagande om stabila och okorrelerade avkastningar. En längre vald horisont ändrar inte de historiska kurserna och innebär inte att avkastningen blir bättre.”

”Vi visar faktisk period och antal dagsavkastningar. Riskmåtten kräver minst 20 dagsavkastningar. Sharpe saknar dessutom ett definierat värde vid noll volatilitet. Ett streck betyder att måttet saknar tillräckligt underlag, medan ett uppmätt nollvärde visas som noll.”

Portföljkollens riskrutor är före de valbara handelsavgifterna och kontoskatten. Strategijämförelsens nettokurva inkluderar de avdrag som användaren har valt. Detta behöver nämnas när resultat från de två vyerna jämförs.

## Ny insättning

”Här räknar vi med insättningen som enda ny köplikvid. Vi behåller de innehav som annars hade kunnat säljas och räknar inte med deras försäljningslikvid. Procenten jämför de köp som insättningen finansierar efter avgifter med köpbehovet för målbilden efter samma insättning.”

## Historisk strategijämförelse

”När jag tar med portföljen hit kan jag välja nuvarande vikter eller målvikter. Det gör det möjligt att jämföra den önskade fördelningen historiskt utan att påstå att innehaven redan har ändrats.”

”Nu jämför vi strategier över samma tillgängliga historik. Vi återspelar kursrörelserna med vald fördelning och rebalansering och räknar av valda avgifter och skatt. Vi uppskattar ingen framtida genomsnittsavkastning. Faktiska datum och kurskällor syns i beräkningsunderlaget.”

”En ny fond kan förkorta den gemensamma jämförelseperioden. Vi skapar inga kurser före fondstart. Om ny data inte kan hämtas används komplett tidigare verifierad historik med tydlig märkning, eller ett felmeddelande. Exempelkurser aktiveras bara genom ett uttryckligt val av testläget.”

## Punkter att avgöra vid manusgenomgången

- Hur mycket av definitionerna som sägs muntligt respektive visas i demon.
- Vilka instrument och målvikter som bäst illustrerar koncentration och omviktning.
- Vilken historisk period som ska användas genom hela presentationen.
- Hur avgifter, AF:s tänkta försäljning och ISK-skatt ska demonstreras utan att blanda samman beräkningsgrunderna.
