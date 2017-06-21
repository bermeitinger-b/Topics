# -*- coding: utf-8 -*-

"""Preprocessing.

This module contains functions for various preprocessing steps
provided by `DARIAH-DE`_.

.. _DARIAH-DE:
    https://de.dariah.eu
    https://github.com/DARIAH-DE
"""

__author__ = "DARIAH-DE"
__authors__ = "Steffen Pielstroem, Philip Duerholt, Sina Bock, Severin Simmler"
__email__ = "pielstroem@biozentrum.uni-wuerzburg.de"

from collections import Counter, defaultdict
import csv
import glob
from itertools import chain
import logging
from lxml import etree
import numpy as np
import os
import pandas as pd
from pathlib import Path
from itertools import zip_longest
from abc import abstractmethod, abstractproperty
from copy import deepcopy
import regex


log = logging.getLogger('preprocessing')
log.addHandler(logging.NullHandler())
logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s %(name)s: %(message)s')

regular_expression = r'\p{Letter}+\p{Punctuation}?\p{Letter}+'


def read_from_txt(doclist):
    """Opens TXT files using file paths.

    Description:
        With this function you can read plain text files. Commit a list of
        full paths or one single path as argument.
        Use the function `create_document_list()` to create a list of your text
        files.

    Args:
        doclist Union(list[str], str): List of all documents in the corpus
            or single path to TXT file.

    Yields:
        Document.

    Todo:
        * Separate metadata (author, header)

    Example:
        >>> list(read_from_txt('corpus_txt/Doyle_AScandalinBohemia.txt'))[0][:20]
        'A SCANDAL IN BOHEMIA'
    """
    log.info("Accessing TXT documents ...")
    if isinstance(doclist, str):
        with open(doclist, 'r', encoding='utf-8') as f:
            yield f.read()
    elif isinstance(doclist, list):
        for file in doclist:
            with open(file, 'r', encoding='utf-8') as f:
                yield f.read()


def read_from_tei(doclist):
    """Opens TEI XML files using file paths.

    Description:
        With this function you can read TEI encoded XML files. Commit a list of
        full paths or one single path as argument.
        Use the function `create_document_list()` to create a list of your XML
        files.

    Args:
        doclist Union(list[str], str): List of all documents in the corpus
            or single path to TEI XML file.

    Yields:
        Document.

    Todo:
        * Seperate metadata (author, header)?

    Example:
        >>> list(read_from_tei('corpus_tei/Schnitzler_Amerika.xml'))[0][142:159]
        'Arthur Schnitzler'
    """
    log.info("Accessing TEI XML documents ...")
    if not isinstance(doclist, list):
        doclist = [doclist]
    ns = dict(tei='http://www.tei-c.org/ns/1.0')
    for file in doclist:
        tree = etree.parse(file)
        text_el = tree.xpath('//tei:text', namespaces=ns)[0]
        yield "".join(text_el.xpath('.//text()'))


def read_from_csv(doclist, columns=['ParagraphId', 'TokenId', 'Lemma', 'CPOS', 'NamedEntity']):
    """Opens CSV files using file paths.

    Description:
        With this function you can read CSV files generated by `DARIAH-DKPro-Wrapper`_,
        a tool for natural language processing. Commit a list of full paths or
        one single path as argument. You also have the ability to select certain
        columns.
        Use the function `create_document_list()` to create a list of your CSV
        files.
        .. _DARIAH-DKPro-Wrapper:
            https://github.com/DARIAH-DE/DARIAH-DKPro-Wrapper

    Args:
        doclist Union(list[str], str): List of all documents in the corpus
            or single path to CSV file.
        columns (list[str]): List of CSV column names.
            Defaults to '['ParagraphId', 'TokenId', 'Lemma', 'CPOS', 'NamedEntity']'.

    Yields:
        Document.

    Todo:
        * Seperate metadata (author, header)?

    Example:
        >>> list(read_from_csv('corpus_csv/Doyle_AScandalinBohemia.txt.csv'))[0][:4] # doctest: +NORMALIZE_WHITESPACE
                   ParagraphId  TokenId    Lemma CPOS NamedEntity
        0            0        0        a  ART           _
        1            0        1  scandal   NP           _
        2            0        2       in   PP           _
        3            0        3  bohemia   NP           _
    """
    log.info("Accessing CSV documents ...")
    if isinstance(doclist, str):
        doclist = [doclist]
    for file in doclist:
        df = pd.read_csv(file, sep='\t', quoting=csv.QUOTE_NONE)
        yield df[columns]


