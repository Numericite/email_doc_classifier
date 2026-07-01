from config.settings import settings
from utils.serialization import serialize
from emails.attachment_extractor import AttachmentExtractor
from exchangelib import Credentials, Configuration, Account, DELEGATE
from datetime import datetime, date ,timedelta
from exchangelib import EWSDateTime

class EmailClient:
    def connect(self):
        creds = Credentials(settings.email_address, settings.email_password)
        config = Configuration(server=settings.exchange_server, credentials=creds)
        self.account = Account(
            primary_smtp_address=settings.exchange_email,
            config=config,
            access_type=DELEGATE,
            autodiscover=False,
        )
        return self.account
    

    
    def filter(self, hours=30):
      account = self.connect()
      extractor = AttachmentExtractor()          # ajout
      limite = EWSDateTime.now(tz=account.default_timezone) - timedelta(hours=hours)
      qs = account.inbox.filter(datetime_received__gte=limite).only(
        'message_id', 'subject', 'sender',
        'datetime_received', 'has_attachments', 'attachments'
      )

      emails = []
      for item in qs.order_by('-datetime_received'):
        attachments = []
        for a in item.attachments:
            if not a.is_inline:
                attachments.append({
                    "nom_fichier": a.name,
                    "type": a.content_type,
                })
        if attachments:
            saved_files = extractor.extract(item)      # ajout : sauvegarde disque
            emails.append({
                "date": serialize(item.datetime_received),
                "sujet": item.subject,
                "sender": item.sender.email_address,
                "nom_sender": serialize(item.sender.name),
                "corps": item.text_body,
                "attachement": attachments,
                "fichiers_sauvegardes": [str(f) for f in saved_files],   # ajout
            })
      return emails

    