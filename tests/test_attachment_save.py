from emails.client import EmailClient

client = EmailClient()
emails = client.filter(hours=1000)
for e in emails:
    print(e["sujet"], "→", e["fichiers_sauvegardes"])