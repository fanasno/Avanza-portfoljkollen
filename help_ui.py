"""Consistent, keyboard- and touch-accessible contextual help."""
import streamlit as st


def explain(title, text, key=None):
    with st.popover(f"ⓘ {title}", type="tertiary", key=key,
                    help="Öppna förklaringen. Fungerar med klick, tryck och tangentbord."):
        st.markdown(text)


METRIC_HELP = {
    "value": "Senast tillgängliga priser och valutakurser används. I kundläget ingår även angiven likvid. Innehaven är demo eller importerade och inget bankkonto är anslutet.",
    "equity": "Andelen som modellen klassificerar som aktier/aktiefonder. Blandfonders underliggande aktieandel är inte genomlyst.",
    "sharpe": "Historisk avkastning över vald riskfri ränta i förhållande till svängningarna. Årsbasis är en skala; historikfönstret väljer datan. Portföljmåttet är före valbara avgifter och kontoskatt.",
    "volatility": "Standardavvikelsen för portföljens dagsavkastningar i SEK, omräknad till årsbasis. Underlaget använder nuvarande vikter konstant över historikfönstret.",
    "largest": "Det största nuvarande innehavet och dess andel av hela portföljvärdet, inklusive likvid i kundläget.",
}
