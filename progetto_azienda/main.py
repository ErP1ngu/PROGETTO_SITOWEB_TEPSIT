import os
import re
import smtplib
from email.message import EmailMessage
from functools import wraps
from io import BytesIO

import pymysql
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

import DB_tool  # modulo con TUTTE le funzioni di accesso al database

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "chiave_segreta_sessione_locale")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # max 4 MB per richiesta

serializer = URLSafeTimedSerializer(app.secret_key)
TOKEN_SCADENZA = 60 * 60 * 24  # il link di conferma vale 24 ore
MAX_IMMAGINE = 2 * 1024 * 1024  # 2 MB

# Dati fissi della pagina "Azienda" (testi, non dati gestiti dal database)
AZIENDA = {
    "nome": "Nordwave S.r.l.",
    "slogan": "Sensori e software per impianti che si controllano da soli.",
    "indirizzo": "Via dell'Industria 24, 20100 Milano",
    "telefono": "+39 02 1234 5678",
    "email": "info@nordwave.example",
    "orari": "Lun–Ven 8:30–18:00",
    "valori": [
        ("Misure affidabili", "Ogni sensore è tarato in laboratorio e viene consegnato con il suo certificato."),
        ("Dati sotto controllo", "I dati dei clienti restano in Europa e viaggiano sempre cifrati."),
        ("Assistenza vera", "Chi risponde al telefono conosce l'impianto e può intervenire subito."),
    ],
    "storia": [
        ("2012", "Nasce Nordwave in un garage di Monza, con due persone e un solo sensore di temperatura."),
        ("2015", "Primo gateway LoRa: i sensori comunicano senza cablaggi fino a 2 km."),
        ("2018", "Apre la sede di Milano con laboratorio di taratura e 15 dipendenti."),
        ("2021", "Esce la piattaforma cloud: allarmi, report e accesso via API."),
        ("2024", "Oltre 400 impianti monitorati in Italia, Francia e Germania."),
    ],
    "servizi": [
        ("Progettazione impianti", "Studiamo il tuo stabilimento e scegliamo dove posizionare i sensori."),
        ("Installazione e collaudo", "Un nostro tecnico installa, collega e verifica ogni punto di misura."),
        ("Monitoraggio cloud", "Controlli temperature, umidità e vibrazioni da browser o da telefono."),
        ("Manutenzione predittiva", "Ti avvisiamo prima che un motore si fermi, non dopo."),
    ],
    "faq": [
        ("Posso provare il sistema prima di acquistarlo?", "Sì: per 30 giorni puoi testare un kit con tre sensori e un gateway senza impegno."),
        ("Quanto dura la batteria dei sensori?", "Fino a 5 anni con una misura ogni 10 minuti."),
        ("I dati si possono esportare?", "Con il piano Plus puoi scaricare report PDF e collegarti alle API."),
        ("Come funziona l'assistenza?", "Rispondiamo entro 2 ore lavorative; con il contratto 24/7 anche di notte e nei festivi."),
    ],
}


# ================================================================ utilità
def invia_email(destinatario, oggetto, corpo):
    """Invia una mail via SMTP. Se MAIL_HOST non è configurato (sviluppo)
    stampa il messaggio nel terminale invece di spedirlo."""
    host = os.getenv("MAIL_HOST")
    if not host:
        print(f"\n--- EMAIL (modalità sviluppo) a {destinatario} ---\n{oggetto}\n{corpo}\n")
        return False
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = os.getenv("MAIL_FROM", os.getenv("MAIL_USER", "noreply@nordwave.example"))
    msg["To"] = destinatario
    msg.set_content(corpo)
    with smtplib.SMTP(host, int(os.getenv("MAIL_PORT", "587"))) as smtp:
        smtp.starttls()
        if os.getenv("MAIL_USER"):
            smtp.login(os.getenv("MAIL_USER"), os.getenv("MAIL_PASSWORD", ""))
        smtp.send_message(msg)
    return True