def tokenize(doc_txt, expression=regular_expression, lower=True, simple=False):
    """Tokenizes with Unicode Regular Expressions.

    Description:
        With this function you can tokenize a document with a regular expression.
        You also have the ability to commit your own regular expression. The default
        expression is '\p{Letter}+\p{Punctuation}?\p{Letter}+', which means one or
        more letters, followed by one or no punctuation, followed by one or more
        letters. So one letter words won't match.
        In case you want to lower alls tokens, set the argument `lower` to True (it
        is by default).
        If you want a very simple and primitive tokenization, set the argument
        `simple` to True.
        Use the functions `read_from_txt()`, `read_from_tei()` or `read_from_csv()`
        to read your text files.

    Args:
        doc_txt (str): Document as string.
        expression (str): Regular expression to find tokens.
        lower (boolean): If True, lowers all words. Defaults to True.
        simple (boolean): Uses simple regular expression (r'\w+'). Defaults to False.
            If set to True, argument `expression` will be ignored.

    Yields:
        Tokens

    Example:
        >>> list(tokenize("This is one example text."))
        ['this', 'is', 'one', 'example', 'text']
    """
    if lower:
        doc_txt = doc_txt.lower()
    if simple:
        pattern = regex.compile(r'\w+')
    else:
        pattern = regex.compile(expression)
    doc_txt = regex.sub("\.", "", doc_txt)
    doc_txt = regex.sub("‒", " ", doc_txt)
    doc_txt = regex.sub("–", " ", doc_txt)
    doc_txt = regex.sub("—", " ", doc_txt)
    doc_txt = regex.sub("―", " ", doc_txt)
    tokens = pattern.finditer(doc_txt)
    for match in tokens:
        yield match.group()


def filter_pos_tags(doc_csv, pos_tags=['ADJ', 'V', 'NN']):
    """Gets lemmas by selected POS-tags from DARIAH-DKPro-Wrapper output.

    Description:
        With this function you can select certain columns of a CSV file
        generated by `DARIAH-DKPro-Wrapper`_, a tool for natural language processing.
        Use the function `read_from_csv()` to read CSV files.
        .. _DARIAH-DKPro-Wrapper:
            https://github.com/DARIAH-DE/DARIAH-DKPro-Wrapper

    Args:
        doc_csv (DataFrame): DataFrame containing DARIAH-DKPro-Wrapper output.
        pos_tags (list[str]): List of DKPro POS-tags that should be selected.
            Defaults to '['ADJ', 'V', 'NN']'.

    Yields:
        Lemma.

    Example:
        >>> df = pd.DataFrame({'CPOS': ['CARD', 'ADJ', 'NN', 'NN'],
        ...                    'Lemma': ['one', 'more', 'example', 'text']})
        >>> list(filter_pos_tags(df))[0] # doctest: +NORMALIZE_WHITESPACE
        1    more
        2    example
        3    text
        Name: Lemma, dtype: object
    """
    log.info("Accessing %s ...", pos_tags)
    doc_csv = doc_csv[doc_csv['CPOS'].isin(pos_tags)]
    yield doc_csv['Lemma']


def split_paragraphs(doc_txt, sep=regex.compile('\n')):
    """Splits the given document by paragraphs.

    Description:
        With this function you can split a document by paragraphs. You also have
        the ability to select a certain regular expression to split the document.
        Use the functions `read_from_txt()`, `read_from_tei()` or `read_from_csv()`
        to read your text files.

    Args:
        doc_txt (str): Document text.
        sep (regex.Regex): Separator indicating a paragraph.

    Returns:
        List of paragraphs.

    Example:
        >>> split_paragraphs("This test contains \\n paragraphs.")
        ['This test contains ', ' paragraphs.']
    """
    if not hasattr(sep, 'match'):
        sep = regex.compile(sep)
    return sep.split(doc_txt)


