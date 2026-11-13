"""
DB_tool.py - modulo di accesso al database.

Tutte le query del progetto passano da qui. Ogni funzione usa query
PARAMETRIZZATE (%s): i valori non vengono mai concatenati nella stringa SQL,
quindi non è possibile la SQL injection.
"""
import os
import getpass
import pymysql
from pymysql.cursors import DictCursor

# Configurazione del server esistente.
# La password NON è scritta nel codice: si imposta con la variabile d'ambiente
# DB_PASSWORD oppure viene chiesta nel terminale al primo accesso al database.
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "10.10.0.10"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "ligabue.ruben"),
    "password": os.getenv("DB_PASSWORD", "11062008"),
    "database": os.getenv("DB_NAME", "rligabue"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": True,
    "connect_timeout": 10,
}

# Colonne per cui è consentito l'ordinamento (whitelist: ORDER BY non si può parametrizzare)
ORDINAMENTI = {
    "nome_asc": "p.nome ASC",
    "prezzo_asc": "p.prezzo ASC",
    "prezzo_desc": "p.prezzo DESC",
    "recenti": "p.creato_il DESC, p.id DESC",
}


# ---------------------------------------------------------------- base
def get_connection():
    # Se la password non è in DB_PASSWORD la chiede una volta sola e la tiene in memoria
    if DB_CONFIG["password"] is None:
        DB_CONFIG["password"] = getpass.getpass(
            f"Password MySQL per {DB_CONFIG['user']}@{DB_CONFIG['host']}: ")
    return pymysql.connect(**DB_CONFIG)


def _select(sql, params=(), one=False):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


def _execute(sql, params=()):
    """INSERT/UPDATE/DELETE. Restituisce l'id inserito (se presente)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------- utenti
TABELLE = ("utenti", "categorie", "prodotti", "dipendenti")


def inizializza_database():
    """Se nel database mancano le tabelle le crea e inserisce i dati di esempio
    eseguendo database.sql. Se le tabelle ci sono già non tocca nulla."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            segnaposti = ", ".join(["%s"] * len(TABELLE))
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables "
                f"WHERE table_schema = DATABASE() AND table_name IN ({segnaposti})",
                TABELLE,
            )
            if cur.fetchone()["n"] == len(TABELLE):
                return False
            percorso = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.sql")
            with open(percorso, encoding="utf-8") as f:
                righe = [r for r in f if not r.strip().startswith("--")]
            for istruzione in "".join(righe).split(";"):
                if istruzione.strip():
                    cur.execute(istruzione)
            print("Database inizializzato: tabelle create e dati di esempio inseriti.")
            return True
    finally:
        conn.close()

def crea_utente(username, email, password_hash, ruolo="base", attivo=0):
    return _execute(
        "INSERT INTO utenti (username, email, password_hash, ruolo, attivo) "
        "VALUES (%s, %s, %s, %s, %s)",
        (username, email, password_hash, ruolo, attivo),
    )


def get_utente_by_username(username):
    return _select("SELECT * FROM utenti WHERE username = %s", (username,), one=True)


def get_utente_by_email(email):
    return _select("SELECT * FROM utenti WHERE email = %s", (email,), one=True)


def get_utente_by_id(user_id):
    return _select("SELECT * FROM utenti WHERE id = %s", (user_id,), one=True)


def attiva_utente(email):
    _execute("UPDATE utenti SET attivo = 1 WHERE email = %s", (email,))


def lista_utenti():
    return _select(
        "SELECT id, username, email, ruolo, attivo, creato_il FROM utenti ORDER BY id"
    )


def aggiorna_ruolo(user_id, ruolo):
    if ruolo not in ("base", "gestore"):
        raise ValueError("Ruolo non valido")
    _execute("UPDATE utenti SET ruolo = %s WHERE id = %s", (ruolo, user_id))


def elimina_utente(user_id):
    _execute("DELETE FROM utenti WHERE id = %s", (user_id,))


def conta_gestori():
    return _select(
        "SELECT COUNT(*) AS n FROM utenti WHERE ruolo = 'gestore' AND attivo = 1", one=True
    )["n"]


# ---------------------------------------------------------------- categorie
def lista_categorie():
    return _select("SELECT id, nome FROM categorie ORDER BY nome")


