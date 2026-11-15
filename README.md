# ExpenseHandler

[![Tests](https://github.com/MagnusHansson50/expenseHandler/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/MagnusHansson50/expenseHandler/actions/workflows/tests.yml)

ExpenseHandler håller koll på vad du handlar för genom att läsa in dina kvitton och sortera
varorna i kategorier, så att du kan följa upp dina utgifter över tid.

**Live:** ingen live-version, avsiktligt. Appen körs på din egen dator och dina kvitton lämnar
den aldrig. Ladda ner programmet för Windows under
[Releases](https://github.com/MagnusHansson50/expenseHandler/releases) eller kör det från koden.

## Vad det gör

Appen läser in PDF-kvitton från Kivra och Willys, plockar ut varor och priser (rabatter och
pant räknas in i varan) och kontrollerar att summan stämmer med det du betalade. Du sorterar
varorna i egna kategorier, och appen kommer ihåg ditt val till nästa kvitto. I historiken ser du
vad du har lagt per kategori och period. Flera personer kan använda samma program med varsitt
konto, och ingen ser någon annans kvitton.

Appen finns på svenska och engelska (välj språk i sidomenyn).

## Kom igång

Det finns två sätt: ladda ner programmet för Windows, eller köra appen från koden.

### Krav

- **Programmet för Windows:** Windows 10 eller 11. Inget annat behöver installeras.
- **Från koden:** Python 3.12 eller senare (Windows, macOS eller Linux).
- **Inga externa tjänster:** inga konton, API-nycklar eller internetanslutning behövs. Allt körs
  lokalt.

### Programmet för Windows

1. Ladda ner den senaste `ExpenseHandler-vX.Y.Z-windows.zip` under
   [Releases](https://github.com/MagnusHansson50/expenseHandler/releases).
2. Packa upp zip-filen, till exempel i `Dokument`.
3. Starta `ExpenseHandler\ExpenseHandler.exe`. Första gången kan Windows visa
   "Windows skyddade datorn" eftersom programmet inte är signerat. Klicka **Mer information**
   och sedan **Kör ändå**.
4. Ett svart fönster öppnas och appen visas i webbläsaren efter några sekunder. Låt fönstret vara
   öppet medan du använder appen; stäng det för att avsluta.

Dina data sparas i `%APPDATA%\ExpenseHandler\expenses.db` (skriv `%APPDATA%` i
Utforskarens adressfält för att hitta mappen), inte i programmappen. Du kan därför byta till en
ny version genom att packa upp den nya zip-filen och ta bort den gamla mappen; dina kvitton
finns kvar.

### Från koden

1. Hämta koden och installera beroenden (en gång):

   ```bash
   git clone https://github.com/MagnusHansson50/expenseHandler.git
   cd expenseHandler
   pip install -r requirements.txt
   ```

2. Starta appen från samma mapp:

   ```bash
   python -m streamlit run app.py
   ```

   Appen öppnas i webbläsaren på `http://localhost:8501`. Starta den alltid från kodmappen,
   annars används inte säkerhetsinställningarna i `.streamlit/config.toml`. Här sparas
   databasen som `expenses.db` i kodmappen.

   Vill du köra från koden men som programmet gör (data i `%APPDATA%`, ledig port, webbläsaren
   öppnas automatiskt) startar du `python desktop/launcher.py` i stället.

### Konfiguration

Ingen konfiguration krävs, och det finns ingen `.env`-fil. Säkerhetsinställningar och utseende
finns i `.streamlit/config.toml`.

Valfritt: miljövariabeln `EXPENSES_DB_PATH` pekar ut en annan databasfil, till exempel för att
prova appen utan att röra dina riktiga kvitton (PowerShell):

```powershell
$env:EXPENSES_DB_PATH = "C:\temp\prova.db"; python -m streamlit run app.py
```

## Konto och inloggning

- Skapa ett konto under fliken **Skapa konto**. Namnet får vara högst 50 tecken och lösenordet
  8–128 tecken.
- Stora och små bokstäver spelar ingen roll i namnet, men i lösenordet: har du registrerat
  "Anna" loggar du in som "anna" också, och ingen annan kan skapa kontot "anna".
- Efter fem felaktiga lösenord i rad låses namnet i 30 sekunder.
- Du loggas ut när du klickar **Logga ut**, laddar om sidan eller stänger fliken.

### Inställningar

Under **⚙️ Inställningar** i sidomenyn väljer du **Högsta belopp per vara**. Gränsen fångar
felskrivningar, till exempel 15900 i stället för 159,00: ett pris över gränsen går inte att
spara, och appen säger vilken rad som är fel. Från början är gränsen 100 000 kr. Köper du något
dyrare, till exempel en bilreparation, höjer du den (mellan 1 000 och 10 000 000 kr) och klickar
**💾 Spara inställningar**. Inställningen gäller bara ditt konto.

### Ta bort ditt konto

Öppna **🗑️ Ta bort mitt konto** i sidomenyn, skriv ditt lösenord, kryssa i rutan och klicka
**Ta bort kontot**. Kontot, dina kategorier och hela din historik raderas för gott och kan inte
återställas. Namnet blir ledigt och kan registreras igen.

### Glömt lösenord

Appen kan inte skicka e-post. Du sätter ett nytt lösenord på samma dator. Med programmet:
öppna mappen `ExpenseHandler` i Utforskaren, högerklicka och välj **Öppna i terminal**, och skriv
(med `.\` först, annars hittar PowerShell inte programmet)

```powershell
.\ExpenseHandler.exe --reset-password "Ditt namn"
```

Från koden:

```bash
python scripts/reset_password.py "Ditt namn"
```

Du får skriva det nya lösenordet två gånger; det visas inte på skärmen.

## Användning

- **Aktuellt kvitto:** ladda upp en kvittokopia från Kivra eller ett digitalt kvitto från Willys
  (PDF, högst 5 MB) eller lägg till köp för hand. Rabatter och pant räknas in i varan de hör
  till; en mängdrabatt som gäller flera varor (till exempel `Willys Plus:CHOKLAD`) blir en egen
  rad. Kontrollera och ändra vara, pris och kategori direkt i tabellen, välj datum och klicka
  **Spara**. Appen kommer ihåg vilken kategori du valde för en vara till nästa gång.
  - **Saknas en vara** på kvittot lägger du till den under **➕ Lägg till en vara som saknas**
    under tabellen (eller i tabellens tomma rad längst ner).
  - **Ska en vara inte vara med**, till exempel något du köpte åt någon annan, tar du bort den
    under **🗑️ Ta bort en vara** (raderna visas med nummer, så två varor med samma namn går att
    skilja åt), med **🗑️ Ta bort från kvittot** i rutan för varor utan kategori, eller genom att
    markera raden i tabellens vänsterkant och trycka Delete. En borttagen vara sparas inte och
    appen lägger den inte på minnet.
  - **Under totalen** jämför appen listan med kvittots "Betalat" så länge du redigerar: en gul
    varning säger hur mycket som saknas eller är för mycket, och när det stämmer står det
    "✔️ Listan stämmer". Varor du tagit bort från kvittot räknas av, så de räknas inte som saknade.
  Får varor från ett uppladdat kvitto ingen kategori (de står som "Övrigt") öppnas en ruta,
  **🏷️ Varor utan kategori**, som visar en vara i taget. Klicka på en kategori, så sparas den och
  nästa vara visas. **Hoppa över** lämnar varan som den är, och **Avsluta** eller krysset stänger
  rutan med det du redan valt. Rutan går att öppna igen med knappen **🏷️ Gå igenom varor utan
  kategori** ovanför tabellen, som också gäller varor du lagt till för hand. Varor du hoppar över
  frågar appen om igen nästa gång; vill du att en vara ska ligga i "Övrigt" väljer du det i
  rutan, så frågar appen inte mer.
  Saknas en kategori kan du skapa den direkt i rutan (**Ny kategori**); den läggs till bland
  kategorierna och du väljer den med ett klick. Under **🗑️ Ta bort en kategori** i rutan kan du
  ta bort en kategori (kryssa i rutan för att bekräfta), precis som under **Hantera kategorier**.
  Köp du redan sparat behåller kategorin; varor i det osparade kvittot hamnar i "Övrigt".
  Nya kategorier skapar du under **⚙️ Hantera kategorier** eller i rutan. Liknar namnet en
  kategori du redan har, så att bara stora och små bokstäver eller mellanslag skiljer (till
  exempel "mjölk" när du har "Mjölk"), frågar appen först: **Lägg till ändå** ger dig båda,
  **Avbryt** lägger inte till något. Exakt samma namn går inte att lägga till.
- **Historik:** välj en period och se totalsumma, utgifter per kategori och alla köp.
  Vill du bara se vissa kategorier väljer du dem under **Kategorier** (tomt betyder alla).
  Totalsumman, antalet köp, diagrammet och listan visar då bara de kategorierna, och valet står
  kvar när du byter period. Kategorier du tagit bort men som finns på sparade köp går också att
  välja. Filtret gäller inte borttagning av ett datum (alla köp det datumet tas bort) eller
  säkerhetskopian och CSV-filen (de innehåller allt).
  Har du sparat ett köp med fel kategori kan du rätta den under **Visa alla köp**: klicka på
  kategorin, välj en annan och klicka **💾 Spara ändringar**. Appen kommer då ihåg den nya
  kategorin för varan till nästa kvitto. Datum, vara och pris går inte att ändra; är något av
  dem fel, ta bort det datumets köp och lägg in dem igen.
  Här kan du också ta bort allt som sparats ett visst datum.

## Tillgänglighet

Målet är WCAG 2.1 nivå AA. Det här är kontrollerat, automatiskt vid varje ändring:

- **Kontrast:** text har minst 4,5 : 1 mot alla bakgrunder och kanterna på fält och knappar
  minst 3 : 1.
- **Skärmläsare:** sidans språk följer språkvalet, så svensk text läses med svensk röst.
  Varje vy granskas med verktyget axe-core.
- **Tangentbord:** allt går att göra utan mus. Tab och Skift+Tab flyttar mellan fälten,
  piltangenterna byter flik, Enter trycker på knappar och öppnar sektioner, och i rutan för
  varor utan kategori väljer du kategori med Tab och Enter. Det första Tab-stoppet är en länk
  som hoppar direkt till innehållet.

Det här fungerar sämre, eftersom det styrs av Streamlit och inte av appen:

- Efter en åtgärd, till exempel när du lagt till en vara, ritas sidan om och fokus hamnar
  överst igen.
- Tabellerna går att nå med tangentbordet och har en dold tabell för skärmläsare, men de är
  svårare att använda än vanliga fält. Varor kan också läggas till och tas bort med formulären
  under tabellen.
- Några av Streamlits egna texter är på engelska ("Skip to main content", "Show password",
  "5MB per file").
- Emojierna i flikar och knappar läses upp av skärmläsare.

Appen är inte provad med en riktig skärmläsare (till exempel NVDA).

## Säkerhetskopiera och byta dator

Under **Historik → 💾 Säkerhetskopia**:

- **Ladda ner säkerhetskopia** ger en fil, till exempel `ExpenseHandler-Anna-2026-11-05.json`,
  med dina kategorier, dina kategorival, hela din historik och ditt högsta belopp per vara (om du
  har ändrat det). Lösenordet följer inte med.
  Filen är inte krypterad och innehåller alla dina köp, så förvara den säkert (till exempel på
  ett USB-minne eller i din egen molnlagring).
- **Ladda ner historiken som CSV (Excel)** ger alla köp som en tabell som går att öppna i Excel.
  Den kan inte läsas in igen; använd säkerhetskopian till det.
- **Läs in en säkerhetskopia** lägger till det som finns i filen och som du inte redan har.
  Det du redan har lämnas orört, och läser du in samma fil två gånger läggs inget till andra gången.
  Filens högsta belopp per vara används bara om du inte har valt ett eget.
  Är något fel i filen läses ingenting in, och du får se vad som är fel.

Byta dator: ladda ner en säkerhetskopia på den gamla datorn, installera programmet på den nya,
skapa ett konto (eller logga in) och läs in filen.

## Arkitektur

Koden är uppdelad i lager där beroenden bara går nedåt; ett test stoppar ändringar som bryter
mot det. Gränssnittet (`app.py` och `ui/`) visar och tar emot, men innehåller inga affärsregler.
Flöden som behöver databasen ligger i `services/`, all ren logik (kvittotolkning, beräkningar,
regler, översättningar) i `core/` utan Streamlit eller databas, och all SQLite-åtkomst i
`integrations/db.py`. Skrivbordsprogrammet är ett tunt skal runt samma app.

```
expenseHandler/
├── app.py              # Det Streamlit kör: inloggning, sidomeny, flikar
├── ui/                 # Resten av gränssnittet: kvitto, historik, popup, inställningar, utseende
├── services/           # Flöden som kombinerar logik och databas
├── core/               # Ren logik: kvittoformat, regler, beräkningar, översättningar
├── integrations/db.py  # All databasåtkomst (SQLite), med användarisolering och schemaversion
├── desktop/            # Skrivbordsprogrammet: launcher, PyInstaller-bygge, starttest
├── scripts/            # Återställning av lösenord från kommandoraden
├── tests/              # pytest, inklusive tester av gränssnittet och tillgänglighet (tests/a11y)
└── .github/workflows/  # CI: lint, tester, tillgänglighetsgranskning, bygge och release
```

## Teknisk stack

| Komponent | Val | Anledning |
|---|---|---|
| Gränssnitt | Streamlit | Formulär, tabeller och diagram i ren Python; körs lokalt i webbläsaren |
| Data | pandas | Kvittorader och historik som tabeller, summor per kategori |
| PDF | pypdf | Underhållen och ren Python; ersatte PyPDF2, som har kända säkerhetsbrister |
| Databas | SQLite | En fil på den egna datorn utan server, med transaktioner och versionshanterat schema |
| Lösenord | scrypt (Pythons standardbibliotek) | Saltad, långsam hash utan extra beroenden |
| Skrivbordsprogram | PyInstaller | Python och alla bibliotek i en mapp; inget att installera för användaren |
| Tester | pytest och Streamlits AppTest | Drygt 760 tester, även av gränssnittet |
| Kodkontroll | Ruff | Snabb lint som stoppar pipelinen vid fel |
| Tillgänglighet | Playwright och axe-core | Granskar varje vy mot WCAG 2.1 AA och provar appen med bara tangentbordet |
| CI/CD | GitHub Actions | Lint, tester på Windows och Ubuntu, tillgänglighet och bygge; en release vid varje versionstagg |

## Utveckling

```bash
pip install -r requirements-dev.txt
python -m pytest              # alla tester
python -m ruff check .        # kodkontroll
```

Tillgänglighetsgranskningen kräver Playwright och en webbläsare:

```bash
pip install -r requirements-a11y.txt
python -m playwright install chromium
python -m pytest tests/a11y
```

Bygga skrivbordsprogrammet:

```bash
pip install -r requirements-build.txt
python -m PyInstaller desktop/ExpenseHandler.spec --noconfirm
```

## Begränsningar

- **Bara på din egen dator.** Appen lyssnar bara på `localhost`, så den går inte att nå från
  andra datorer. Det är avsiktligt.
- **Databasen är inte krypterad.** Allt sparas i filen `expenses.db` (i `%APPDATA%\ExpenseHandler`
  med programmet, annars i kodmappen). Inloggningen
  skyddar användarna från varandra i appen, men den som kommer åt datorn kan läsa filen direkt.
  Lösenorden sparas aldrig i klartext.
- **Säkerhetskopior görs inte automatiskt.** Försvinner eller skadas `expenses.db` är allt som
  inte finns i en säkerhetskopia borta. Ladda ner en säkerhetskopia då och då. Öppnar du en databas som
  en nyare version av programmet har använt, säger en äldre version ifrån i stället för att
  ändra den; installera då den nyaste versionen.
- **Bara Windows som färdigt program**, och det är inte signerat (därav varningen vid första
  starten). Programmet uppdaterar sig inte självt: ladda ner nya versioner från Releases.
  Det är stort (cirka 200 MB uppackat) eftersom Python och alla bibliotek följer med.
- **Inget byte av lösenord i appen.** Lösenord byts med skriptet ovan. Har du glömt lösenordet
  och vill ta bort kontot sätter du först ett nytt lösenord med skriptet.
- **En borttagning går inte att ångra.** Vill du spara din historik, ladda ner en
  säkerhetskopia innan du tar bort kontot. Säkerhetskopior och kopior av `expenses.db` som du
  har sparat tidigare innehåller fortfarande det borttagna.
- **Säkerhetskopian är inte krypterad** och kan inte skyddas med lösenord. En säkerhetskopia från
  en nyare version av programmet kan inte läsas in av en äldre; uppdatera då programmet först.
- **Högsta belopp per vara är som mest 10 000 000 kr**, även om du höjer gränsen.
- **Bara ljust utseende.** Appen har ett eget ljust tema och inget mörkt läge.
- **Bara två sorters PDF-kvitton kan läsas in:** kvittokopior från Kivra, oavsett butik (till
  exempel ICA, Jula, Kjell & Co, Rusta och Stadium; ladda ner kvittot som PDF i Kivra), och
  digitala kvitton från Willys. Andra kvitton ger meddelandet att formatet inte känns igen och
  får läggas in för hand.
- **Willys-kvitton är bara provade från självscanning.** Ett kvitto från vanlig kassa kan se
  annorlunda ut; läses en rad fel syns det som en varning om att summan inte stämmer.
- **I sparade köp går bara kategorin att ändra**, inte datum, vara eller pris. Ett köp som
  sparades med en kategori du sedan har tagit bort visar den gamla kategorin tills du byter den.
- **Registreringen visar om ett namn redan är upptaget**, och vem som helst kan låsa ett namn i
  30 sekunder genom att skriva fel lösenord fem gånger.
- **Ingen automatisk utloggning** så länge fliken är öppen. Logga ut om andra använder datorn.
- **Språket sparas per webbläsarflik** (i adressen, `?lang=sv`), inte per användare. Kategorier
  du har skapat översätts inte när du byter språk.
- **Vissa texter är alltid på engelska**, till exempel "Upload" och "Press Enter to submit form",
  eftersom de kommer från Streamlit. Priser i inmatningsfält och tabeller visas med decimalpunkt.
- Byter du språk medan du är på **Historik** hoppar appen tillbaka till första fliken.