def segment_fuzzy(document, segment_size=5000, tolerance=0.05):
    """Segments a document, tolerating existing chunks (like paragraphs).

    Description:
        Consider you have a document. You wish to split the document into
        segments of about 1000 tokens, but you prefer to keep paragraphs together
        if this does not increase or decrease the token size by more than 5%.

    Args:
        document: The document to process. This is an Iterable of chunks, each
            of which is an iterable of tokens.
        segment_size (int): The target length of each segment in tokens.
        tolerance (Number): How much may the actual segment size differ from
            the segment_size? If 0 < tolerance < 1, this is interpreted as a
            fraction of the segment_size, otherwise it is interpreted as an
            absolute number. If tolerance < 0, chunks are never split apart.

    Yields:
        Segments. Each segment is a list of chunks, each chunk is a list of
        tokens.

    Example:
        >>> list(segment_fuzzy([['This', 'test', 'is', 'very', 'clear'],
        ...                     ['and', 'contains', 'chunks']], 2)) # doctest: +NORMALIZE_WHITESPACE
        [[['This', 'test']],
        [['is', 'very']],
        [['clear'], ['and']],
        [['contains', 'chunks']]]
    """
    if tolerance > 0 and tolerance < 1:
        tolerance = round(segment_size * tolerance)

    current_segment = []
    current_size = 0
    carry = None
    doc_iter = iter(document)

    try:
        while True:
            chunk = list(carry if carry else next(doc_iter))
            carry = None
            current_segment.append(chunk)
            current_size += len(chunk)

            if current_size >= segment_size:
                too_long = current_size - segment_size
                too_short = segment_size - (current_size - len(chunk))

                if tolerance >= 0 and min(too_long, too_short) > tolerance:
                    chunk_part0 = chunk[:-too_long]
                    carry = chunk[-too_long:]
                    current_segment[-1] = chunk_part0
                elif too_long >= too_short:
                    carry = current_segment.pop()
                yield current_segment
                current_segment = []
                current_size = 0
    except StopIteration:
        pass

    # handle leftovers
    if current_segment:
        yield current_segment


def segment(document, segment_size=1000, tolerance=0, chunker=None,
            tokenizer=None, flatten_chunks=False, materialize=False):
    """Segments a document into segments of about `segment_size` tokens, respecting existing chunks.

    Description:
        Consider you have a document. You wish to split the document into
        segments of about 1000 tokens, but you prefer to keep paragraphs together
        if this does not increase or decrease the token size by more than 5%.
        This is a convenience wrapper around `segment_fuzzy()`.

    Args:
        segment_size (int): The target size of each segment, in tokens.
        tolerance (Number): see `segment_fuzzy`
        chunker (callable): a one-argument function that cuts the document into
            chunks. If this is present, it is called on the given document.
        tokenizer (callable): a one-argument function that tokenizes each chunk.
        flatten_chunks (bool): if True, undo the effect of the chunker by
            chaining the chunks in each segment, thus each segment consists of
            tokens. This can also be a one-argument function in order to
            customize the un-chunking.

    Example:
        >>> list(segment([['This', 'test', 'is', 'very', 'clear'],
        ...               ['and', 'contains', 'chunks']], 2)) # doctest: +NORMALIZE_WHITESPACE
        [[['This', 'test']],
        [['is', 'very']],
        [['clear'], ['and']],
        [['contains', 'chunks']]]
    """
    if chunker is not None:
        document = chunker(document)
    if tokenizer is not None:
        document = map(tokenizer, document)

    segments = segment_fuzzy(document, segment_size, tolerance)

    if flatten_chunks:
        if not callable(flatten_chunks):
            def flatten_chunks(segment):
                return list(chain.from_iterable(segment))
        segments = map(flatten_chunks, segments)
    if materialize:
        segments = list(segments)

    return segments

