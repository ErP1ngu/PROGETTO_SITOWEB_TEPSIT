"""
Punto 1 della consegna: connessione al database via Python e stampa dei dati.
Esegui:  python test_db.py   (dopo aver importato database.sql)
"""
import DB_tool

print("=== CATEGORIE ===")
for c in DB_tool.lista_categorie():
    print(f"{c['id']:>3}  {c['nome']}")

print("\n=== PRODOTTI ===")
for p in DB_tool.cerca_prodotti():
    print(f"{p['id']:>3}  {p['nome']:<32} {p['categoria'] or '-':<10} "
          f"{p['prezzo']:>8} €  (disp. {p['quantita']})")

print("\n=== UTENTI ===")
for u in DB_tool.lista_utenti():
    print(f"{u['id']:>3}  {u['username']:<10} {u['email']:<28} {u['ruolo']}")
