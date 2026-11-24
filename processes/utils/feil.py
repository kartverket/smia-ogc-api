"""Felles feilmelding for feil hos oss eller våre avhengigheter (Matrikkel, database).

pygeoapi svarer 400 på alle prosessfeil. `deploy/wsgi.py` kjenner igjen denne
meldingen og svarer 503 i stedet, så meldingen må ikke endres uten at begge
stedene følger med.
"""

SERVERFEIL_MELDING = "En feil oppstod, prøv igjen senere."