def remove_features_from_file(doc_token_list, features_to_be_removed):
    """Removes features using feature list.

    Description:
        With this function you can remove features from ppreprocessed files.
        Commit a list of features.
        Use the function `tokenize()` to access your files.

    Args:
        doc_token_list Union(list[str], str): List of all documents in the corpus
            and their tokens.
        features_to_be_removed list[str]: List of features that should be
        removed
    Yields:
        cleaned token array

    Todo:

    Example:
        >>> doc_tokens = [['short', 'example', 'example', 'text', 'text']]
        >>> features_to_be_removed = ['example']
        >>> test = remove_features_from_file(doc_tokens, features_to_be_removed)
        >>> list(test)
        [['short', 'text', 'text']]
    """
    #log.info("Removing features ...")
    doc_token_array = np.array(doc_token_list)
    feature_array = np.array(features_to_be_removed)
    #get indices of features that should be deleted
    indices = np.where(np.in1d(doc_token_array, feature_array,))
    doc_token_array = np.delete(doc_token_array, indices)
    yield doc_token_array.tolist()

def create_mallet_import(doc_tokens_cleaned, doc_labels, outpath = os.path.join('tutorial_supplementals', 'mallet_input')):
    """Creates files for mallet import.

    Description:
        With this function you can create preprocessed plain text files.
        Commit a list of full paths or one single path as argument.
        Use the function `remove_features_from_file()` to create a list of tokens
        per document.

    Args:
        doc_tokens_cleaned Union(list[str], str): List of tokens per document
        doc_labels list[str]: List of documents labels.

    Todo:

    Example:
        >>> doc_labels = ['examplefile']
        >>> doc_tokens_cleaned = [['short', 'example', 'text']]
        >>> create_mallet_import(doc_tokens_cleaned, doc_labels)
        >>> outpath = os.path.join('tutorial_supplementals', 'mallet_input')
        >>> os.path.isfile(os.path.join(outpath, 'examplefile.txt'))
        True
    """
    #log.info("Generating mallet input files ...")
    if not os.path.exists(outpath):
                os.makedirs(outpath)

    for tokens, label in zip(doc_tokens_cleaned, doc_labels):
        with open(os.path.join(outpath,label+'.txt'), 'w', encoding="utf-8") as f:
            f.write(str(tokens))


def create_dictionary(tokens):
    """Creates a dictionary of unique tokens with identifier.

    Description:
        With this function you can create a dictionary of unique tokens as key
        and an identifier as value.
        Use the function `tokenize()` to tokenize your text files.

    Args:
        tokens (list): List of tokens.

    Returns:
        Dictionary.

    Example:
        >>> create_dictionary(['example'])
        {'example': 1}
    """
    if all(isinstance(element, list) for element in tokens):
        tokens = {token for element in tokens for token in element}
    return {token: id_ for id_, token in enumerate(set(tokens), 1)}


def _create_large_counter(doc_labels, doc_tokens, type_dictionary):
    """Creates a dictionary of dictionaries.

    Description:
        Only the function `create_sparse_bow()` uses this private function to
        create a dictionary of dictionaries.
        The first level consists of the document label as key, and the dictionary
        of counts as value. The second level consists of token ID as key, and the
        count of tokens in document pairs as value.

    Args:
        doc_labels (list): List of doc labels.
        doc_tokens (list): List of tokens.
        type_dictionary (dict): Dictionary of {token: id}.

    Returns:
        Dictionary of dictionaries.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'example', 'text', 'text']]
        >>> type_dictionary = {'short': 1, 'example': 2, 'text': 3}
        >>> isinstance(_create_large_counter(doc_labels, doc_tokens, type_dictionary), defaultdict)
        True
    """
    largecounter = defaultdict(dict)
    for doc, tokens in zip(doc_labels, doc_tokens):
        largecounter[doc] = Counter(
            [type_dictionary[token] for token in tokens])
    return largecounter


