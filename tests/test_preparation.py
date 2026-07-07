from extraction.data_preparation import DataPreparation

prep = DataPreparation()
contenu = prep.prepare("data/inbox_temp/BDC DITN.pdf")

print (contenu)