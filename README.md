# ExpenseHandler

En webbapp för att hålla koll på vad du handlar för. Ladda upp kvittokopior från Kivra (PDF)
eller lägg in köp för hand, sortera varorna i kategorier och följ upp utgifterna över tid.
Flera personer kan använda samma app; var och en loggar in och ser bara sina egna kvitton.

Appen finns på svenska och engelska (välj språk i sidomenyn).

## Kom igång

Kräver Python 3.12 eller senare.

1. Installera beroenden (en gång), från mappen där koden ligger:

   ```bash
   pip install -r requirements.txt
   ```

2. Starta appen från samma mapp:

   ```bash
   python -m streamlit run app.py
   ```

   Appen öppnas i webbläsaren på `http://localhost:8501`. Starta den alltid från kodmappen,
   annars används inte säkerhetsinställningarna i `.streamlit/config.toml`.

## Konto och inloggning

- Skapa ett konto under fliken **Skapa konto**. Namnet får vara högst 50 tecken och lösenordet
  8–128 tecken. Namn som bara skiljer sig i stora/små bokstäver ("Anna" och "anna") räknas som
  samma namn.
- Logga in med exakt det namn du registrerade (stora/små bokstäver spelar roll).
- Efter fem felaktiga lösenord i rad låses namnet i 30 sekunder.
- Du loggas ut när du klickar **Logga ut**, laddar om sidan eller stänger fliken.

### Glömt lösenord

Appen kan inte skicka e-post. Den som kör appen sätter ett nytt lösenord på samma dator:

```bash
python scripts/reset_password.py "Ditt namn"
```

Du får skriva det nya lösenordet två gånger; det visas inte på skärmen.

## Användning

- **Aktuellt kvitto:** ladda upp en kvittokopia från Kivra (PDF, högst 5 MB) eller lägg till köp
  för hand. Kontrollera och ändra kategorierna i tabellen, välj datum och klicka **Spara**. Appen
  kommer ihåg vilken kategori du valde för en vara till nästa gång.
  Om varorna inte summerar till kvittots "Betalat" visas en gul varning; kontrollera då att alla
  varor finns med och har rätt pris innan du sparar.
- **Historik:** välj en period och se totalsumma, utgifter per kategori och alla köp.
  Här kan du också ta bort allt som sparats ett visst datum.

## Begränsningar

- **Bara på din egen dator.** Appen lyssnar bara på `localhost`, så den går inte att nå från
  andra datorer. Det är avsiktligt.
- **Databasen är inte krypterad.** Allt sparas i filen `expenses.db` i kodmappen. Inloggningen
  skyddar användarna från varandra i appen, men den som kommer åt datorn kan läsa filen direkt.
  Lösenorden sparas aldrig i klartext.
- **Ingen säkerhetskopia.** Försvinner eller skadas `expenses.db` är all historik borta.
  Kopiera filen till en säker plats då och då (när appen är stängd).
- **Inget byte av lösenord eller borttagning av konto i appen.** Lösenord byts med skriptet ovan.
- **Bara kvittokopior från Kivra** kan läsas in från PDF, oavsett butik (till exempel ICA, Jula,
  Kjell & Co, Rusta och Stadium). Ladda ner kvittot som PDF i Kivra. Andra kvitton får läggas in
  för hand.
- **Registreringen visar om ett namn redan är upptaget**, och vem som helst kan låsa ett namn i
  30 sekunder genom att skriva fel lösenord fem gånger.
- **Ingen automatisk utloggning** så länge fliken är öppen. Logga ut om andra använder datorn.
- **Språket sparas per webbläsarflik** (i adressen, `?lang=sv`), inte per användare. Kategorier
  du har skapat översätts inte när du byter språk.
- **Vissa texter är alltid på engelska**, till exempel "Upload" och "Press Enter to submit form",
  eftersom de kommer från Streamlit. Priser i inmatningsfält och tabeller visas med decimalpunkt.
- Byter du språk medan du är på **Historik** hoppar appen tillbaka till första fliken.