def _create_sparse_index(largecounter):
    """Creates a sparse index for pandas DataFrame.

    Description:
        Only the function `create_sparse_bow()` uses this private function to
        create a pandas multiindex out of tuples.
        The multiindex represents document ID to token IDs relations.

    Args:
        largecounter (dict): Dictionary of {document: {token: frequency}}.

    Returns:
        Pandas MultiIndex.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'example', 'text', 'text']]
        >>> type_dictionary = {'short': 1, 'example': 2, 'text': 3}
        >>> largecounter = _create_large_counter(doc_labels, doc_tokens, type_dictionary)
        >>> isinstance(_create_sparse_index(largecounter), pd.MultiIndex)
        True
    """
    tuples = []
    for key in range(1, len(largecounter) + 1):
        if len(largecounter[key]) == 0:
            tuples.append((key, 0))
        for value in largecounter[key]:
            tuples.append((key, value))
    sparse_index = pd.MultiIndex.from_tuples(
        tuples, names=['doc_id', 'token_id'])
    return sparse_index


def create_sparse_bow(doc_labels, doc_tokens, type_dictionary, doc_dictionary):
    """Creates sparse matrix for bag-of-words model.

    Description:
        This function creates a sparse DataFrame ('bow' means `bag-of-words`_)
        containing document and type identifier as multiindex and type
        frequencies as values representing the counts of tokens for each token
        in each document.
        It is also the main function that incorporates the private functions
        `_create_large_counter()` and `_create_sparse_index()``.
        Use the function `get_labels()` for `doc_labels`, `tokenize()` for
        `doc_tokens`, and `create_dictionary()` for `type_dictionary` as well
        as for `doc_ids`.
        Use the function `create_dictionary()` to generate the dictionaries
        `type_dictionary` and `doc_dictionary`.
        .. _bag-of-words:
            https://en.wikipedia.org/wiki/Bag-of-words_model

    Args:
        doc_labels (list[str]): List of doc labels as string.
        doc_tokens (list[str]): List of tokens as string.
        type_dictionary (dict[str]): Dictionary with {token: id}.
        doc_ids (dict[str]): Dictionary with {document label: id}.

    Returns:
        Multiindexed Pandas DataFrame.

    ToDo:
        * Test if it's necessary to build sparse_df_filled with int8 zeroes instead of int64.
        * Avoid saving sparse bow as .mm file to ingest into gensim.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'text']]
        >>> type_dictionary = {'short': 1, 'example': 2, 'text': 3}
        >>> doc_ids = {'exampletext': 1}
        >>> len(create_sparse_bow(doc_labels, doc_tokens, type_dictionary, doc_ids))
        3
    """
    temp_counter = _create_large_counter(
        doc_labels, doc_tokens, type_dictionary)
    largecounter = {doc_dictionary[key]: value for key, value in temp_counter.items()}
    sparse_index = _create_sparse_index(largecounter)
    sparse_bow_filled = pd.DataFrame(
        np.zeros((len(sparse_index), 1), dtype=int), index=sparse_index)
    index_iterator = sparse_index.groupby(
        sparse_index.get_level_values('doc_id'))

    for doc_id in range(1, len(sparse_index.levels[0]) + 1):
        for token_id in [val[1] for val in index_iterator[doc_id]]:
            sparse_bow_filled.set_value(
                (doc_id, token_id), 0, int(largecounter[doc_id][token_id]))
    return sparse_bow_filled


def save_sparse_bow(sparse_bow, output):
    """Saves sparse matrix for bag-of-words model.

    Description:
        With this function you can save the sparse matrix as `.mm file`_.
        .. _.mm file: http://math.nist.gov/MatrixMarket/formats.html#MMformat

    Args:
        sparse_bow (DataFrame): DataFrame with term and term frequency by document.
        output (str): Path to output file without extension, e.g. /tmp/sparsebow.

    Returns:
        None.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'text']]
        >>> type_dictionary = {'short': 1, 'example': 2, 'text': 3}
        >>> doc_ids = {'exampletext': 1}
        >>> sparse_bow = create_sparse_bow(doc_labels, doc_tokens, type_dictionary, doc_ids)
        >>> save_sparse_bow(sparse_bow, 'sparsebow')
        >>> import os.path
        >>> os.path.isfile('sparsebow.mm')
        True
    """
    num_docs = sparse_bow.index.get_level_values("doc_id").max()
    num_types = sparse_bow.index.get_level_values("token_id").max()
    sum_counts = sparse_bow[0].sum()

    header_string = str(num_docs) + " " + str(num_types) + \
        " " + str(sum_counts) + "\n"

    with open('.'.join([output, 'mm']), 'w', encoding="utf-8") as f:
        f.write("%%MatrixMarket matrix coordinate real general\n")
        f.write(header_string)
        sparse_bow.to_csv(f, sep=' ', header=None)


