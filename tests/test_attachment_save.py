from emails.client import EmailClient

client = EmailClient()
emails = client.filter(hours=1)
for e in emails:
    print(e["sujet"], "→", e["fichiers_sauvegardes"])