def riconosci_immagine(dati):
    """Controlla i primi byte del file: non ci si fida dell'estensione."""
    if dati.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if dati.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if dati[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if dati[:4] == b"RIFF" and dati[8:12] == b"WEBP":
        return "image/webp"
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Accedi per vedere questa pagina.", "info")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def gestore_required(f):
    """Solo utenti con ruolo 'gestore' (il ruolo viene riletto dal database)."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        utente = DB_tool.get_utente_by_id(session["user_id"])
        if not utente or utente["ruolo"] != "gestore":
            abort(403)
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inietta_utente():
    return {
        "utente_loggato": session.get("username"),
        "is_gestore": session.get("ruolo") == "gestore",
    }


@app.errorhandler(403)
def vietato(_):
    return render_template("errore.html", titolo="Accesso negato",
                           testo="Questa pagina è riservata agli utenti gestori."), 403


@app.errorhandler(413)
def troppo_grande(_):
    flash("Il file è troppo grande (massimo 2 MB).", "error")
    return redirect(request.referrer or url_for("dashboard"))


# ================================================================ pagine pubbliche
@app.route("/")
def index():
    return redirect(url_for("azienda"))


@app.route("/azienda")
def azienda():
    return render_template(
        "azienda.html",
        a=AZIENDA,
        stats=DB_tool.statistiche(),
        evidenza=DB_tool.prodotti_in_evidenza(3),
        team=DB_tool.lista_dipendenti(),
    )


# ================================================================ registrazione + conferma mail
@app.route("/registrazione", methods=["GET", "POST"])
def registrazione():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conferma = request.form.get("conferma", "")

        errori = []
        if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
            errori.append("Lo username deve avere 3–30 caratteri tra lettere, numeri e _.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errori.append("Inserisci un indirizzo email valido.")
        if len(password) < 8:
            errori.append("La password deve avere almeno 8 caratteri.")
        if password != conferma:
            errori.append("Le due password non coincidono.")
        if not errori and DB_tool.get_utente_by_username(username):
            errori.append("Questo username è già in uso.")
        if not errori and DB_tool.get_utente_by_email(email):
            errori.append("Esiste già un account con questa email.")

        if errori:
            for e in errori:
                flash(e, "error")
            return render_template("registrazione.html", username=username, email=email)

        try:
            DB_tool.crea_utente(username, email, generate_password_hash(password))
        except pymysql.err.IntegrityError:
            flash("Username o email già registrati.", "error")
            return render_template("registrazione.html", username=username, email=email)

        token = serializer.dumps(email, salt="conferma-email")
        link = url_for("conferma_email", token=token, _external=True)
        invia_email(
            email, "Conferma il tuo account Nordwave",
            f"Ciao {username},\n\nper attivare l'account apri questo link "
            f"(valido 24 ore):\n{link}\n\nSe non hai richiesto la registrazione ignora questa mail.",
        )
        flash("Registrazione completata. Ti abbiamo inviato una mail: "
              "apri il link per attivare l'account.", "success")
        return redirect(url_for("login"))

    return render_template("registrazione.html")


@app.route("/conferma/<token>")
def conferma_email(token):
    try:
        email = serializer.loads(token, salt="conferma-email", max_age=TOKEN_SCADENZA)
    except SignatureExpired:
        flash("Il link è scaduto. Registrati di nuovo.", "error")
        return redirect(url_for("registrazione"))
    except BadSignature:
        flash("Link di conferma non valido.", "error")
        return redirect(url_for("login"))

    if not DB_tool.get_utente_by_email(email):
        flash("Account non trovato.", "error")
        return redirect(url_for("registrazione"))
    DB_tool.attiva_utente(email)
    flash("Account attivato! Ora puoi accedere.", "success")
    return redirect(url_for("login"))


# ================================================================ login / logout
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        utente = DB_tool.get_utente_by_username(username)

        if not utente or not check_password_hash(utente["password_hash"], password):
            error = "Credenziali non valide."
        elif not utente["attivo"]:
            error = "Account non ancora attivato: apri il link che ti abbiamo inviato via email."
        else:
            session.clear()
            session["user_id"] = utente["id"]
            session["username"] = utente["username"]
            session["ruolo"] = utente["ruolo"]
            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ================================================================ dashboard prodotti
def _numero(valore):
    try:
        return float(valore.replace(",", ".")) if valore else None
    except ValueError:
        return None


@app.route("/dashboard")
@login_required
def dashboard():
    # Ricerca e filtri arrivano dal form (GET) e vengono eseguiti nel database
    filtri = {
        "q": request.args.get("q", "").strip(),
        "categoria": request.args.get("categoria", type=int),
        "prezzo_min": request.args.get("prezzo_min", ""),
        "prezzo_max": request.args.get("prezzo_max", ""),
        "ordine": request.args.get("ordine", "nome_asc"),
    }
    prodotti = DB_tool.cerca_prodotti(
        testo=filtri["q"],
        categoria_id=filtri["categoria"],
        prezzo_min=_numero(filtri["prezzo_min"]),
        prezzo_max=_numero(filtri["prezzo_max"]),
        ordine=filtri["ordine"],
    )
    return render_template(
        "dashboard.html",
        username=session.get("username"),
        prodotti=prodotti,
        categorie=DB_tool.lista_categorie(),
        stats=DB_tool.statistiche(),
        filtri=filtri,
    )


# ---------------------------------------------------------------- CRUD prodotti (solo gestori)
def _leggi_form_prodotto():
    """Valida il form e restituisce (dati, errori)."""
    nome = request.form.get("nome", "").strip()
    descrizione = request.form.get("descrizione", "").strip()
    categoria_id = request.form.get("categoria_id", type=int)
    errori = []
    try:
        prezzo = round(float(request.form.get("prezzo", "").replace(",", ".")), 2)
        if prezzo < 0:
            raise ValueError
    except ValueError:
        prezzo = None
        errori.append("Il prezzo deve essere un numero maggiore o uguale a 0.")
    quantita = request.form.get("quantita", type=int)
    if quantita is None or quantita < 0:
        errori.append("La quantità deve essere un numero intero maggiore o uguale a 0.")
    if not nome or len(nome) > 100:
        errori.append("Il nome è obbligatorio (massimo 100 caratteri).")

    immagine, mime = None, None
    file = request.files.get("immagine")
    if file and file.filename:
        immagine = file.read()
        mime = riconosci_immagine(immagine)
        if len(immagine) > MAX_IMMAGINE:
            errori.append("L'immagine supera i 2 MB.")
        elif not mime:
            errori.append("Formato immagine non valido (usa PNG, JPG, GIF o WEBP).")

    dati = dict(nome=nome, descrizione=descrizione, prezzo=prezzo, quantita=quantita,
                categoria_id=categoria_id, immagine=immagine, immagine_mime=mime)
    return dati, errori


@app.route("/prodotti/nuovo", methods=["GET", "POST"])
@gestore_required
def prodotto_nuovo():
    if request.method == "POST":
        dati, errori = _leggi_form_prodotto()
        if not errori:
            DB_tool.crea_prodotto(**dati)
            flash("Prodotto creato.", "success")
            return redirect(url_for("dashboard"))
        for e in errori:
            flash(e, "error")
        return render_template("prodotto_form.html", p=dati,
                               categorie=DB_tool.lista_categorie(), nuovo=True)
    return render_template("prodotto_form.html", p={}, categorie=DB_tool.lista_categorie(), nuovo=True)


@app.route("/prodotti/<int:pid>/modifica", methods=["GET", "POST"])
@gestore_required
def prodotto_modifica(pid):
    esistente = DB_tool.get_prodotto(pid)
    if not esistente:
        abort(404)
    if request.method == "POST":
        dati, errori = _leggi_form_prodotto()
        if not errori:
            DB_tool.aggiorna_prodotto(
                pid, **dati, rimuovi_immagine=bool(request.form.get("rimuovi_immagine")))
            flash("Prodotto aggiornato.", "success")
            return redirect(url_for("dashboard"))
        for e in errori:
            flash(e, "error")
        dati.update(id=pid, ha_immagine=esistente["ha_immagine"])
        return render_template("prodotto_form.html", p=dati,
                               categorie=DB_tool.lista_categorie(), nuovo=False)
    return render_template("prodotto_form.html", p=esistente,
                           categorie=DB_tool.lista_categorie(), nuovo=False)


@app.route("/prodotti/<int:pid>/elimina", methods=["POST"])
@gestore_required
def prodotto_elimina(pid):
    DB_tool.elimina_prodotto(pid)
    flash("Prodotto eliminato.", "success")
    return redirect(url_for("dashboard"))


@app.route("/prodotti/<int:pid>/immagine")
def prodotto_immagine(pid):
    riga = DB_tool.get_immagine_prodotto(pid)
    if not riga or not riga["immagine"]:
        abort(404)
    return send_file(BytesIO(riga["immagine"]), mimetype=riga["immagine_mime"] or "image/jpeg")


# ================================================================ gestione utenti (solo gestori)
@app.route("/gestione/utenti")
@gestore_required
def gestione_utenti():
    return render_template("utenti.html", utenti=DB_tool.lista_utenti())


@app.route("/gestione/utenti/<int:uid>/ruolo", methods=["POST"])
@gestore_required
def utente_ruolo(uid):
    nuovo = request.form.get("ruolo")
    utente = DB_tool.get_utente_by_id(uid)
    if not utente or nuovo not in ("base", "gestore"):
        abort(400)
    if utente["ruolo"] == "gestore" and nuovo == "base" and DB_tool.conta_gestori() <= 1:
        flash("Deve restare almeno un gestore attivo.", "error")
    else:
        DB_tool.aggiorna_ruolo(uid, nuovo)
        if uid == session["user_id"]:
            session["ruolo"] = nuovo
        flash(f"Ruolo di {utente['username']} aggiornato.", "success")
    return redirect(url_for("gestione_utenti"))


@app.route("/gestione/utenti/<int:uid>/elimina", methods=["POST"])
@gestore_required
def utente_elimina(uid):
    if uid == session["user_id"]:
        flash("Non puoi eliminare il tuo account.", "error")
    else:
        DB_tool.elimina_utente(uid)
        flash("Utente eliminato.", "success")
    return redirect(url_for("gestione_utenti"))


if __name__ == "__main__":
    app.run(debug=True)
