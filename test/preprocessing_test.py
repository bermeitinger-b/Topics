from dariah_topics import preprocessing as pre
from pathlib import Path

project_path = Path(__file__).absolute().parent.parent

# Funktion muss irgendwie mit test heißen
def test_document_list():

    # die Funktion under test aufrufen

    doclist = pre.create_document_list(str(Path(project_path, 'corpus_txt')))

    # Bedingungen auf dem Ergebnis prüfen:
    assert len(doclist) == 17

    return doclist

def test_document_labels():
    doclist = test_document_list()
    labels = pre.get_labels(doclist)
    assert len(list(labels)) == len(doclist)
