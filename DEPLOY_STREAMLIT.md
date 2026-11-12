# Publicering i Streamlit Community Cloud

Detta projekt innehåller den aktuella Avanza-demon. Appkod, beräkningsmoduler, fondkatalog, tema och beroenden har kopierats från den verifierade lokala versionen. Inga Cloudflare-tunnlar behövs för denna publicering.

## Inställningar

| Fält | Värde |
| --- | --- |
| GitHub repository | `fanasno/Avanza-portfoljkollen` |
| Branch | `main` |
| Main file path | `app.py` |
| Python version | `3.13` under Advanced settings |
| Önskad appadress | `avanza-portfoljkollen.streamlit.app`, om namnet är ledigt |

1. Logga in på https://share.streamlit.io/ med kontot som administrerar `fanasno`.
2. Välj **Create app**, därefter **Yup, I have an app**.
3. Ange repository, branch och main file path enligt tabellen, eller klistra in GitHub-adressen till `app.py`.
4. Under **Advanced settings**, välj Python 3.13. Inga apphemligheter krävs av den nuvarande demon.
5. Klicka **Deploy** och vänta tills appen har startat. Använd den adress Streamlit faktiskt tilldelar; det önskade adressnamnet är inte reserverat.

`requirements.txt` har låsta paketversioner och `.streamlit/config.toml` innehåller appens tema. Streamlit hämtar kod och paket från detta repository och bygger om appen efter uppdateringar på `main`.

## Data och verifiering

Marknadsdata hämtas från appens befintliga källor när den används. Lokala pris-cacher och uppladdade kundfiler ingår inte i projektet. Om dataleverantörer blockerar molnserverns trafik visas appens befintliga datafel; historik ersätts inte automatiskt med exempelkurser.

Efter publicering: öppna Översikt, Portföljkollen och Simulatorn, kontrollera verklig fondhistorik och avgifts-/skatteval samt att sidan fungerar efter omladdning.

Regressionstester kan köras med `python -m unittest discover -s tests -v`.

Officiella instruktioner: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