def find_stopwords(sparse_bow, id_types, mfw=200):
    """Creates a stopword list.

    Description:
        With this function you can determine most frequent words, also known as
        stopwords. First, you have to translate your corpus into the bag-of-words
        model using the function `create_sparse_matrix()` and create an dictionary
        containing types and identifier using `create_dictionary()`.

    Args:
        sparse_bow (DataFrame): DataFrame with term and term frequency by document.
        id_types (dict[str]): Dictionary with {token: id}.
        mfw (int): Target size of most frequent words to be considered.

    Returns:
        Most frequent words in a list.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'short', 'example', 'text']]
        >>> id_types = {'short': 1, 'example': 2, 'text': 3}
        >>> doc_ids = {'exampletext': 1}
        >>> sparse_bow = create_sparse_bow(doc_labels, doc_tokens, id_types, doc_ids)
        >>> find_stopwords(sparse_bow, id_types, 1)
        ['short']
    """
    log.info("Finding stopwords ...")
    type2id = {value: key for key, value in id_types.items()}
    sparse_bow_collapsed = sparse_bow.groupby(
        sparse_bow.index.get_level_values('token_id')).sum()
    sparse_bow_stopwords = sparse_bow_collapsed[0].nlargest(mfw)
    stopwords = [type2id[key]
                 for key in sparse_bow_stopwords.index.get_level_values('token_id')]
    return stopwords


def find_hapax(sparse_bow, id_types):
    """Creates a list with hapax legommena.

    Description:
        With this function you can determine hapax legomena for each document.
        First, you have to translate your corpus into the bag-of-words
        model using the function `create_sparse_matrix()` and create an dictionary
        containing types and identifier using `create_dictionary()`.

    Args:
        sparse_bow (DataFrame): DataFrame with term and term frequency by document.
        id_types (dict[str]): Dictionary with {token: id}.

    Returns:
        Hapax legomena in a list.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'example', 'text', 'text']]
        >>> id_types = {'short': 1, 'example': 2, 'text': 3}
        >>> doc_ids = {'exampletext': 1}
        >>> sparse_bow = create_sparse_bow(doc_labels, doc_tokens, id_types, doc_ids)
        >>> find_hapax(sparse_bow, id_types)
        ['short']
    """
    log.info("Finding hapax legomena ...")
    type2id = {value: key for key, value in id_types.items()}
    sparse_bow_collapsed = sparse_bow.groupby(
        sparse_bow.index.get_level_values('token_id')).sum()
    sparse_bow_hapax = sparse_bow_collapsed.loc[sparse_bow_collapsed[0] == 1]
    hapax = [type2id[key]
             for key in sparse_bow_hapax.index.get_level_values('token_id')]
    return hapax


def remove_features(sparse_bow, id_types, features):
    """Removes features based on a list of words (types).

    Description:
        With this function you can clean your corpus from stopwords and hapax
        legomena.
        First, you have to translate your corpus into the bag-of-words
        model using the function `create_sparse_bow()` and create a dictionary
        containing types and identifier using `create_dictionary()`.
        Use the functions `find_stopwords()` and `find_hapax()` to generate a
        feature list.

    Args:
        sparse_bow (DataFrame): DataFrame with term and term frequency by document.
        features Union(set, list): Set or list containing features to remove.
        (not included) features (str): Text as iterable.

    Returns:
        Clean corpus.

    ToDo:
        * Adapt function to work with mm-corpus format.

    Example:
        >>> doc_labels = ['exampletext']
        >>> doc_tokens = [['short', 'example', 'example', 'text', 'text']]
        >>> id_types = {'short': 1, 'example': 2, 'text': 3}
        >>> doc_ids = {'exampletext': 1}
        >>> sparse_bow = create_sparse_bow(doc_labels, doc_tokens, id_types, doc_ids)
        >>> features = ['short']
        >>> len(remove_features(sparse_bow, id_types, features))
        2
    """
    log.info("Removing features ...")
    if isinstance(features, list):
        features = set(features)
    stoplist_applied = [word for word in set(id_types.keys()) if word in features]
    clean_sparse_bow = sparse_bow.drop([id_types[word] for word in stoplist_applied], level="token_id")
    log.debug("%s features removed.", len(features))
    return clean_sparse_bow


