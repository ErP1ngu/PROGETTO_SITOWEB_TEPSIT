# Nordwave – applicativo web Flask + MySQL

## Avvio
1. In phpMyAdmin clicca sul database **rligabue** (server 10.10.0.10) → **Importa** → `database.sql`.
2. `pip install -r requirements.txt`
3. Connessione predefinita: host `10.10.0.10`, utente `ligabue.ruben`, database `rligabue`. La password viene chiesta nel terminale all'avvio, oppure impostala con `DB_PASSWORD` (es. `export DB_PASSWORD=...`).
4. `python test_db.py` → stampa i dati letti dal database (punto 1 della consegna).
5. `python main.py` → http://127.0.0.1:5000

## Utenti di prova
| username | password   | ruolo   |
|----------|------------|---------|
| admin    | Admin123!  | gestore |
| utente   | Utente123! | base    |

## Email di conferma
Senza `MAIL_HOST` il link di attivazione viene stampato nel terminale.
Per spedirla davvero: `MAIL_HOST MAIL_PORT MAIL_USER MAIL_PASSWORD MAIL_FROM`.

## Esportare il database (punto 2)
phpMyAdmin → seleziona `rligabue` → **Esporta** → metodo *Personalizzato* → formato SQL →
spunta "Aggiungi DROP TABLE" → **Esegui**. Il file ottenuto sostituisce `database.sql`.

## Struttura
- `main.py` rotte, ruoli, registrazione, upload immagini
- `DB_tool.py` tutte le funzioni di accesso al database (query parametrizzate)
- `templates/`, `static/style.css`
