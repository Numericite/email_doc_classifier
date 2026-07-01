from emails.client import EmailClient

client = EmailClient()
emails = client.filter(hours=30)
for e in emails:
    print(e["sujet"], "→", e["fichiers_sauvegardes"])