def make_doc2bow_list(sparse_bow):
    """Creates doc2bow_list for gensim.

    Description:
        With this function you can create a doc2bow_list as input for the gensim
        function `get_document_topics()` to show topics for each document.

    Args:
        sparse_bow (DataFrame): DataFrame with term and term frequency by document.

    Returns:
        List of lists containing tuples.

    Example:
        >>> doc_labels = ['exampletext1', 'exampletext2']
        >>> doc_tokens = [['test', 'corpus'], ['for', 'testing']]
        >>> type_dictionary = {'test': 1, 'corpus': 2, 'for': 3, 'testing': 4}
        >>> doc_dictionary = {'exampletext1': 1, 'exampletext2': 2}
        >>> sparse_bow = create_sparse_bow(doc_labels, doc_tokens, type_dictionary, doc_dictionary)
        >>> from gensim.models import LdaModel
        >>> from gensim.corpora import Dictionary
        >>> corpus = [['test', 'corpus'], ['for', 'testing']]
        >>> dictionary = Dictionary(corpus)
        >>> documents = [dictionary.doc2bow(document) for document in corpus]
        >>> model = LdaModel(corpus=documents, id2word=dictionary, iterations=1, passes=1, num_topics=1)
        >>> make_doc2bow_list(sparse_bow)
        [[(1, 1), (2, 1)], [(3, 1), (4, 1)]]
    """
    doc2bow_list = []
    for doc in sparse_bow.index.groupby(sparse_bow.index.get_level_values('doc_id')):
        temp = [(token, count) for token, count in zip(
            sparse_bow.loc[doc].index, sparse_bow.loc[doc][0])]
        doc2bow_list.append(temp)
    return doc2bow_list


def gensim2dataframe(model, num_keys=10):
    """Converts gensim output to DataFrame.

    Description:
        With this function you can convert gensim output (usually a list of
        tuples) to a DataFrame, a more convenient datastructure.

    Args:
        model: Gensim LDA model.
        num_keys (int): Number of top keywords for topic.

    Returns:
        DataFrame.

    ToDo:

    Example:
        >>> from gensim.models import LdaModel
        >>> from gensim.corpora import Dictionary
        >>> corpus = [['test', 'corpus'], ['for', 'testing']]
        >>> dictionary = Dictionary(corpus)
        >>> documents = [dictionary.doc2bow(document) for document in corpus]
        >>> model = LdaModel(corpus=documents, id2word=dictionary, iterations=1, passes=1, num_topics=1)
        >>> isinstance(gensim2dataframe(model, 4), pd.DataFrame)
        True
    """
#    num_topics = model.num_topics
#    topics_df = pd.DataFrame(index=range(num_topics), columns=range(num_keys))
#    topics = model.show_topics(
#        num_topics=num_topics, log=False, formatted=False)
#    for topic in topics:
#        idx = topic[0]
#        temp = topic[1]
#        topics_df.loc[idx] = temp

    num_topics = model.num_topics
    topics_df = pd.DataFrame(index = range(num_topics),
                                 columns= range(num_keys))

    topics = model.show_topics(num_topics = model.num_topics, formatted=False)

    for topic, values in topics:
        keyword = [value[0] for value in values]
        topics_df.loc[topic] = keyword

    return topics_df


def doctopic2dataframe(model, doc2bow_list, doc2id):
    """Use only for testing purposes, not working properly

    Note:

    Args:

    Returns:

    ToDo: make it work
    """
    df = pd.DataFrame()
    for idx, doc in enumerate(doc2bow_list, 1):
        df[doc2id[idx]] = pd.Series(
            [value[1] for value in model.get_document_topics(doc)])
    return df.fillna(0)