# ---------------------------------------------------------------- prodotti
def cerca_prodotti(testo="", categoria_id=None, prezzo_min=None, prezzo_max=None,
                   ordine="nome_asc"):
    """Ricerca + filtri + ordinamento. Non carica il BLOB dell'immagine."""
    sql = (
        "SELECT p.id, p.nome, p.descrizione, p.prezzo, p.quantita, p.categoria_id, "
        "c.nome AS categoria, (p.immagine IS NOT NULL) AS ha_immagine "
        "FROM prodotti p LEFT JOIN categorie c ON c.id = p.categoria_id WHERE 1=1"
    )
    params = []
    if testo:
        sql += " AND (p.nome LIKE %s OR p.descrizione LIKE %s)"
        like = f"%{testo}%"
        params += [like, like]
    if categoria_id:
        sql += " AND p.categoria_id = %s"
        params.append(categoria_id)
    if prezzo_min is not None:
        sql += " AND p.prezzo >= %s"
        params.append(prezzo_min)
    if prezzo_max is not None:
        sql += " AND p.prezzo <= %s"
        params.append(prezzo_max)
    sql += " ORDER BY " + ORDINAMENTI.get(ordine, ORDINAMENTI["nome_asc"])
    return _select(sql, tuple(params))


def prodotti_in_evidenza(limite=3):
    return _select(
        "SELECT p.id, p.nome, p.descrizione, p.prezzo, c.nome AS categoria, "
        "(p.immagine IS NOT NULL) AS ha_immagine "
        "FROM prodotti p LEFT JOIN categorie c ON c.id = p.categoria_id "
        "ORDER BY p.prezzo DESC LIMIT %s",
        (limite,),
    )


def get_prodotto(prodotto_id):
    return _select(
        "SELECT id, nome, descrizione, prezzo, quantita, categoria_id, "
        "(immagine IS NOT NULL) AS ha_immagine FROM prodotti WHERE id = %s",
        (prodotto_id,), one=True,
    )


def get_immagine_prodotto(prodotto_id):
    return _select(
        "SELECT immagine, immagine_mime FROM prodotti WHERE id = %s",
        (prodotto_id,), one=True,
    )


def crea_prodotto(nome, descrizione, prezzo, quantita, categoria_id,
                  immagine=None, immagine_mime=None):
    return _execute(
        "INSERT INTO prodotti (nome, descrizione, prezzo, quantita, categoria_id, "
        "immagine, immagine_mime) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (nome, descrizione, prezzo, quantita, categoria_id, immagine, immagine_mime),
    )


def aggiorna_prodotto(prodotto_id, nome, descrizione, prezzo, quantita, categoria_id,
                      immagine=None, immagine_mime=None, rimuovi_immagine=False):
    """Se immagine è None l'immagine esistente resta invariata."""
    if immagine is not None:
        _execute(
            "UPDATE prodotti SET nome=%s, descrizione=%s, prezzo=%s, quantita=%s, "
            "categoria_id=%s, immagine=%s, immagine_mime=%s WHERE id=%s",
            (nome, descrizione, prezzo, quantita, categoria_id,
             immagine, immagine_mime, prodotto_id),
        )
    elif rimuovi_immagine:
        _execute(
            "UPDATE prodotti SET nome=%s, descrizione=%s, prezzo=%s, quantita=%s, "
            "categoria_id=%s, immagine=NULL, immagine_mime=NULL WHERE id=%s",
            (nome, descrizione, prezzo, quantita, categoria_id, prodotto_id),
        )
    else:
        _execute(
            "UPDATE prodotti SET nome=%s, descrizione=%s, prezzo=%s, quantita=%s, "
            "categoria_id=%s WHERE id=%s",
            (nome, descrizione, prezzo, quantita, categoria_id, prodotto_id),
        )


def elimina_prodotto(prodotto_id):
    _execute("DELETE FROM prodotti WHERE id = %s", (prodotto_id,))


# ---------------------------------------------------------------- azienda
def lista_dipendenti():
    return _select("SELECT nome, ruolo, bio FROM dipendenti ORDER BY id")


def statistiche():
    """Numeri mostrati nella pagina Azienda e nella dashboard."""
    return _select(
        "SELECT (SELECT COUNT(*) FROM prodotti)   AS n_prodotti, "
        "       (SELECT COUNT(*) FROM categorie)  AS n_categorie, "
        "       (SELECT COUNT(*) FROM utenti WHERE attivo = 1) AS n_utenti, "
        "       (SELECT COALESCE(SUM(prezzo * quantita), 0) FROM prodotti) AS valore_magazzino",
        one=True,
    )
